# B.I.D.O.
Best Investment Decision Optimizator

## Expense tracker desktop app

This repository now includes a simple expense tracking application that
is composed of two Python scripts:

* `backend.py` – a Flask based REST API backed by SQLite for storing expenses.
* `frontend.py` – a PySide6 desktop interface inspired by IBM's Carbon Design System.

### Prerequisites

Install the required dependencies inside your virtual environment:

```bash
pip install flask PySide6 requests
```

### Running the backend

```bash
python backend.py
```

This will start the development server on `http://127.0.0.1:5000`.

### Running the front-end

In a second terminal start the PySide6 client:

```bash
python frontend.py
```

Make sure the backend is running before launching the front-end so the
expenses can be loaded and stored correctly.
