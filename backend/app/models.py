import uuid
from datetime import datetime, timezone
from sqlalchemy import (JSON, Boolean, false, String, Integer, Text, DateTime,
                        ForeignKey, UniqueConstraint, Uuid)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # incrementado em logout/troca de senha: invalida todos os tokens antigos
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    source_filename: Mapped[str | None] = mapped_column(String(255))
    followers_total: Mapped[int] = mapped_column(Integer, default=0)
    following_total: Mapped[int] = mapped_column(Integer, default=0)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    info: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    profiles: Mapped[list["Profile"]] = relationship(back_populates="order", cascade="all, delete-orphan")

class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("order_id", "username"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    username: Mapped[str] = mapped_column(String(30))
    followers_count: Mapped[int | None] = mapped_column(Integer)
    following_count: Mapped[int | None] = mapped_column(Integer)
    bio: Mapped[str | None] = mapped_column(Text)
    profile_url: Mapped[str | None] = mapped_column(String(255))   # link canônico (Apify `url`)
    enrich_source: Mapped[str | None] = mapped_column(String(30))  # provider que consultou
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    order: Mapped[Order] = relationship(back_populates="profiles")
