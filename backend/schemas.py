"""Pydantic schemas for serialising expense tracking data."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None


class CategoryRead(CategoryBase, ORMModel):
    id: int
    created_at: datetime


class ExpenseBase(BaseModel):
    description: str = Field(..., max_length=255)
    amount: Decimal = Field(..., gt=0)
    incurred_on: Optional[datetime] = None
    category_id: Optional[int] = Field(None, ge=1)


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=255)
    amount: Optional[Decimal] = Field(None, gt=0)
    incurred_on: Optional[datetime] = None
    category_id: Optional[int] = Field(None, ge=1)


class ExpenseRead(ExpenseBase, ORMModel):
    id: int


class SummaryRead(BaseModel):
    total_expense: Decimal
    by_category: List["CategorySummary"]


class CategorySummary(BaseModel):
    category_id: Optional[int]
    category_name: Optional[str]
    total: Decimal


SummaryRead.model_rebuild()
