from __future__ import annotations

from decimal import Decimal

import pytest

from backend import crud, schemas


def test_create_and_list_categories(db_session):
    created = crud.create_category(db_session, schemas.CategoryCreate(name="Food", description="Meals"))
    assert created.id is not None

    categories = crud.list_categories(db_session)
    assert len(categories) == 1
    assert categories[0].name == "Food"


def test_create_expense_without_category(db_session):
    expense_in = schemas.ExpenseCreate(description="Coffee", amount=Decimal("3.50"))
    expense = crud.create_expense(db_session, expense_in)
    assert expense.description == "Coffee"
    assert expense.category_id is None


def test_expense_summary(db_session):
    food = crud.create_category(db_session, schemas.CategoryCreate(name="Food"))
    misc = crud.create_category(db_session, schemas.CategoryCreate(name="Misc"))
    crud.create_expense(
        db_session,
        schemas.ExpenseCreate(description="Lunch", amount=Decimal("12.00"), category_id=food.id),
    )
    crud.create_expense(
        db_session,
        schemas.ExpenseCreate(description="Notebook", amount=Decimal("5.00"), category_id=misc.id),
    )
    crud.create_expense(
        db_session,
        schemas.ExpenseCreate(description="Donation", amount=Decimal("20.00")),
    )

    summary = crud.expense_summary(db_session)
    assert summary.total_expense == Decimal("37.00")
    totals = {item.category_id: item.total for item in summary.by_category}
    assert totals[food.id] == Decimal("12.00")
    assert totals[misc.id] == Decimal("5.00")
    assert totals[None] == Decimal("20.00")


def test_delete_category_removes_expenses(db_session):
    category = crud.create_category(db_session, schemas.CategoryCreate(name="Subscriptions"))
    expense = crud.create_expense(
        db_session,
        schemas.ExpenseCreate(description="Streaming", amount=Decimal("9.99"), category_id=category.id),
    )
    crud.delete_category(db_session, category.id)

    with pytest.raises(crud.EntityNotFoundError):
        crud.get_category(db_session, category.id)
    with pytest.raises(crud.EntityNotFoundError):
        crud.get_expense(db_session, expense.id)

