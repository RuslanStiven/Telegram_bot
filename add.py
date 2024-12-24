import asyncio
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException
from aiogram.filters.command import Command
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from pydantic import BaseModel
import uvicorn
import httpx
from models import User, MessageModals
from database import async_engine, SessionLocal
from bot_api import token_api
import re
from sqlalchemy.future import select
import logging
from aiogram import Bot, Dispatcher, types

url = "http://127.0.0.1:8080"
class MessageSchemaBot(BaseModel):
    content: str
    from_user_id: Optional[int] = None
    save_to_db: Optional[bool] = False


class MessageSchema(BaseModel):
    content: str
    sender_id: int
    from_user_id: int




async def add_user(telegram_id, username, name, session: AsyncSession):
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    current_time = datetime.now()

    if not user:
        new_user = User(
            telegram_id=telegram_id,
            username=username,
            name=name,
            last_start_time=current_time
        )
        session.add(new_user)
    else:
        user.last_start_time = current_time

    try:
        print("Попытка коммита")
        await session.commit()
        print("Коммит успешно завершен")
    except Exception as e:
        await session.rollback()
        print(f"Ошибка базы данных: {e}")
        raise

    return f"Привет, {name}! Ты успешно зарегистрирован." if not user else f"Добро пожаловать снова, {name}!"

async def send_to_external_address(address: str, content: str):
    async with httpx.AsyncClient() as client:
        try:

            response = await client.post(address, json={"message": content})
            if response.status_code == 200:
                logging.info(f"Сообщение успешно отправлено на внешний адрес {address}.")
            else:
                logging.error(f"Ошибка при отправке сообщения на внешний адрес {address}: {response.status_code}")
        except httpx.RequestError as e:
            logging.error(f"Ошибка запроса при отправке на {address}: {e}")


def is_valid_url(url: str) -> bool:
    regex = r"^(http|https)://"
    return bool(re.match(regex, url))

async def add_message(db: AsyncSession, content: str, address: str, sender_id: int):
    logging.info(f"Попытка добавления сообщения в БД: sender_id={sender_id}, content={content}")
    try:
        result = await db.execute(select(User).filter_by(telegram_id=sender_id))
        user = result.scalar_one_or_none()

        if not user:
            logging.error(f"Пользователь с ID {sender_id} не найден.")
            raise HTTPException(status_code=404, detail="Пользователь не найден.")

        message = MessageModals(sender_id=sender_id, content=content)
        logging.info(f"Перед добавлением сообщения в БД: content={content}")
        db.add(message)
        await db.commit()
        logging.info(f"Сообщение успешно добавлено в БД: {content}")
    except Exception as e:
        await db.rollback()
        logging.error(f"Ошибка при добавлении сообщения: {e}")
        raise HTTPException(status_code=500, detail="Не удалось сохранить сообщение.")




async def send_message_to_api(content: str, from_user_id: int):
    url = "http://127.0.0.1:8080/user_send"
    payload = {
        "content": content,
        "from_user_id": from_user_id
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
        if response.status_code == 200:
            print("Сообщение успешно отправлено в API!")
            return response.json()
        else:
            print(f"Ошибка: {response.status_code}")
            return None