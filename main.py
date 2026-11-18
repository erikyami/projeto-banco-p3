from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.exceptions import HTTPException

from database import init_db_pool, close_db_pool
from routers.auth_routes import router as auth_router
from routers.public_routes import router as public_router
from routers.staff_routes import router as staff_router
from routers.participante_routes import router as participante_router
from routers.palestrante_routes import router as palestrante_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialização do Pool de Conexões assíncrono (aiomysql)
    await init_db_pool()
    yield
    # Encerramento gracioso do Pool
    await close_db_pool()


app = FastAPI(
    title="Sistema de Gestão de Eventos Acadêmicos - BICT/UFMA",
    description="Sistema completo com Raw SQL (aiomysql), MySQL/MariaDB e FastAPI",
    lifespan=lifespan
)


# Tratador para redirecionar usuários não autenticados direto para a tela de login
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code in (302, 303, 307) and "Location" in exc.headers:
        return RedirectResponse(url=exc.headers["Location"], status_code=exc.status_code)
    # Comportamento padrão para outros erros
    from fastapi.exception_handlers import http_exception_handler
    return await http_exception_handler(request, exc)


# Registro de Rotas Modulares
app.include_router(public_router)
app.include_router(auth_router)
app.include_router(staff_router)
app.include_router(participante_router)
app.include_router(palestrante_router)
