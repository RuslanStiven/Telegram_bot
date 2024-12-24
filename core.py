import logging
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from models import User, MessageModals
from database import async_engine
from sqlalchemy.orm import sessionmaker


async_session_factory = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session

async def add_user(telegram_id, username, name, last_start_time=None):
    async with async_session_factory() as session:
        stmt = insert(User).values(
            telegram_id=telegram_id,
            username=username,
            name=name,
            last_start_time=last_start_time
        )
        await session.execute(stmt)
        await session.commit()


async def user_send(content: str, sender_id: int, db: AsyncSession):
    logging.info(f"Попытка сохранить сообщение: {content}, от пользователя {sender_id}")
    db_message = MessageModals(content=content, sender_id=sender_id)
    db.add(db_message)

    try:
        await db.commit()
        logging.info(f"Сообщение успешно сохранено: {content}")
    except Exception as e:
        logging.error(f"Ошибка сохранения сообщения: {e}")
        await db.rollback()
        raise

async def create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(User.metadata.drop_all)
        await conn.run_sync(User.metadata.create_all)
