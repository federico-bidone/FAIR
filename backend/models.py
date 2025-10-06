"""SQLAlchemy models for the expense tracking backend."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class Category(Base):
    __tablename__ = "categories"

    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String(100), unique=True, nullable=False, index=True)
    description: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)

    expenses = relationship("Expense", back_populates="category", cascade="all, delete-orphan")


class Expense(Base):
    __tablename__ = "expenses"

    id: int = Column(Integer, primary_key=True, index=True)
    description: str = Column(String(255), nullable=False)
    amount: float = Column(Numeric(12, 2), nullable=False)
    incurred_on: datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
    category_id: Optional[int] = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)

    category = relationship("Category", back_populates="expenses")
