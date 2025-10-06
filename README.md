# B.I.D.O.

Best Investment Decision Optimizator

## Backend service

The repository now includes a lightweight FastAPI backend that exposes REST endpoints for managing expenses and categories and returning aggregated summaries.

### Requirements

* Python 3.10+
* [FastAPI](https://fastapi.tiangolo.com/)
* [SQLAlchemy](https://www.sqlalchemy.org/)
* [Uvicorn](https://www.uvicorn.org/) (for running the ASGI server)
* [Pytest](https://docs.pytest.org/) (for running the backend test suite)

Install dependencies into a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" sqlalchemy pydantic pytest
```

### Running the API server

Initialise the SQLite database and start the FastAPI application:

```bash
uvicorn backend.server:app --reload
```

The API defaults to storing data in `backend/expenses.db`. Override the location by setting the `BIDO_DB_PATH` environment variable before launching the server.

### Available endpoints

* `GET /health` – quick service healthcheck
* `GET /categories`, `POST /categories`, `PUT /categories/{id}`, `DELETE /categories/{id}` – manage expense categories
* `GET /expenses`, `POST /expenses`, `PUT /expenses/{id}`, `DELETE /expenses/{id}` – manage expenses
* `GET /summary` – aggregate totals for all expenses grouped by category

### Running tests

Execute the backend test suite with pytest:

```bash
pytest backend/tests
```
