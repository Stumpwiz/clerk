# app/models/user.py - Local application user for authentication

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, UniqueConstraint, false, func
from sqlalchemy import LargeBinary
from sqlalchemy.orm import deferred
from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_email", "email"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(512), nullable=False)
    session_version = Column(Integer, nullable=False, default=0, server_default="0")
    display_name = Column(String(255), nullable=False)
    avatar_path = Column(Text, nullable=True, default=None)
    avatar_bytes = deferred(Column(LargeBinary, nullable=True))
    is_active = Column(Boolean, nullable=False, server_default="true", default=True)
    is_admin = Column(Boolean, nullable=False, server_default=false(), default=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True, default=None)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - simple repr
        return f"<User {self.email}>"
