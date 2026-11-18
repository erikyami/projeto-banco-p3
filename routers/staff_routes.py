import uuid
from datetime import date
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Request, Form, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pymysql.err import IntegrityError

from database import fetch_all, fetch_one, execute_query
from auth import require_auth, hash_senha

router = APIRouter(prefix="/admin", tags=["Administração / Staff"])
templates = Jinja2Templates(directory="templates")


def verificar_staff(request: Request):
    """Garante que apenas membros do Staff ou Admin acessem a área."""
    return require_auth(request, allowed_roles=["STAFF", "ADMIN", "APOIO"])


# ====================================================================
# DASHBOARD DO STAFF
# ====================================================================

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_staff(request: Request, user: dict = Depends(verificar_staff)):
    totais = {
        "eventos": (await fetch_one("SELECT COUNT(*) AS total FROM evento"))["total"],
        "atividades": (await fetch_one("SELECT COUNT(*) AS total FROM atividade"))["total"],
        "participantes": (await fetch_one("SELECT COUNT(*) AS total FROM participante"))["total"],
        "palestrantes": (await fetch_one("SELECT COUNT(*) AS total FROM palestrante"))["total"],
        "inscricoes": (await fetch_one("SELECT COUNT(*) AS total FROM inscricao"))["total"],
        "presencas": (await fetch_one("SELECT COUNT(*) AS total FROM presenca WHERE presente = 1"))["total"],
        "certificados": (await fetch_one("SELECT COUNT(*) AS total FROM certificado WHERE status = 'VALIDO'"))["total"]
    }

    ultimos_eventos = await fetch_all("SELECT * FROM evento ORDER BY id_evento DESC LIMIT 5")
    ultimas_atividades = await fetch_all("""
        SELECT a.*, e.nome AS evento_nome
        FROM atividade a
        INNER JOIN evento e ON a.id_evento = e.id_evento
        ORDER BY a.id_atividade DESC LIMIT 5
    """)

    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context={"user": user, "totais": totais, "eventos": ultimos_eventos, "atividades": ultimas_atividades}
    )


# ====================================================================
# 1. CRUD DE STAFF (APOIO / USUÁRIO)
# ====================================================================

@router.get("/staff", response_class=HTMLResponse)
async def listar_staff(request: Request, msg: str = None, tipo: str = "info", user: dict = Depends(verificar_staff)):
    equipe = await fetch_all("SELECT id_usuario, cpf, nome, email, perfil, status, data_cadastro FROM usuario ORDER BY id_usuario DESC")
    return templates.TemplateResponse(
        request=request,
        name="admin/staff.html",
        context={"user": user, "equipe": equipe, "msg": msg, "tipo": tipo}
    )


@router.post("/staff")
async def criar_staff(
    request: Request,
    nome: str = Form(...),
    cpf: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    perfil: str = Form("APOIO"),
    user: dict = Depends(verificar_staff)
):
    cpf_limpo = "".join(filter(str.isdigit, cpf))
    senha_hash = hash_senha(senha)

    query = """
        INSERT INTO usuario (nome, cpf, email, senha_hash, perfil, status)
        VALUES (%s, %s, %s, %s, %s, 'ATIVO')
    """
    try:
        await execute_query(query, (nome.strip(), cpf_limpo, email.strip().lower(), senha_hash, perfil))
        return RedirectResponse(
            url="/admin/staff?msg=Membro+da+equipe+de+apoio+cadastrado+com+sucesso!&tipo=success",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except IntegrityError as e:
        return RedirectResponse(
            url=f"/admin/staff?msg=ERRO:+CPF+ou+E-mail+ja+cadastrados+para+outro+usuario.&tipo=danger",
            status_code=status.HTTP_303_SEE_OTHER
        )


@router.post("/staff/{id_usuario}/status")
async def alternar_status_staff(
    id_usuario: int,
    novo_status: str = Form(...),
    user: dict = Depends(verificar_staff)
):
    await execute_query("UPDATE usuario SET status = %s WHERE id_usuario = %s", (novo_status, id_usuario))
    return RedirectResponse(
        url=f"/admin/staff?msg=Status+do+usuario+alterado+para+{novo_status}!&tipo=info",
        status_code=status.HTTP_303_SEE_OTHER
    )


# ====================================================================
# 2. CRUD DE EVENTOS (CRIAR, EDITAR, LISTAR E CANCELAR)
# ====================================================================

@router.get("/eventos", response_class=HTMLResponse)
async def listar_eventos_admin(request: Request, msg: str = None, tipo: str = "info", user: dict = Depends(verificar_staff)):
    eventos = await fetch_all("""
        SELECT e.*, COUNT(a.id_atividade) AS total_atividades,
               COUNT(DISTINCT i.id_inscricao) AS total_inscritos
        FROM evento e
        LEFT JOIN atividade a ON e.id_evento = a.id_evento
        LEFT JOIN inscricao i ON e.id_evento = i.id_evento
        GROUP BY e.id_evento
        ORDER BY e.data_inicio DESC
    """)
    return templates.TemplateResponse(
        request=request,
        name="admin/eventos.html",
        context={"user": user, "eventos": eventos, "msg": msg, "tipo": tipo}
    )


@router.post("/eventos")
async def criar_evento(
    codigo: str = Form(...),
    nome: str = Form(...),
    descricao: str = Form(...),
    data_inicio: str = Form(...),
    data_fim: str = Form(...),
    local: str = Form(...),
    user: dict = Depends(verificar_staff)
):
    query = """
        INSERT INTO evento (codigo, nome, descricao, data_inicio, data_fim, local, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'ATIVO')
    """
    try:
        await execute_query(query, (codigo.strip().upper(), nome.strip(), descricao.strip(), data_inicio, data_fim, local.strip()))
        return RedirectResponse(
            url="/admin/eventos?msg=Evento+criado+com+sucesso!&tipo=success",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except IntegrityError:
        return RedirectResponse(
            url="/admin/eventos?msg=ERRO:+Ja+existe+um+evento+com+este+codigo.&tipo=danger",
            status_code=status.HTTP_303_SEE_OTHER
        )


@router.post("/eventos/{id_evento}/editar")
async def editar_evento(
    id_evento: int,
    nome: str = Form(...),
    descricao: str = Form(...),
    data_inicio: str = Form(...),
    data_fim: str = Form(...),
    local: str = Form(...),
    status_evento: str = Form(...),
    user: dict = Depends(verificar_staff)
):
    query = """
        UPDATE evento
        SET nome = %s, descricao = %s, data_inicio = %s, data_fim = %s, local = %s, status = %s
        WHERE id_evento = %s
    """
    await execute_query(query, (nome.strip(), descricao.strip(), data_inicio, data_fim, local.strip(), status_evento, id_evento))
    return RedirectResponse(
        url="/admin/eventos?msg=Evento+atualizado+com+sucesso!&tipo=success",
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/eventos/{id_evento}/cancelar")
async def cancelar_evento(id_evento: int, user: dict = Depends(verificar_staff)):
    await execute_query("UPDATE evento SET status = 'CANCELADO' WHERE id_evento = %s", (id_evento,))
    return RedirectResponse(
        url="/admin/eventos?msg=Evento+cancelado!&tipo=warning",
        status_code=status.HTTP_303_SEE_OTHER
    )


# ====================================================================
# 3. CRUD DE ATIVIDADES (CONTEMPLANDO REQUISITOS DE CERTIFICADO)
# ====================================================================

@router.get("/atividades", response_class=HTMLResponse)
async def listar_atividades_admin(request: Request, msg: str = None, tipo: str = "info", user: dict = Depends(verificar_staff)):
    eventos = await fetch_all("SELECT id_evento, nome FROM evento WHERE status = 'ATIVO' ORDER BY nome")
    palestrantes = await fetch_all("SELECT id_palestrante, nome FROM palestrante ORDER BY nome")
    atividades = await fetch_all("""
        SELECT a.*, e.nome AS evento_nome,
               GROUP_CONCAT(p.nome SEPARATOR ', ') AS palestrantes,
               COUNT(DISTINCT pa.id_participacao) AS total_inscritos
        FROM atividade a
        INNER JOIN evento e ON a.id_evento = e.id_evento
        LEFT JOIN atividade_palestrante ap ON a.id_atividade = ap.id_atividade
        LEFT JOIN palestrante p ON ap.id_palestrante = p.id_palestrante
        LEFT JOIN participacao_atividade pa ON a.id_atividade = pa.id_atividade
        GROUP BY a.id_atividade
        ORDER BY a.data_atividade DESC, a.hora_inicio ASC
    """)
    return templates.TemplateResponse(
        request=request,
        name="admin/atividades.html",
        context={"user": user, "atividades": atividades, "eventos": eventos, "palestrantes": palestrantes, "msg": msg, "tipo": tipo}
    )


@router.post("/atividades")
async def criar_atividade(
    id_evento: int = Form(...),
    tipo: str = Form(...),
    nome: str = Form(...),
    descricao: str = Form(...),
    data_atividade: str = Form(...),
    data_fim: Optional[str] = Form(None),
    hora_inicio: str = Form(...),
    hora_fim: str = Form(...),
    carga_horaria: Decimal = Form(...),
    limite_vagas: int = Form(...),
    frequencia_minima: Decimal = Form(75.00),
    exige_conclusao: Optional[int] = Form(0),
    id_palestrante: Optional[int] = Form(None),
    user: dict = Depends(verificar_staff)
):
    data_fim_efetiva = data_fim if data_fim else data_atividade

    query = """
        INSERT INTO atividade (
            id_evento, tipo, nome, descricao, data_atividade, data_fim, hora_inicio, hora_fim,
            carga_horaria, limite_vagas, frequencia_minima, exige_conclusao, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'AGENDADA')
    """
    id_atividade = await execute_query(query, (
        id_evento, tipo.strip(), nome.strip(), descricao.strip(), data_atividade, data_fim_efetiva,
        hora_inicio, hora_fim, carga_horaria, limite_vagas, frequencia_minima, exige_conclusao
    ))

    if id_palestrante:
        await execute_query(
            "INSERT INTO atividade_palestrante (id_atividade, id_palestrante) VALUES (%s, %s)",
            (id_atividade, id_palestrante)
        )

    return RedirectResponse(
        url="/admin/atividades?msg=Atividade+cadastrada+com+sucesso!&tipo=success",
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/atividades/{id_atividade}/editar")
async def editar_atividade(
    id_atividade: int,
    nome: str = Form(...),
    tipo: str = Form(...),
    descricao: str = Form(...),
    data_atividade: str = Form(...),
    data_fim: Optional[str] = Form(None),
    hora_inicio: str = Form(...),
    hora_fim: str = Form(...),
    carga_horaria: Decimal = Form(...),
    limite_vagas: int = Form(...),
    frequencia_minima: Decimal = Form(...),
    exige_conclusao: Optional[int] = Form(0),
    status_atv: str = Form(...),
    user: dict = Depends(verificar_staff)
):
    data_fim_efetiva = data_fim if data_fim else data_atividade

    query = """
        UPDATE atividade
        SET nome = %s, tipo = %s, descricao = %s, data_atividade = %s, data_fim = %s, hora_inicio = %s,
            hora_fim = %s, carga_horaria = %s, limite_vagas = %s, frequencia_minima = %s,
            exige_conclusao = %s, status = %s
        WHERE id_atividade = %s
    """
    await execute_query(query, (
        nome.strip(), tipo.strip(), descricao.strip(), data_atividade, data_fim_efetiva, hora_inicio,
        hora_fim, carga_horaria, limite_vagas, frequencia_minima, exige_conclusao, status_atv, id_atividade
    ))
    return RedirectResponse(
        url="/admin/atividades?msg=Atividade+atualizada+com+sucesso!&tipo=success",
        status_code=status.HTTP_303_SEE_OTHER
    )


# ====================================================================
# 4. CRUD DE PARTICIPANTES E PALESTRANTES (GESTÃO E HISTÓRICO)
# ====================================================================

@router.get("/participantes", response_class=HTMLResponse)
async def listar_participantes_admin(request: Request, msg: str = None, tipo: str = "info", user: dict = Depends(verificar_staff)):
    participantes = await fetch_all("""
        SELECT p.*, COUNT(DISTINCT i.id_evento) AS total_eventos,
               COUNT(DISTINCT pa.id_atividade) AS total_atividades,
               COUNT(DISTINCT c.id_certificado) AS total_certificados
        FROM participante p
        LEFT JOIN inscricao i ON p.id_participante = i.id_participante
        LEFT JOIN participacao_atividade pa ON i.id_inscricao = pa.id_inscricao
        LEFT JOIN certificado c ON pa.id_participacao = c.id_participacao AND c.status = 'VALIDO'
        GROUP BY p.id_participante
        ORDER BY p.nome ASC
    """)
    return templates.TemplateResponse(
        request=request,
        name="admin/participantes.html",
        context={"user": user, "participantes": participantes, "msg": msg, "tipo": tipo}
    )


@router.get("/palestrantes", response_class=HTMLResponse)
async def listar_palestrantes_admin(request: Request, msg: str = None, tipo: str = "info", user: dict = Depends(verificar_staff)):
    palestrantes = await fetch_all("""
        SELECT p.*, COUNT(ap.id_atividade) AS total_atividades
        FROM palestrante p
        LEFT JOIN atividade_palestrante ap ON p.id_palestrante = ap.id_palestrante
        GROUP BY p.id_palestrante
        ORDER BY p.nome ASC
    """)
    return templates.TemplateResponse(
        request=request,
        name="admin/palestrantes.html",
        context={"user": user, "palestrantes": palestrantes, "msg": msg, "tipo": tipo}
    )


@router.post("/palestrantes")
async def criar_palestrante_admin(
    nome: str = Form(...),
    cpf: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    telefone: str = Form(None),
    curriculo: str = Form(...),
    user: dict = Depends(verificar_staff)
):
    cpf_limpo = "".join(filter(str.isdigit, cpf))
    senha_hash = hash_senha(senha)
    query = """
        INSERT INTO palestrante (nome, cpf, email, senha_hash, telefone, curriculo)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    try:
        await execute_query(query, (nome.strip(), cpf_limpo, email.strip().lower(), senha_hash, telefone, curriculo.strip()))
        return RedirectResponse(
            url="/admin/palestrantes?msg=Palestrante+cadastrado+com+sucesso!&tipo=success",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except IntegrityError:
        return RedirectResponse(
            url="/admin/palestrantes?msg=ERRO:+CPF+ou+E-mail+ja+cadastrados+para+outro+palestrante.&tipo=danger",
            status_code=status.HTTP_303_SEE_OTHER
        )


# ====================================================================
# 5. CONTROLE DE PRESENÇA MULTIDIAS (data_aula) COM VALIDAÇÃO DE INTERVALO
# ====================================================================

@router.get("/presencas", response_class=HTMLResponse)
async def tela_presencas(
    request: Request,
    id_atividade: Optional[int] = None,
    data_aula: Optional[str] = None,
    busca_participante: Optional[str] = None,
    msg: str = None,
    tipo: str = "info",
    user: dict = Depends(verificar_staff)
):
    atividades = await fetch_all("""
        SELECT a.id_atividade, a.nome, a.tipo, a.data_atividade, 
               COALESCE(a.data_fim, a.data_atividade) AS data_fim_efetiva,
               e.nome AS evento_nome
        FROM atividade a
        INNER JOIN evento e ON a.id_evento = e.id_evento
        WHERE e.status = 'ATIVO'
        ORDER BY a.nome
    """)

    inscritos = []
    atividade_selecionada_obj = None

    if id_atividade:
        for atv in atividades:
            if atv["id_atividade"] == id_atividade:
                atividade_selecionada_obj = atv
                break

        if not data_aula:
            data_filtro = str(atividade_selecionada_obj["data_atividade"]) if atividade_selecionada_obj else str(date.today())
        else:
            data_filtro = data_aula

        query = """
            SELECT 
                pa.id_participacao,
                p.id_participante,
                p.nome AS participante_nome,
                p.cpf,
                p.email,
                i.numero AS numero_inscricao,
                COALESCE(pr.presente, 0) AS presente,
                pr.id_presenca,
                pr.data_registro,
                pr.data_remocao,
                u_gerou.nome AS staff_gerou_nome,
                u_removeu.nome AS staff_removeu_nome
            FROM participacao_atividade pa
            INNER JOIN inscricao i ON pa.id_inscricao = i.id_inscricao
            INNER JOIN participante p ON i.id_participante = p.id_participante
            LEFT JOIN presenca pr ON pa.id_participacao = pr.id_participacao AND pr.data_aula = %s
            LEFT JOIN usuario u_gerou ON pr.id_usuario = u_gerou.id_usuario
            LEFT JOIN usuario u_removeu ON pr.id_usuario_remocao = u_removeu.id_usuario
            WHERE pa.id_atividade = %s AND pa.status = 'CONFIRMADA'
            ORDER BY p.nome ASC
        """
        inscritos = await fetch_all(query, (data_filtro, id_atividade))
    else:
        data_filtro = data_aula or str(date.today())

    # Pesquisa de todas as presenças de determinado participante (por nome ou CPF)
    resultado_busca_participante = []
    participante_pesquisado = None

    if busca_participante:
        termo = f"%{busca_participante.strip()}%"
        query_busca = """
            SELECT 
                p.id_participante,
                p.nome AS participante_nome,
                p.cpf,
                p.email,
                e.nome AS evento_nome,
                a.nome AS atividade_nome,
                a.tipo AS atividade_tipo,
                pr.id_presenca,
                pr.data_aula,
                pr.presente,
                pr.data_registro,
                pr.data_remocao,
                u_gerou.nome AS staff_gerou_nome,
                u_removeu.nome AS staff_removeu_nome
            FROM presenca pr
            INNER JOIN participacao_atividade pa ON pr.id_participacao = pa.id_participacao
            INNER JOIN inscricao i ON pa.id_inscricao = i.id_inscricao
            INNER JOIN participante p ON i.id_participante = p.id_participante
            INNER JOIN atividade a ON pa.id_atividade = a.id_atividade
            INNER JOIN evento e ON a.id_evento = e.id_evento
            LEFT JOIN usuario u_gerou ON pr.id_usuario = u_gerou.id_usuario
            LEFT JOIN usuario u_removeu ON pr.id_usuario_remocao = u_removeu.id_usuario
            WHERE p.nome LIKE %s OR p.cpf LIKE %s OR p.email LIKE %s
            ORDER BY p.nome, pr.data_aula DESC
        """
        resultado_busca_participante = await fetch_all(query_busca, (termo, termo, termo))

    # Histórico recente de auditoria (quem gerou ou removeu presenças)
    logs_auditoria = await fetch_all("""
        SELECT 
            lp.id_log,
            lp.acao,
            lp.data_aula,
            lp.data_hora,
            u.nome AS staff_nome,
            u.perfil AS staff_perfil,
            p.nome AS participante_nome,
            a.nome AS atividade_nome
        FROM log_presenca lp
        INNER JOIN usuario u ON lp.id_usuario = u.id_usuario
        INNER JOIN participacao_atividade pa ON lp.id_participacao = pa.id_participacao
        INNER JOIN inscricao i ON pa.id_inscricao = i.id_inscricao
        INNER JOIN participante p ON i.id_participante = p.id_participante
        INNER JOIN atividade a ON pa.id_atividade = a.id_atividade
        ORDER BY lp.data_hora DESC
        LIMIT 10
    """)

    return templates.TemplateResponse(
        request=request,
        name="admin/presencas.html",
        context={
            "user": user,
            "atividades": atividades,
            "id_atividade_selecionada": id_atividade,
            "atividade_selecionada_obj": atividade_selecionada_obj,
            "data_aula_selecionada": data_filtro,
            "inscritos": inscritos,
            "busca_participante": busca_participante,
            "resultado_busca_participante": resultado_busca_participante,
            "logs_auditoria": logs_auditoria,
            "msg": msg,
            "tipo": tipo
        }
    )


@router.post("/presencas")
async def registrar_presenca_multidias(
    id_atividade: int = Form(...),
    data_aula: str = Form(...),
    id_participacao: int = Form(...),
    presente: Optional[int] = Form(0),
    user: dict = Depends(verificar_staff)
):
    """
    Registra ou remove a presença com auditoria de quem gerou e quem removeu.
    """
    info_atividade = await fetch_one("""
        SELECT a.nome, a.data_atividade, COALESCE(a.data_fim, a.data_atividade) AS data_fim_efetiva,
               e.nome AS evento_nome
        FROM atividade a
        INNER JOIN evento e ON a.id_evento = e.id_evento
        WHERE a.id_atividade = %s
    """, (id_atividade,))

    if not info_atividade:
        return RedirectResponse(
            url="/admin/presencas?msg=Atividade+nao+encontrada.&tipo=danger",
            status_code=status.HTTP_303_SEE_OTHER
        )

    try:
        dt_aula = date.fromisoformat(data_aula)
    except ValueError:
        return RedirectResponse(
            url=f"/admin/presencas?id_atividade={id_atividade}&msg=Data+invalida.&tipo=danger",
            status_code=status.HTTP_303_SEE_OTHER
        )

    dt_inicio = info_atividade["data_atividade"]
    dt_fim = info_atividade["data_fim_efetiva"]

    if dt_inicio and dt_fim:
        if dt_aula < dt_inicio or dt_aula > dt_fim:
            return RedirectResponse(
                url=f"/admin/presencas?id_atividade={id_atividade}&data_aula={data_aula}&msg=BLOQUEADO:+A+presenca+so+pode+ser+registrada+no+intervalo+da+atividade+({dt_inicio.strftime('%d/%m/%Y')}+a+{dt_fim.strftime('%d/%m/%Y')}).&tipo=danger",
                status_code=status.HTTP_303_SEE_OTHER
            )

    id_usuario_staff = user["id"]

    if presente == 1:
        # GERAR PRESENÇA: registra id_usuario como quem gerou
        query = """
            INSERT INTO presenca (id_participacao, id_usuario, data_aula, presente, data_registro)
            VALUES (%s, %s, %s, 1, NOW())
            ON DUPLICATE KEY UPDATE
                presente = 1,
                id_usuario = VALUES(id_usuario),
                data_registro = NOW()
        """
        await execute_query(query, (id_participacao, id_usuario_staff, data_aula))
        
        # Registrar log de auditoria
        await execute_query("""
            INSERT INTO log_presenca (id_participacao, id_usuario, acao, data_aula, data_hora)
            VALUES (%s, %s, 'GERADA', %s, NOW())
        """, (id_participacao, id_usuario_staff, data_aula))
        
        msg = "Presenca+confirmada+com+sucesso!"
    else:
        # REMOVER PRESENÇA: marca presente = 0 e registra id_usuario_remocao
        query = """
            INSERT INTO presenca (id_participacao, id_usuario, id_usuario_remocao, data_aula, presente, data_registro, data_remocao)
            VALUES (%s, %s, %s, %s, 0, NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                presente = 0,
                id_usuario_remocao = %s,
                data_remocao = NOW()
        """
        await execute_query(query, (id_participacao, id_usuario_staff, id_usuario_staff, data_aula, id_usuario_staff))
        
        # Registrar log de auditoria
        await execute_query("""
            INSERT INTO log_presenca (id_participacao, id_usuario, acao, data_aula, data_hora)
            VALUES (%s, %s, 'REMOVIDA', %s, NOW())
        """, (id_participacao, id_usuario_staff, data_aula))
        
        msg = "Presenca+removida+(marcado+ausente)+com+sucesso!"

    return RedirectResponse(
        url=f"/admin/presencas?id_atividade={id_atividade}&data_aula={data_aula}&msg={msg}&tipo=success",
        status_code=status.HTTP_303_SEE_OTHER
    )


# ====================================================================
# 6. RELATÓRIOS CONSOLIDADOS
# ====================================================================

@router.get("/relatorios", response_class=HTMLResponse)
async def tela_relatorios(request: Request, user: dict = Depends(verificar_staff)):
    # 1. Total de inscritos por evento
    inscritos_por_evento = await fetch_all("""
        SELECT e.id_evento, e.codigo, e.nome AS evento_nome, e.status,
               COUNT(i.id_inscricao) AS total_inscritos,
               COUNT(DISTINCT pa.id_participacao) AS total_participacoes_atividades
        FROM evento e
        LEFT JOIN inscricao i ON e.id_evento = i.id_evento
        LEFT JOIN participacao_atividade pa ON i.id_inscricao = pa.id_inscricao
        GROUP BY e.id_evento
        ORDER BY total_inscritos DESC
    """)

    # 2. Frequência consolidada dos participantes por atividade
    frequencia_participantes = await fetch_all("""
        SELECT 
            p.nome AS participante_nome,
            p.cpf,
            e.nome AS evento_nome,
            a.nome AS atividade_nome,
            a.frequencia_minima,
            pa.id_participacao,
            COUNT(pr.id_presenca) AS total_dias_registrados,
            SUM(COALESCE(pr.presente, 0)) AS total_dias_presente,
            ROUND((SUM(COALESCE(pr.presente, 0)) / NULLIF(COUNT(pr.id_presenca), 0)) * 100, 2) AS percentual_frequencia,
            c.codigo_validacao,
            c.status AS status_certificado
        FROM participacao_atividade pa
        INNER JOIN inscricao i ON pa.id_inscricao = i.id_inscricao
        INNER JOIN participante p ON i.id_participante = p.id_participante
        INNER JOIN atividade a ON pa.id_atividade = a.id_atividade
        INNER JOIN evento e ON a.id_evento = e.id_evento
        LEFT JOIN presenca pr ON pa.id_participacao = pr.id_participacao
        LEFT JOIN certificado c ON pa.id_participacao = c.id_participacao
        GROUP BY pa.id_participacao
        ORDER BY a.nome, p.nome
    """)

    return templates.TemplateResponse(
        request=request,
        name="admin/relatorios.html",
        context={
            "user": user,
            "inscritos_por_evento": inscritos_por_evento,
            "frequencia_participantes": frequencia_participantes
        }
    )


# ====================================================================
# 7. GESTÃO E EMISSÃO DE CERTIFICADOS (PARTICIPANTE E PALESTRANTE)
# ====================================================================

@router.get("/certificados", response_class=HTMLResponse)
async def listar_certificados_admin(request: Request, msg: str = None, tipo: str = "info", user: dict = Depends(verificar_staff)):
    certificados = await fetch_all("""
        SELECT 
            c.id_certificado,
            c.tipo_destinatario,
            c.codigo_validacao,
            c.status,
            c.data_emissao,
            c.carga_horaria,
            COALESCE(p.nome, pal.nome) AS destinatario_nome,
            COALESCE(p.cpf, pal.cpf) AS destinatario_cpf,
            COALESCE(a.nome, a_pal.nome) AS atividade_nome,
            COALESCE(e.nome, e_pal.nome) AS evento_nome
        FROM certificado c
        LEFT JOIN participacao_atividade pa ON c.id_participacao = pa.id_participacao
        LEFT JOIN inscricao i ON pa.id_inscricao = i.id_inscricao
        LEFT JOIN participante p ON i.id_participante = p.id_participante
        LEFT JOIN atividade a ON pa.id_atividade = a.id_atividade
        LEFT JOIN evento e ON a.id_evento = e.id_evento
        LEFT JOIN palestrante pal ON c.id_palestrante = pal.id_palestrante
        LEFT JOIN atividade a_pal ON c.id_atividade = a_pal.id_atividade
        LEFT JOIN evento e_pal ON a_pal.id_evento = e_pal.id_evento
        ORDER BY c.data_emissao DESC
    """)

    # Candidatos Participantes elegíveis para emissão
    candidatos_emissao = await fetch_all("""
        SELECT 
            pa.id_participacao,
            p.nome AS participante_nome,
            p.cpf AS participante_cpf,
            a.nome AS atividade_nome,
            a.carga_horaria,
            a.frequencia_minima,
            COUNT(pr.id_presenca) AS total_aulas,
            SUM(COALESCE(pr.presente, 0)) AS presencas,
            ROUND((SUM(COALESCE(pr.presente, 0)) / NULLIF(COUNT(pr.id_presenca), 0)) * 100, 2) AS percentual_frequencia
        FROM participacao_atividade pa
        INNER JOIN inscricao i ON pa.id_inscricao = i.id_inscricao
        INNER JOIN participante p ON i.id_participante = p.id_participante
        INNER JOIN atividade a ON pa.id_atividade = a.id_atividade
        LEFT JOIN presenca pr ON pa.id_participacao = pr.id_participacao
        LEFT JOIN certificado c ON pa.id_participacao = c.id_participacao
        WHERE c.id_certificado IS NULL
        GROUP BY pa.id_participacao
        HAVING percentual_frequencia >= a.frequencia_minima
    """)

    # Candidatos Palestrantes vinculados a atividades sem certificado emitido
    palestrantes_aptos = await fetch_all("""
        SELECT 
            ap.id_atividade,
            ap.id_palestrante,
            pal.nome AS palestrante_nome,
            pal.cpf AS palestrante_cpf,
            a.nome AS atividade_nome,
            a.carga_horaria,
            e.nome AS evento_nome
        FROM atividade_palestrante ap
        INNER JOIN palestrante pal ON ap.id_palestrante = pal.id_palestrante
        INNER JOIN atividade a ON ap.id_atividade = a.id_atividade
        INNER JOIN evento e ON a.id_evento = e.id_evento
        LEFT JOIN certificado c ON c.tipo_destinatario = 'PALESTRANTE' 
                               AND c.id_palestrante = ap.id_palestrante 
                               AND c.id_atividade = ap.id_atividade
        WHERE c.id_certificado IS NULL
        ORDER BY pal.nome, a.nome
    """)

    return templates.TemplateResponse(
        request=request,
        name="admin/certificados.html",
        context={
            "user": user,
            "certificados": certificados,
            "candidatos_emissao": candidatos_emissao,
            "palestrantes_aptos": palestrantes_aptos,
            "msg": msg,
            "tipo": tipo
        }
    )


@router.post("/certificados/{id_certificado}/status")
async def alterar_status_certificado(
    id_certificado: int,
    novo_status: str = Form(...),
    user: dict = Depends(verificar_staff)
):
    await execute_query(
        "UPDATE certificado SET status = %s WHERE id_certificado = %s",
        (novo_status, id_certificado)
    )
    return RedirectResponse(
        url=f"/admin/certificados?msg=Status+do+certificado+atualizado+para+{novo_status}!&tipo=info",
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/certificados/emitir")
async def emitir_certificado_admin(
    id_participacao: int = Form(...),
    user: dict = Depends(verificar_staff)
):
    # Buscar carga horária da atividade
    dados = await fetch_one("""
        SELECT a.carga_horaria
        FROM participacao_atividade pa
        INNER JOIN atividade a ON pa.id_atividade = a.id_atividade
        WHERE pa.id_participacao = %s
    """, (id_participacao,))

    if not dados:
        return RedirectResponse(
            url="/admin/certificados?msg=Participacao+nao+encontrada.&tipo=danger",
            status_code=status.HTTP_303_SEE_OTHER
        )

    codigo_validacao = f"CERT-UFMA-2026-DISC-{uuid.uuid4().hex[:8].upper()}"

    query = """
        INSERT INTO certificado (tipo_destinatario, id_participacao, codigo_validacao, status, data_emissao, carga_horaria)
        VALUES ('PARTICIPANTE', %s, %s, 'VALIDO', NOW(), %s)
    """
    await execute_query(query, (id_participacao, codigo_validacao, dados["carga_horaria"]))

    return RedirectResponse(
        url=f"/admin/certificados?msg=Certificado+de+participante+emitido!+Codigo:+{codigo_validacao}&tipo=success",
        status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/certificados/emitir-palestrante")
async def emitir_certificado_palestrante_admin(
    id_palestrante: int = Form(...),
    id_atividade: int = Form(...),
    user: dict = Depends(verificar_staff)
):
    # Buscar dados da atividade
    dados = await fetch_one("""
        SELECT carga_horaria FROM atividade WHERE id_atividade = %s
    """, (id_atividade,))

    if not dados:
        return RedirectResponse(
            url="/admin/certificados?msg=Atividade+nao+encontrada.&tipo=danger",
            status_code=status.HTTP_303_SEE_OTHER
        )

    codigo_validacao = f"CERT-UFMA-2026-DOC-{uuid.uuid4().hex[:8].upper()}"

    query = """
        INSERT INTO certificado (tipo_destinatario, id_palestrante, id_atividade, codigo_validacao, status, data_emissao, carga_horaria)
        VALUES ('PALESTRANTE', %s, %s, %s, 'VALIDO', NOW(), %s)
    """
    try:
        await execute_query(query, (id_palestrante, id_atividade, codigo_validacao, dados["carga_horaria"]))
        return RedirectResponse(
            url=f"/admin/certificados?msg=Certificado+do+palestrante+emitido+com+sucesso!+Codigo:+{codigo_validacao}&tipo=success",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except IntegrityError:
        return RedirectResponse(
            url="/admin/certificados?msg=Ja+existe+certificado+emitido+para+este+palestrante+nesta+atividade.&tipo=warning",
            status_code=status.HTTP_303_SEE_OTHER
        )
