from fastapi import APIRouter, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pymysql.err import IntegrityError

from database import fetch_one, execute_query
from auth import hash_senha, verificar_senha, criar_token, COOKIE_NAME, get_current_user

router = APIRouter(tags=["Autenticação"])
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def tela_login(request: Request, msg: str = None, tipo: str = "info", perfil: str = "STAFF"):
    current_user = get_current_user(request)
    if current_user:
        # Se já está logado, redireciona para a área correspondente
        if current_user["perfil"] in ("STAFF", "ADMIN"):
            return RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        elif current_user["perfil"] == "PARTICIPANTE":
            return RedirectResponse(url="/participante/painel", status_code=status.HTTP_303_SEE_OTHER)
        elif current_user["perfil"] == "PALESTRANTE":
            return RedirectResponse(url="/palestrante/painel", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"msg": msg, "tipo": tipo, "perfil_selecionado": perfil, "user": None}
    )


@router.post("/login")
async def processar_login(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    perfil: str = Form(...)
):
    email_limpo = email.strip().lower()
    perfil_limpo = perfil.strip().upper()

    user_data = None

    if perfil_limpo == "STAFF":
        user_data = await fetch_one(
            "SELECT id_usuario AS id, nome, email, senha_hash, perfil, status FROM usuario WHERE email = %s",
            (email_limpo,)
        )
        if user_data:
            if user_data["status"] == "PENDENTE":
                return RedirectResponse(
                    url="/login?msg=Seu+cadastro+de+Staff+esta+PENDENTE+de+aprovacao+por+um+Administrador.&tipo=warning&perfil=STAFF",
                    status_code=status.HTTP_303_SEE_OTHER
                )
            elif user_data["status"] != "ATIVO":
                return RedirectResponse(
                    url="/login?msg=Usuario+da+equipe+inativo.+Contate+a+administracao.&tipo=danger&perfil=STAFF",
                    status_code=status.HTTP_303_SEE_OTHER
                )

    elif perfil_limpo == "PALESTRANTE":
        user_data = await fetch_one(
            "SELECT id_palestrante AS id, nome, email, senha_hash FROM palestrante WHERE email = %s",
            (email_limpo,)
        )
        if user_data:
            user_data["perfil"] = "PALESTRANTE"

    elif perfil_limpo == "PARTICIPANTE":
        user_data = await fetch_one(
            "SELECT id_participante AS id, nome, email, senha_hash FROM participante WHERE email = %s",
            (email_limpo,)
        )
        if user_data:
            user_data["perfil"] = "PARTICIPANTE"

    if not user_data or not verificar_senha(senha, user_data["senha_hash"]):
        return RedirectResponse(
            url=f"/login?msg=E-mail+ou+senha+incorretos+para+o+perfil+selecionado.&tipo=danger&perfil={perfil_limpo}",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # Autenticação bem-sucedida -> Criação do JWT
    token_payload = {
        "id": user_data["id"],
        "nome": user_data["nome"],
        "email": user_data["email"],
        "perfil": user_data["perfil"]
    }
    jwt_token = criar_token(token_payload)

    # Determinar destino
    if user_data["perfil"] in ("STAFF", "ADMIN", "APOIO"):
        destino = "/admin/dashboard"
    elif user_data["perfil"] == "PARTICIPANTE":
        destino = "/participante/painel"
    else:
        destino = "/palestrante/painel"

    response = RedirectResponse(url=destino, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=COOKIE_NAME,
        value=jwt_token,
        httponly=True,
        max_age=86400,
        samesite="lax"
    )
    return response


@router.get("/cadastro", response_class=HTMLResponse)
async def tela_cadastro(request: Request, msg: str = None, tipo: str = "info", perfil: str = "PARTICIPANTE"):
    return templates.TemplateResponse(
        request=request,
        name="cadastro.html",
        context={"msg": msg, "tipo": tipo, "perfil_selecionado": perfil.upper(), "user": get_current_user(request)}
    )


@router.post("/cadastro")
async def processar_cadastro(
    request: Request,
    tipo_cadastro: str = Form("PARTICIPANTE"),
    nome: str = Form(...),
    cpf: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    telefone: str = Form(None),
    curriculo: str = Form(None)
):
    tipo_limpo = tipo_cadastro.strip().upper()
    cpf_limpo = "".join(filter(str.isdigit, cpf))
    if len(cpf_limpo) != 11:
        return RedirectResponse(
            url=f"/cadastro?msg=CPF+deve+conter+exatamente+11+digitos.&tipo=danger&perfil={tipo_limpo}",
            status_code=status.HTTP_303_SEE_OTHER
        )

    senha_hash = hash_senha(senha)
    email_limpo = email.strip().lower()
    nome_limpo = nome.strip()

    try:
        if tipo_limpo == "PARTICIPANTE":
            query = """
                INSERT INTO participante (nome, cpf, email, senha_hash, telefone)
                VALUES (%s, %s, %s, %s, %s)
            """
            await execute_query(query, (nome_limpo, cpf_limpo, email_limpo, senha_hash, telefone))
            return RedirectResponse(
                url="/login?msg=Cadastro+de+Participante+realizado+com+sucesso!+Faca+seu+login.&tipo=success&perfil=PARTICIPANTE",
                status_code=status.HTTP_303_SEE_OTHER
            )

        elif tipo_limpo == "PALESTRANTE":
            query = """
                INSERT INTO palestrante (nome, cpf, email, senha_hash, telefone, curriculo)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            await execute_query(query, (nome_limpo, cpf_limpo, email_limpo, senha_hash, telefone, curriculo))
            return RedirectResponse(
                url="/login?msg=Cadastro+de+Palestrante+realizado+com+sucesso!+Faca+seu+login.&tipo=success&perfil=PALESTRANTE",
                status_code=status.HTTP_303_SEE_OTHER
            )

        elif tipo_limpo == "STAFF":
            # Membros do staff cadastrados publicamente entram como PENDENTE de aprovação
            query = """
                INSERT INTO usuario (nome, cpf, email, senha_hash, perfil, status)
                VALUES (%s, %s, %s, %s, 'APOIO', 'PENDENTE')
            """
            await execute_query(query, (nome_limpo, cpf_limpo, email_limpo, senha_hash))
            return RedirectResponse(
                url="/login?msg=Solicitacao+de+cadastro+enviada!+Aguarde+a+aprovacao+de+um+Administrador+para+acessar.&tipo=info&perfil=STAFF",
                status_code=status.HTTP_303_SEE_OTHER
            )

        else:
            return RedirectResponse(
                url="/cadastro?msg=Perfil+de+cadastro+invalido.&tipo=danger",
                status_code=status.HTTP_303_SEE_OTHER
            )

    except IntegrityError as e:
        if e.args[0] == 1062:
            return RedirectResponse(
                url=f"/cadastro?msg=ERRO:+Ja+existe+uma+conta+com+este+CPF+ou+E-mail.&tipo=danger&perfil={tipo_limpo}",
                status_code=status.HTTP_303_SEE_OTHER
            )
        return RedirectResponse(
            url=f"/cadastro?msg=Erro+ao+cadastrar:+{e}&tipo=danger&perfil={tipo_limpo}",
            status_code=status.HTTP_303_SEE_OTHER
        )


@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(
        url="/login?msg=Voce+saiu+do+sistema+com+sucesso.&tipo=info",
        status_code=status.HTTP_303_SEE_OTHER
    )
    response.delete_cookie(COOKIE_NAME)
    return response
