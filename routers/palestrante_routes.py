from typing import Optional
from fastapi import APIRouter, Request, Form, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pymysql.err import IntegrityError

from database import fetch_all, fetch_one, execute_query
from auth import require_auth, hash_senha, criar_token, COOKIE_NAME

router = APIRouter(prefix="/palestrante", tags=["Área do Palestrante"])
templates = Jinja2Templates(directory="templates")


def verificar_palestrante(request: Request):
    return require_auth(request, allowed_roles=["PALESTRANTE"])


@router.get("/painel", response_class=HTMLResponse)
async def painel_palestrante(request: Request, msg: Optional[str] = None, tipo: str = "info", user: dict = Depends(verificar_palestrante)):
    id_palestrante = user["id"]

    # 1. Atividades ministradas pelo palestrante
    minhas_atividades = await fetch_all("""
        SELECT 
            a.id_atividade,
            a.nome AS atividade_nome,
            a.tipo,
            a.data_atividade,
            a.hora_inicio,
            a.hora_fim,
            a.carga_horaria,
            a.status AS status_atividade,
            e.nome AS evento_nome,
            e.local,
            COUNT(DISTINCT pa.id_participacao) AS total_alunos_inscritos
        FROM atividade_palestrante ap
        INNER JOIN atividade a ON ap.id_atividade = a.id_atividade
        INNER JOIN evento e ON a.id_evento = e.id_evento
        LEFT JOIN participacao_atividade pa ON a.id_atividade = pa.id_atividade
        WHERE ap.id_palestrante = %s
        GROUP BY a.id_atividade
        ORDER BY a.data_atividade DESC
    """, (id_palestrante,))

    # 2. Certificados de palestrante emitidos
    meus_certificados = await fetch_all("""
        SELECT 
            c.id_certificado,
            c.codigo_validacao,
            c.status AS status_certificado,
            c.data_emissao,
            c.carga_horaria,
            a.nome AS atividade_nome,
            e.nome AS evento_nome
        FROM certificado c
        INNER JOIN atividade a ON c.id_atividade = a.id_atividade
        INNER JOIN evento e ON a.id_evento = e.id_evento
        WHERE c.tipo_destinatario = 'PALESTRANTE' AND c.id_palestrante = %s
        ORDER BY c.data_emissao DESC
    """, (id_palestrante,))

    return templates.TemplateResponse(
        request=request,
        name="palestrante/painel.html",
        context={
            "user": user,
            "atividades": minhas_atividades,
            "certificados": meus_certificados,
            "msg": msg,
            "tipo": tipo
        }
    )


# ====================================================================
# PERFIL DO PALESTRANTE (VISUALIZAÇÃO E EDIÇÃO)
# ====================================================================

@router.get("/perfil", response_class=HTMLResponse)
async def ver_perfil_palestrante(request: Request, msg: str = None, tipo: str = "info", user: dict = Depends(verificar_palestrante)):
    dados_pal = await fetch_one(
        "SELECT id_palestrante, cpf, nome, email, telefone, curriculo FROM palestrante WHERE id_palestrante = %s",
        (user["id"],)
    )
    return templates.TemplateResponse(
        request=request,
        name="palestrante/perfil.html",
        context={"user": user, "palestrante": dados_pal, "msg": msg, "tipo": tipo}
    )


@router.post("/perfil")
async def atualizar_perfil_palestrante(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    telefone: Optional[str] = Form(None),
    curriculo: Optional[str] = Form(None),
    senha: Optional[str] = Form(None),
    user: dict = Depends(verificar_palestrante)
):
    id_pal = user["id"]
    nome_limpo = nome.strip()
    email_limpo = email.strip().lower()

    try:
        if senha and len(senha.strip()) >= 6:
            senha_hash = hash_senha(senha.strip())
            await execute_query("""
                UPDATE palestrante 
                SET nome = %s, email = %s, telefone = %s, curriculo = %s, senha_hash = %s
                WHERE id_palestrante = %s
            """, (nome_limpo, email_limpo, telefone, curriculo, senha_hash, id_pal))
        else:
            await execute_query("""
                UPDATE palestrante 
                SET nome = %s, email = %s, telefone = %s, curriculo = %s
                WHERE id_palestrante = %s
            """, (nome_limpo, email_limpo, telefone, curriculo, id_pal))

        token_payload = {
            "id": id_pal,
            "nome": nome_limpo,
            "email": email_limpo,
            "perfil": "PALESTRANTE"
        }
        novo_jwt = criar_token(token_payload)
        resp = RedirectResponse(url="/palestrante/perfil?msg=Dados+do+palestrante+atualizados+com+sucesso!&tipo=success", status_code=status.HTTP_303_SEE_OTHER)
        resp.set_cookie(key=COOKIE_NAME, value=novo_jwt, httponly=True, max_age=86400, samesite="lax")
        return resp

    except IntegrityError as e:
        if e.args[0] == 1062:
            return RedirectResponse(
                url="/palestrante/perfil?msg=ERRO:+Ja+existe+outro+palestrante+cadastrado+com+este+E-mail.&tipo=danger",
                status_code=status.HTTP_303_SEE_OTHER
            )
        return RedirectResponse(
            url=f"/palestrante/perfil?msg=Erro+ao+atualizar:+{e}&tipo=danger",
            status_code=status.HTTP_303_SEE_OTHER
        )
