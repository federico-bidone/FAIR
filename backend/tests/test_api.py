from __future__ import annotations


def test_healthcheck(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_retrieve_expense(client):
    category = client.post("/categories", json={"name": "Travel", "description": "Trips"})
    assert category.status_code == 201
    category_id = category.json()["id"]

    create_resp = client.post(
        "/expenses",
        json={
            "description": "Train ticket",
            "amount": "45.10",
            "category_id": category_id,
        },
    )
    assert create_resp.status_code == 201
    expense_id = create_resp.json()["id"]

    get_resp = client.get(f"/expenses/{expense_id}")
    assert get_resp.status_code == 200
    payload = get_resp.json()
    assert payload["description"] == "Train ticket"
    assert payload["amount"] == "45.10"
    assert payload["category_id"] == category_id


def test_summary_endpoint(client):
    client.post("/expenses", json={"description": "Book", "amount": "15.00"})
    summary_resp = client.get("/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_expense"] == "15.00"
    assert any(item["total"] == "15.00" for item in summary["by_category"])
