import os
import asyncio
from typing import Optional, List, Dict, Any
import aiomysql

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "eventos_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "eventos_pass")
DB_NAME = os.getenv("DB_NAME", "eventos_db")

pool: Optional[aiomysql.Pool] = None


async def init_db_pool(retries: int = 15, delay: int = 2) -> aiomysql.Pool:
    global pool
    for attempt in range(1, retries + 1):
        try:
            print(f"[DB] Tentando conectar ao MariaDB/MySQL ({DB_HOST}:{DB_PORT}/{DB_NAME}) - Tentativa {attempt}/{retries}...")
            pool = await aiomysql.create_pool(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                db=DB_NAME,
                autocommit=True,
                cursorclass=aiomysql.DictCursor,
                minsize=2,
                maxsize=15
            )
            print("[DB] Pool de conexões MySQL/MariaDB criado com sucesso!")
            return pool
        except Exception as e:
            print(f"[DB] Falha na conexão: {e}. Aguardando {delay}s...")
            await asyncio.sleep(delay)
    raise RuntimeError("Não foi possível conectar ao banco de dados após várias tentativas.")


async def close_db_pool():
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
        print("[DB] Pool de conexões fechado.")


async def execute_query(query: str, params: tuple = None) -> int:
    """Executa queries INSERT, UPDATE, DELETE em SQL puro e retorna lastrowid ou rowcount."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(query, params or ())
            return cursor.lastrowid or cursor.rowcount


async def fetch_all(query: str, params: tuple = None) -> List[Dict[str, Any]]:
    """Executa SELECT puro e retorna todas as linhas como dicionários."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(query, params or ())
            return await cursor.fetchall()


async def fetch_one(query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
    """Executa SELECT puro e retorna uma única linha como dicionário."""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(query, params or ())
            return await cursor.fetchone()
