"""FastAPI application exposing expense tracking endpoints."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import crud, database, schemas


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.init_db()
    yield


app = FastAPI(title="B.I.D.O. Expense Backend", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/expenses", response_model=List[schemas.ExpenseRead])
def list_expenses(db: Session = Depends(database.get_db)) -> List[schemas.ExpenseRead]:
    return crud.list_expenses(db)


@app.post(
    "/expenses",
    response_model=schemas.ExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(expense_in: schemas.ExpenseCreate, db: Session = Depends(database.get_db)) -> schemas.ExpenseRead:
    return crud.create_expense(db, expense_in)


@app.get("/expenses/{expense_id}", response_model=schemas.ExpenseRead)
def get_expense(expense_id: int, db: Session = Depends(database.get_db)) -> schemas.ExpenseRead:
    try:
        return crud.get_expense(db, expense_id)
    except crud.EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.put("/expenses/{expense_id}", response_model=schemas.ExpenseRead)
def update_expense(
    expense_id: int,
    update_in: schemas.ExpenseUpdate,
    db: Session = Depends(database.get_db),
) -> schemas.ExpenseRead:
    try:
        return crud.update_expense(db, expense_id, update_in)
    except crud.EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: Session = Depends(database.get_db)) -> None:
    try:
        crud.delete_expense(db, expense_id)
    except crud.EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.get("/categories", response_model=List[schemas.CategoryRead])
def list_categories(db: Session = Depends(database.get_db)) -> List[schemas.CategoryRead]:
    return crud.list_categories(db)


@app.post(
    "/categories",
    response_model=schemas.CategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_category(category_in: schemas.CategoryCreate, db: Session = Depends(database.get_db)) -> schemas.CategoryRead:
    try:
        return crud.create_category(db, category_in)
    except crud.EntityConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.get("/categories/{category_id}", response_model=schemas.CategoryRead)
def get_category(category_id: int, db: Session = Depends(database.get_db)) -> schemas.CategoryRead:
    try:
        return crud.get_category(db, category_id)
    except crud.EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.put("/categories/{category_id}", response_model=schemas.CategoryRead)
def update_category(
    category_id: int,
    update_in: schemas.CategoryUpdate,
    db: Session = Depends(database.get_db),
) -> schemas.CategoryRead:
    try:
        return crud.update_category(db, category_id, update_in)
    except crud.EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except crud.EntityConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(database.get_db)) -> None:
    try:
        crud.delete_category(db, category_id)
    except crud.EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.get("/summary", response_model=schemas.SummaryRead)
def get_summary(db: Session = Depends(database.get_db)) -> schemas.SummaryRead:
    return crud.expense_summary(db)


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
