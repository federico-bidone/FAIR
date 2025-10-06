"""CRUD helper functions for the expense tracking backend."""
from __future__ import annotations

from decimal import Decimal
from typing import List

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, schemas


class EntityNotFoundError(RuntimeError):
    """Raised when an entity cannot be located in the database."""


class EntityConflictError(RuntimeError):
    """Raised when a unique constraint is violated."""


def list_categories(session: Session) -> List[models.Category]:
    stmt = select(models.Category).order_by(models.Category.name)
    return list(session.scalars(stmt))


def get_category(session: Session, category_id: int) -> models.Category:
    category = session.get(models.Category, category_id)
    if category is None:
        raise EntityNotFoundError(f"Category {category_id} not found")
    return category


def create_category(session: Session, category_in: schemas.CategoryCreate) -> models.Category:
    category = models.Category(**category_in.model_dump())
    session.add(category)
    try:
        session.flush()
    except IntegrityError as exc:  # pragma: no cover - simple mapping
        raise EntityConflictError("Category name must be unique") from exc
    session.refresh(category)
    return category


def update_category(session: Session, category_id: int, update_in: schemas.CategoryUpdate) -> models.Category:
    category = get_category(session, category_id)
    for field, value in update_in.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    try:
        session.flush()
    except IntegrityError as exc:  # pragma: no cover
        raise EntityConflictError("Category name must be unique") from exc
    session.refresh(category)
    return category


def delete_category(session: Session, category_id: int) -> None:
    category = get_category(session, category_id)
    session.delete(category)
    session.flush()


def list_expenses(session: Session) -> List[models.Expense]:
    stmt = select(models.Expense).order_by(models.Expense.incurred_on.desc())
    return list(session.scalars(stmt))


def get_expense(session: Session, expense_id: int) -> models.Expense:
    expense = session.get(models.Expense, expense_id)
    if expense is None:
        raise EntityNotFoundError(f"Expense {expense_id} not found")
    return expense


def create_expense(session: Session, expense_in: schemas.ExpenseCreate) -> models.Expense:
    data = expense_in.model_dump(exclude_unset=True)
    expense = models.Expense(**data)
    session.add(expense)
    session.flush()
    session.refresh(expense)
    return expense


def update_expense(session: Session, expense_id: int, update_in: schemas.ExpenseUpdate) -> models.Expense:
    expense = get_expense(session, expense_id)
    for field, value in update_in.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)
    session.flush()
    session.refresh(expense)
    return expense


def delete_expense(session: Session, expense_id: int) -> None:
    expense = get_expense(session, expense_id)
    session.delete(expense)
    session.flush()


def expense_summary(session: Session) -> schemas.SummaryRead:
    total_stmt = select(func.coalesce(func.sum(models.Expense.amount), 0))
    total_value: Decimal = session.scalar(total_stmt) or Decimal(0)

    by_category_stmt = (
        select(
            models.Expense.category_id,
            models.Category.name,
            func.coalesce(func.sum(models.Expense.amount), 0).label("total"),
        )
        .outerjoin(models.Category)
        .group_by(models.Expense.category_id, models.Category.name)
    )
    by_category = [
        schemas.CategorySummary(
            category_id=row.category_id,
            category_name=row.name,
            total=row.total,
        )
        for row in session.execute(by_category_stmt)
    ]

    return schemas.SummaryRead(total_expense=total_value, by_category=by_category)
