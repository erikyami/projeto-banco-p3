from typing import Optional
from fastapi import APIRouter, Request, status, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import fetch_all, fetch_one
from auth import require_auth

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
