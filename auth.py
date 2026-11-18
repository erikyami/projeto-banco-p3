import os
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "bict_ufma_banco_de_dados_2026_secret_key")
JWT_ALGORITHM = "HS256"
COOKIE_NAME = "certifica_session"


def hash_senha(senha: str) -> str:
    """Gera hash SHA-256 seguro para armazenamento de senhas sem ORM."""
    return hashlib.sha256(senha.strip().encode("utf-8")).hexdigest()


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Verifica correspondência do hash da senha."""
    return hash_senha(senha) == senha_hash


def criar_token(dados: dict, expires_hours: int = 24) -> str:
    """Gera token JWT contendo payload do usuário autenticado."""
    payload = dados.copy()
    exp = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    payload["exp"] = exp
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decodificar_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodifica e valida assinatura e expiração do JWT."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Recupera dados do usuário logado a partir do cookie da sessão."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return decodificar_token(token)


def require_auth(request: Request, allowed_roles: Optional[list] = None) -> Optional[Dict[str, Any]]:
    """
    Verifica se o usuário está logado e possui perfil autorizado.
    Retorna os dados do usuário ou levanta redirecionamento para o login.
    """
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login?msg=Acesso+restrito.+Por+favor,+faca+login.&tipo=warning"}
        )
    
    if allowed_roles and user.get("perfil") not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login?msg=Acesso+negado+para+o+seu+perfil.&tipo=danger"}
        )
    
    return user
