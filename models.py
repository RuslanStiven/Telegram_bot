from datetime import datetime
from database import async_engine
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    name = Column(String, nullable=True)
    last_start_time = Column(DateTime)

    messages = relationship("MessageModals", back_populates="sender")


class MessageModals(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, index=True)
    sender_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    sender = relationship("User", back_populates="messages")

async def create_message(db: AsyncSession, telegram_id: int, content: str):

    user = await db.execute(select(User).filter(User.telegram_id == telegram_id))
    user = user.scalar_one_or_none()

    if user is None:
        raise Exception("User not found")

    message = MessageModals(content=content, sender_id=user.telegram_id, created_at=datetime.utcnow())

    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message



async def create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
