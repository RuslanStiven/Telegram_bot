import asyncio
from typing import Optional
from datetime import datetime
from add import is_valid_url, send_to_external_address, add_message, add_user
from add import MessageSchema, MessageSchemaBot
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

logging.basicConfig(level=logging.INFO)

bot = Bot(token=token_api)
dp = Dispatcher()

app = FastAPI()
url = "http://127.0.0.1:8080"

async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        yield session

async def send_message_to_all(db: AsyncSession, content: str):
    stmt = select(User.telegram_id)
    result = await db.execute(stmt)
    user_ids = [row[0] for row in result.fetchall()]

    tasks = [bot.send_message(user_id, content) for user_id in user_ids]
    await asyncio.gather(*tasks)

@dp.message(Command("start"))
async def start_command(message: types.Message, **kwargs):
    async with async_session_factory() as session:
        telegram_id = message.from_user.id
        username = message.from_user.username
        name = message.from_user.full_name

        response = await add_user(telegram_id, username, name, session)
        await message.answer(response)


@dp.message()
async def handle_message(message: types.Message):
    logging.info(f"Получено сообщение: {message.text} от пользователя {message.from_user.id}")
    content = message.text.strip()

    logging.info(f"Контент после очистки: '{content}'")

    if not content:
        logging.warning(f"Пользователь {message.from_user.id} отправил пустое сообщение.")
        return

    from_user_id = message.from_user.id

    if message.text.startswith("/user_send"):
        url = "http://127.0.0.1:8080/user_send"
        payload = {
            "content": content,
            "sender_id": from_user_id,
            "from_user_id": from_user_id,
        }

    elif message.text.startswith("/bot_send"):
        url = "http://127.0.0.1:8080/bot_send"
        payload = {
            "content": content,
            "sender_id": from_user_id,
            "from_user_id": from_user_id,
            "save_to_db": False
        }

    else:
        url = "http://127.0.0.1:8080/default_send"
        payload = {
            "content": content,
            "from_user_id": from_user_id
        }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            logging.info(f"Ответ от API: {response.json()}")
            if response.status_code == 200:
                await message.answer("Сообщение успешно обработано.")
            else:
                await message.answer("Ошибка при обработке сообщения.")
    except Exception as e:
        logging.error(f"Ошибка при отправке данных в API: {e}")
        await message.answer("Произошла ошибка.")


@app.post("/user_send")
async def user_send(message: MessageSchema, db: AsyncSession = Depends(get_db)):
    logging.info(f"Получено сообщение на /user_send: {message}")

    if not message.content:
        logging.error("Пустое содержимое сообщения.")
        raise HTTPException(status_code=400, detail="Контент сообщения не может быть пустым.")

    content = message.content.strip()

    logging.info(f"Обработанное сообщение: {content}")

    match = re.match(r'^/user_send\s*(https?://\S+)?\s*(.*)', content)

    if match:
        address = match.group(1)
        content = match.group(2)

        if not content.strip():
            logging.warning("Контент пустой после извлечения.")
            return {"error": "Сообщение не может быть пустым."}

        logging.info(f"Извлеченные данные: адрес={address}, контент={content}")

        try:
            if address:
                if not is_valid_url(address):
                    logging.error(f"Неверный URL: {address}")
                    raise HTTPException(status_code=400,
                                        detail="Неверный URL: он должен начинаться с http:// или https://")
                await send_to_external_address(address, content)


            await add_message(db, content, address, message.sender_id)

            return {"message": "Сообщение обработано."}

        except Exception as e:
            logging.error(f"Ошибка при обработке сообщения: {e}")
            raise HTTPException(status_code=500, detail="Ошибка при обработке запроса.")

    else:
        logging.error("Неверный формат команды.")
        raise HTTPException(status_code=400, detail="Неверный формат команды.")




@app.post("/bot_send")
async def bot_send_endpoint(message: MessageSchemaBot, db: AsyncSession = Depends(get_db)):
    logging.info(f"Получено сообщение на /bot_send: {message}")
    text = message.content.strip()
    match = re.match(r'^/bot_send\s+(@\w+)?\s*(.+)', text)

    if match:
        username = match.group(1)
        content = match.group(2)

        if username:
            username = username[1:]

            stmt = select(User).where(User.username == username)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if user:

                try:
                    await bot.send_message(user.telegram_id, content)
                    logging.info(f"Сообщение отправлено пользователю {username}: {content}")
                    return {"message": f"Сообщение отправлено пользователю {username}"}
                except Exception as e:
                    logging.error(f"Ошибка отправки сообщения: {e}")
                    return {"error": f"Не удалось отправить сообщение пользователю {username}: {e}"}
            else:
                return {"error": f"Пользователь с именем {username} не найден."}

        else:

            try:
                stmt = select(User.telegram_id)
                result = await db.execute(stmt)
                user_ids = [row[0] for row in result.fetchall()]

                tasks = [bot.send_message(user_id, content) for user_id in user_ids]
                await asyncio.gather(*tasks)

                logging.info("Сообщение отправлено всем пользователям")
                return {"message": "Сообщение отправлено всем пользователям"}
            except Exception as e:
                logging.error(f"Ошибка при отправке сообщения всем пользователям: {e}")
                return {"error": f"Не удалось отправить сообщение всем пользователям: {e}"}
    else:

        raise HTTPException(status_code=400, detail="Неверный формат команды. Ожидается: /bot_send @пользователь текст сообщения.")



async def start_bot():
    await dp.start_polling(bot)


async def start_fastapi():
    config = uvicorn.Config(app, host="127.0.0.1", port=8080)
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    fastapi_task = asyncio.create_task(start_fastapi())
    bot_task = asyncio.create_task(start_bot())

    await asyncio.gather(fastapi_task, bot_task)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())
    loop.run_until_complete(start_fastapi())
