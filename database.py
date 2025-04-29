# app/database.py
import aiomysql
from config import settings

class Database:
    pool = None

    @classmethod
    async def connect(cls):
        if cls.pool is None:
            cls.pool = await aiomysql.create_pool(
                host=settings.db_host,
                port=settings.db_port,
                user=settings.db_user,
                password=settings.db_password,
                db=settings.db_name,
                autocommit=True,
                minsize=1,
                maxsize=10
            )
        return cls.pool

    @classmethod
    async def close(cls):
        if cls.pool:
            cls.pool.close()
            await cls.pool.wait_closed()
