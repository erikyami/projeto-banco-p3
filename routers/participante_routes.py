import uuid
from typing import Optional
from fastapi import APIRouter, Request, Form, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pymysql.err import IntegrityError

from database import fetch_all, fetch_one, execute_query
from auth import require_auth, hash_senha, criar_token, COOKIE_NAME

router = APIRouter(prefix="/participante", tags=["Área do Participante"])
templates = Jinja2Templates(directory="templates")


def verificar_participante(request: Request):
    return require_auth(request, allowed_roles=["PARTICIPANTE"])


@router.get("/painel", response_class=HTMLResponse)
async def painel_participante(request: Request, msg: str = None, tipo: str = "info", user: dict = Depends(verificar_participante)):
    id_part = user["id"]

    # Inscrições ativas do participante
    minhas_inscricoes = await fetch_all("""
        SELECT 
            i.id_inscricao,
            i.numero,
            i.data_inscricao,
            e.id_evento,
            e.nome AS evento_nome,
            e.data_inicio,
            e.data_fim,
            e.local
        FROM inscricao i
        INNER JOIN evento e ON i.id_evento = e.id_evento
        WHERE i.id_participante = %s
        ORDER BY i.data_inscricao DESC
    """, (id_part,))

    # Atividades que o participante está cursando
    minhas_atividades = await fetch_all("""
        SELECT 
            pa.id_participacao,
            a.nome AS atividade_nome,
            a.tipo,
            a.data_atividade,
            a.carga_horaria,
            a.frequencia_minima,
            e.nome AS evento_nome,
            COUNT(pr.id_presenca) AS total_dias_registrados,
            SUM(COALESCE(pr.presente, 0)) AS presencas,
            ROUND((SUM(COALESCE(pr.presente, 0)) / NULLIF(COUNT(pr.id_presenca), 0)) * 100, 2) AS frequencia_atual,
            c.id_certificado,
            c.codigo_validacao,
            c.status AS status_certificado
        FROM participacao_atividade pa
        INNER JOIN inscricao i ON pa.id_inscricao = i.id_inscricao
        INNER JOIN atividade a ON pa.id_atividade = a.id_atividade
        INNER JOIN evento e ON a.id_evento = e.id_evento
        LEFT JOIN presenca pr ON pa.id_participacao = pr.id_participacao
        LEFT JOIN certificado c ON pa.id_participacao = c.id_participacao
        WHERE i.id_participante = %s
        GROUP BY pa.id_participacao
        ORDER BY a.data_atividade DESC
    """, (id_part,))

    # Eventos e atividades disponíveis para novas inscrições
    eventos_disponiveis = await fetch_all("""
        SELECT e.*
        FROM evento e
        WHERE e.status = 'ATIVO'
          AND e.id_evento NOT IN (SELECT id_evento FROM inscricao WHERE id_participante = %s)
        ORDER BY e.data_inicio ASC
    """, (id_part,))

    atividades_disponiveis = await fetch_all("""
        SELECT a.*, e.nome AS evento_nome
        FROM atividade a
        INNER JOIN evento e ON a.id_evento = e.id_evento
        INNER JOIN inscricao i ON e.id_evento = i.id_evento AND i.id_participante = %s
        WHERE a.id_atividade NOT IN (
            SELECT pa.id_atividade FROM participacao_atividade pa
            INNER JOIN inscricao i2 ON pa.id_inscricao = i2.id_inscricao
            WHERE i2.id_participante = %s
        )
    """, (id_part, id_part))

    minhas_presencas_detalhadas = await fetch_all("""
        SELECT 
            pr.data_aula,
            pr.presente,
            pr.data_registro,
            pr.data_remocao,
            a.nome AS atividade_nome,
            e.nome AS evento_nome,
            u_gerou.nome AS staff_gerou_nome,
            u_removeu.nome AS staff_removeu_nome
        FROM presenca pr
        INNER JOIN participacao_atividade pa ON pr.id_participacao = pa.id_participacao
        INNER JOIN inscricao i ON pa.id_inscricao = i.id_inscricao
        INNER JOIN atividade a ON pa.id_atividade = a.id_atividade
        INNER JOIN evento e ON a.id_evento = e.id_evento
        LEFT JOIN usuario u_gerou ON pr.id_usuario = u_gerou.id_usuario
        LEFT JOIN usuario u_removeu ON pr.id_usuario_remocao = u_removeu.id_usuario
        WHERE i.id_participante = %s
        ORDER BY pr.data_aula DESC
    """, (id_part,))

    return templates.TemplateResponse(
        request=request,
        name="participante/painel.html",
        context={
            "user": user,
            "inscricoes": minhas_inscricoes,
            "atividades": minhas_atividades,
            "presencas_detalhadas": minhas_presencas_detalhadas,
            "eventos_disponiveis": eventos_disponiveis,
            "atividades_disponiveis": atividades_disponiveis,
            "msg": msg,
            "tipo": tipo
        }
    )


@router.post("/inscrever-evento")
async def inscrever_evento(id_evento: int = Form(...), user: dict = Depends(verificar_participante)):
    id_part = user["id"]
    numero_inscricao = f"INS-2026-{uuid.uuid4().hex[:6].upper()}"

    query = """
        INSERT INTO inscricao (id_participante, id_evento, numero, status)
        VALUES (%s, %s, %s, 'CONFIRMADA')
    """
    try:
        await execute_query(query, (id_part, id_evento, numero_inscricao))
        return RedirectResponse(
            url="/participante/painel?msg=Inscricao+no+evento+confirmada+com+sucesso!&tipo=success",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except IntegrityError:
        return RedirectResponse(
            url="/participante/painel?msg=Voce+ja+esta+inscrito+neste+evento.&tipo=warning",
            status_code=status.HTTP_303_SEE_OTHER
        )


@router.post("/inscrever-atividade")
async def inscrever_atividade(id_atividade: int = Form(...), user: dict = Depends(verificar_participante)):
    id_part = user["id"]

    # Obter id_inscricao do participante no evento da atividade
    dados_insc = await fetch_one("""
        SELECT i.id_inscricao
        FROM inscricao i
        INNER JOIN atividade a ON i.id_evento = a.id_evento
        WHERE i.id_participante = %s AND a.id_atividade = %s
    """, (id_part, id_atividade))

    if not dados_insc:
        return RedirectResponse(
            url="/participante/painel?msg=Voce+precisa+estar+inscrito+no+evento+antes+de+se+inscrever+na+atividade.&tipo=danger",
            status_code=status.HTTP_303_SEE_OTHER
        )

    query = """
        INSERT INTO participacao_atividade (id_inscricao, id_atividade, status)
        VALUES (%s, %s, 'CONFIRMADA')
    """
    try:
        await execute_query(query, (dados_insc["id_inscricao"], id_atividade))
        return RedirectResponse(
            url="/participante/painel?msg=Inscricao+na+atividade+realizada+com+sucesso!&tipo=success",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except IntegrityError:
        return RedirectResponse(
            url="/participante/painel?msg=Voce+ja+esta+inscrito+nesta+atividade.&tipo=warning",
            status_code=status.HTTP_303_SEE_OTHER
        )


# ====================================================================
# PERFIL DO PARTICIPANTE (VISUALIZAÇÃO E EDIÇÃO)
# ====================================================================

@router.get("/perfil", response_class=HTMLResponse)
async def ver_perfil_participante(request: Request, msg: str = None, tipo: str = "info", user: dict = Depends(verificar_participante)):
    dados_part = await fetch_one(
        "SELECT id_participante, cpf, nome, email, telefone FROM participante WHERE id_participante = %s",
        (user["id"],)
    )
    return templates.TemplateResponse(
        request=request,
        name="participante/perfil.html",
        context={"user": user, "participante": dados_part, "msg": msg, "tipo": tipo}
    )


@router.post("/perfil")
async def atualizar_perfil_participante(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    telefone: Optional[str] = Form(None),
    senha: Optional[str] = Form(None),
    user: dict = Depends(verificar_participante)
):
    id_part = user["id"]
    nome_limpo = nome.strip()
    email_limpo = email.strip().lower()

    try:
        if senha and len(senha.strip()) >= 6:
            senha_hash = hash_senha(senha.strip())
            await execute_query("""
                UPDATE participante 
                SET nome = %s, email = %s, telefone = %s, senha_hash = %s
                WHERE id_participante = %s
            """, (nome_limpo, email_limpo, telefone, senha_hash, id_part))
        else:
            await execute_query("""
                UPDATE participante 
                SET nome = %s, email = %s, telefone = %s
                WHERE id_participante = %s
            """, (nome_limpo, email_limpo, telefone, id_part))

        # Atualiza a sessão
        token_payload = {
            "id": id_part,
            "nome": nome_limpo,
            "email": email_limpo,
            "perfil": "PARTICIPANTE"
        }
        novo_jwt = criar_token(token_payload)
        resp = RedirectResponse(url="/participante/perfil?msg=Dados+cadastrais+atualizados+com+sucesso!&tipo=success", status_code=status.HTTP_303_SEE_OTHER)
        resp.set_cookie(key=COOKIE_NAME, value=novo_jwt, httponly=True, max_age=86400, samesite="lax")
        return resp

    except IntegrityError as e:
        if e.args[0] == 1062:
            return RedirectResponse(
                url="/participante/perfil?msg=ERRO:+Ja+existe+outro+usuario+cadastrado+com+este+E-mail.&tipo=danger",
                status_code=status.HTTP_303_SEE_OTHER
            )
        return RedirectResponse(
            url=f"/participante/perfil?msg=Erro+ao+atualizar:+{e}&tipo=danger",
            status_code=status.HTTP_303_SEE_OTHER
        )
