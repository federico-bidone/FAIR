"""Simple expense tracking backend service.

This module exposes a small REST API that can be consumed by the
PySide6 front-end.  It stores the expenses inside a local SQLite
database so that the data persist between application restarts.

Endpoints
---------
GET /expenses
    Retrieve the list of stored expenses ordered by date (descending).

POST /expenses
    Create a new expense. The request body must be JSON containing the
    ``description`` (string), ``category`` (string), ``amount`` (float)
    and ``date`` (ISO formatted string ``YYYY-MM-DD``).

DELETE /expenses/<id>
    Remove the expense identified by ``id``.

The service is intentionally lightweight so it can be executed without
additional infrastructure.  It uses Flask because it ships with a
development server that is more than enough for local desktop usage.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from flask import Flask, jsonify, request


DB_PATH = Path(__file__).with_name("expenses.db")


@dataclass
class Expense:
    """Simple data holder describing an expense entry."""

    id: Optional[int]
    description: str
    category: str
    amount: float
    date: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Expense":
        return cls(
            id=row["id"],
            description=row["description"],
            category=row["category"],
            amount=row["amount"],
            date=row["date"],
        )


class ExpenseRepository:
    """Lightweight repository for interacting with the SQLite database."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.touch(exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    amount REAL NOT NULL,
                    date TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def list_expenses(self) -> List[Expense]:
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, description, category, amount, date FROM expenses ORDER BY date DESC, id DESC"
            ).fetchall()
            return [Expense.from_row(row) for row in rows]

    def add_expense(self, expense: Expense) -> Expense:
        with sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                "INSERT INTO expenses (description, category, amount, date) VALUES (?, ?, ?, ?)",
                (expense.description, expense.category, expense.amount, expense.date),
            )
            conn.commit()
            expense.id = cursor.lastrowid
            return expense

    def delete_expense(self, expense_id: int) -> bool:
        with sqlite3.connect(self._path) as conn:
            cursor = conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            conn.commit()
            return cursor.rowcount > 0


repository = ExpenseRepository(DB_PATH)
app = Flask(__name__)


def _validate_payload(data: dict) -> Optional[str]:
    """Validate the incoming JSON body and return an error message if invalid."""

    required_fields = {"description", "category", "amount", "date"}
    missing = required_fields - data.keys()
    if missing:
        return f"Missing fields: {', '.join(sorted(missing))}"

    try:
        float(data["amount"])
    except (TypeError, ValueError):
        return "Amount must be a number"

    if not isinstance(data["description"], str) or not data["description"].strip():
        return "Description must be a non-empty string"

    if not isinstance(data["category"], str) or not data["category"].strip():
        return "Category must be a non-empty string"

    if not isinstance(data["date"], str) or len(data["date"]) != 10:
        return "Date must be an ISO string in the form YYYY-MM-DD"

    return None


@app.get("/expenses")
def get_expenses():
    expenses = [asdict(expense) for expense in repository.list_expenses()]
    return jsonify(expenses)


@app.post("/expenses")
def create_expense():
    data = request.get_json(force=True, silent=True) or {}
    error = _validate_payload(data)
    if error:
        return {"error": error}, 400

    expense = Expense(
        id=None,
        description=data["description"].strip(),
        category=data["category"].strip(),
        amount=float(data["amount"]),
        date=data["date"],
    )
    saved = repository.add_expense(expense)
    return asdict(saved), 201


@app.delete("/expenses/<int:expense_id>")
def delete_expense(expense_id: int):
    deleted = repository.delete_expense(expense_id)
    if not deleted:
        return {"error": "Expense not found"}, 404
    return {"status": "deleted"}, 200


def main() -> None:
    """Entrypoint for running the development server."""

    app.run(host="127.0.0.1", port=5000, debug=True)


if __name__ == "__main__":
    main()
