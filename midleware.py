from aiogram.dispatcher.middlewares.base import BaseMiddleware

class DatabaseMiddleware(BaseMiddleware):
    def __init__(self, async_sessionmaker):
        super().__init__()
        self.async_sessionmaker = async_sessionmaker

    async def __call__(self, handler, event, data):
        async with self.async_sessionmaker() as session:
            data["db"] = session
            return await handler(event, data)