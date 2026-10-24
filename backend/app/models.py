import uuid
from datetime import datetime, timezone
from sqlalchemy import (JSON, Boolean, String, Integer, Text, DateTime,
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
    # incrementado em logout/troca de senha: invalida todos os tokens antigos
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Invite(Base):
    """Convite de acesso (backoffice): um link de uso único por e-mail.

    O operador cria o convite via `python -m app.invite` e distribui o link
    fora da aplicação; não há verificação por e-mail (o endereço é confiável no
    momento do convite). Expira em `INVITE_DAYS` e é consumido no aceite.
    """
    __tablename__ = "invites"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 do token; nunca o cru
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # NULL = pendente

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
    entries: Mapped[list["TakeoutEntry"]] = relationship(back_populates="order", cascade="all, delete-orphan")

class Profile(Base):
    """Perfil enriquecido, global e agnóstico: independe do pedido.

    A chave natural é o `username` (vindo do Takeout). A relação de um pedido
    com este perfil fica em `TakeoutEntry` e expira na retenção; o perfil
    permanece para reuso já que se basea em dados públicos.
    """
    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("username"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(30))
    followers_count: Mapped[int | None] = mapped_column(Integer)
    following_count: Mapped[int | None] = mapped_column(Integer)
    bio: Mapped[str | None] = mapped_column(Text)
    profile_url: Mapped[str | None] = mapped_column(String(255))   # link canônico (Apify `url`)
    full_name: Mapped[str | None] = mapped_column(String(255))     # Apify `fullName`
    external_url: Mapped[str | None] = mapped_column(Text)         # Apify `externalUrl`
    profile_pic_url: Mapped[str | None] = mapped_column(Text)      # Apify `profilePicUrl`
    posts_count: Mapped[int | None] = mapped_column(Integer)       # Apify `postsCount`
    category: Mapped[str | None] = mapped_column(String(255))      # Apify `businessCategoryName`
    is_verified: Mapped[bool | None] = mapped_column(Boolean)      # Apify `verified`
    is_business: Mapped[bool | None] = mapped_column(Boolean)      # Apify `isBusinessAccount`
    enrich_source: Mapped[str | None] = mapped_column(String(30))  # provider que consultou
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")


class TakeoutEntry(Base):
    """Relação de um pedido com um perfil (seguidor/eu sigo), vinda do Takeout.

    Um usuário nas duas listas gera duas linhas (follower + following). Expira
    com a retenção do pedido; o `Profile` correspondente permanece.
    """
    __tablename__ = "takeout_entries"
    __table_args__ = (UniqueConstraint("order_id", "username", "relation"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    username: Mapped[str] = mapped_column(String(30), ForeignKey("profiles.username", ondelete="CASCADE"), index=True)
    relation: Mapped[str] = mapped_column(String(20))   # "follower" | "following"
    order: Mapped[Order] = relationship(back_populates="entries")
