# app/models/user.py - Application user record synchronized with Clerk

from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint, Index
from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("clerk_user_id", name="uq_users_clerk_user_id"),
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_email", "email"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Stable identifier from Clerk (e.g., "user_..."), used for sync
    clerk_user_id = Column(String(128), nullable=False)

    # Primary contact email
    email = Column(String(255), nullable=False)

    # Profile / display data captured by Clerk
    first_name = Column(String(100), nullable=True, default=None)
    last_name = Column(String(100), nullable=True, default=None)
    profile_image_url = Column(Text, nullable=True, default=None)

    # Timestamps from Clerk; stored as timestamptz (SQLAlchemy DateTime with timezone)
    created_at = Column(DateTime(timezone=True), nullable=True, default=None)
    updated_at = Column(DateTime(timezone=True), nullable=True, default=None)
    last_sign_in_at = Column(DateTime(timezone=True), nullable=True, default=None)

    def __repr__(self) -> str:  # pragma: no cover - simple repr
        return f"<User {self.email} ({self.clerk_user_id})>"
