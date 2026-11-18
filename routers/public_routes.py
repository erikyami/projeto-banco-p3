from typing import Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import fetch_all, fetch_one
from auth import get_current_user

router = APIRouter(tags=["Público"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, msg: Optional[str] = None, tipo: Optional[str] = "info"):
    user = get_current_user(request)
    
    # Próximos eventos
    eventos = await fetch_all("""
        SELECT e.*, COUNT(a.id_atividade) AS total_atividades
        FROM evento e
        LEFT JOIN atividade a ON e.id_evento = a.id_evento
        WHERE e.status = 'ATIVO'
        GROUP BY e.id_evento
        ORDER BY e.data_inicio ASC
        LIMIT 6
    """)

    # Estatísticas públicas
    tot_eventos = await fetch_one("SELECT COUNT(*) AS total FROM evento WHERE status = 'ATIVO'")
    tot_atividades = await fetch_one("SELECT COUNT(*) AS total FROM atividade")
    tot_certificados = await fetch_one("SELECT COUNT(*) AS total FROM certificado WHERE status = 'VALIDO'")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user": user,
            "eventos": eventos,
            "tot_eventos": tot_eventos["total"] if tot_eventos else 0,
            "tot_atividades": tot_atividades["total"] if tot_atividades else 0,
            "tot_certificados": tot_certificados["total"] if tot_certificados else 0,
            "msg": msg,
            "tipo": tipo
        }
    )


@router.get("/sobre", response_class=HTMLResponse)
async def pagina_sobre(request: Request):
    """
    Item 1 Obrigatório:
    Página 'Sobre' exibindo obrigatoriamente e exatamente o texto definido nas especificações.
    """
    user = get_current_user(request)
    texto_obrigatorio = (
        "Trabalho acadêmico da Universidade Federal do Maranhão do curso BICT, disciplina Banco de Dados. "
        "Participantes: Francisco Erik da Silva, Joao Elivaldo Barros Moraes, Jose Diomar Machado Costa. "
        "Professor da disciplina: CLAUDIO MANOEL PEREIRA AROUCHA."
    )
    return templates.TemplateResponse(
        request=request,
        name="sobre.html",
        context={
            "user": user,
            "texto_obrigatorio": texto_obrigatorio
        }
    )


@router.get("/verificar", response_class=HTMLResponse)
async def verificar_certificado_publico(request: Request, codigo: Optional[str] = Query(None)):
    """
    Item 5 Obrigatório:
    Verificação Pública onde qualquer pessoa insere o código do certificado e verifica se é válido,
    exibindo os dados do participante, evento e carga horária (via JOINs no SQL).
    """
    user = get_current_user(request)
    certificado_encontrado = None
    erro_busca = None

    if codigo:
        codigo_formatado = codigo.strip().upper()
        query = """
            SELECT 
                c.id_certificado,
                c.tipo_destinatario,
                c.codigo_validacao,
                c.status,
                c.data_emissao,
                c.carga_horaria,
                COALESCE(p.nome, pal.nome) AS participante_nome,
                COALESCE(p.cpf, pal.cpf) AS participante_cpf,
                COALESCE(p.email, pal.email) AS participante_email,
                COALESCE(a.nome, a_pal.nome) AS atividade_nome,
                COALESCE(a.tipo, a_pal.tipo) AS atividade_tipo,
                COALESCE(e.nome, e_pal.nome) AS evento_nome,
                COALESCE(e.local, e_pal.local) AS evento_local,
                COALESCE(e.data_inicio, e_pal.data_inicio) AS data_inicio,
                COALESCE(e.data_fim, e_pal.data_fim) AS data_fim
            FROM certificado c
            LEFT JOIN participacao_atividade pa ON c.id_participacao = pa.id_participacao
            LEFT JOIN inscricao i ON pa.id_inscricao = i.id_inscricao
            LEFT JOIN participante p ON i.id_participante = p.id_participante
            LEFT JOIN atividade a ON pa.id_atividade = a.id_atividade
            LEFT JOIN evento e ON a.id_evento = e.id_evento
            LEFT JOIN palestrante pal ON c.id_palestrante = pal.id_palestrante
            LEFT JOIN atividade a_pal ON c.id_atividade = a_pal.id_atividade
            LEFT JOIN evento e_pal ON a_pal.id_evento = e_pal.id_evento
            WHERE UPPER(c.codigo_validacao) = %s
        """
        resultado = await fetch_one(query, (codigo_formatado,))

        if not resultado:
            erro_busca = "Certificado Inválido ou Não Encontrado. Verifique o código digitado e tente novamente."
        elif resultado["status"] == "REVOGADO":
            erro_busca = f"Atenção: O certificado com código {codigo_formatado} foi REVOGADO pela comissão organizadora e perdeu sua validade oficial."
        else:
            certificado_encontrado = resultado

    return templates.TemplateResponse(
        request=request,
        name="verificar_certificado.html",
        context={
            "user": user,
            "codigo": codigo,
            "certificado": certificado_encontrado,
            "erro_busca": erro_busca
        }
    )
