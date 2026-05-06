from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.config import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    api_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(32), nullable=False, default="beginner")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="user", uselist=False)
    orders = relationship("Order", back_populates="user")
    trades = relationship("Trade", back_populates="user")
