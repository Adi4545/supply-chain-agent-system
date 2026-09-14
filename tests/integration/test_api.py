"""Integration tests for FastAPI endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_list_products() -> None:
    """GET /products should return product list."""
    resp = client.get("/products")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(p["product_id"] == "P001" for p in data)


def test_list_suppliers() -> None:
    """GET /suppliers should return suppliers."""
    resp = client.get("/suppliers?product_id=P001")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_get_inventory() -> None:
    """GET /inventory/{product_id} should return quantity."""
    resp = client.get("/inventory/P001")
    assert resp.status_code == 200
    assert resp.json()["quantity"] == 3500


def test_plan_endpoint() -> None:
    """POST /plan should run pipeline and return decision."""
    resp = client.post(
        "/plan",
        json={"objective": "Plan replenishment for product P001", "product_id": "P001"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["final_decision"]["requires_human_approval"] is True
    assert "Orchestrator" in data["trace_summary"]
    assert data["inventory"] == 3500
    assert data["demand_forecast"] is not None


def test_execution_trace() -> None:
    """GET /execution-trace/{run_id} should return trace."""
    plan_resp = client.post(
        "/plan",
        json={"objective": "Plan replenishment for product P001", "product_id": "P001"},
    )
    run_id = plan_resp.json()["run_id"]
    resp = client.get(f"/execution-trace/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["run_id"] == run_id
    assert len(resp.json()["trace"]) > 0


def test_simulate_disruption() -> None:
    """POST /simulate-disruption should replan."""
    plan_resp = client.post(
        "/plan",
        json={"objective": "Plan replenishment for product P001", "product_id": "P001"},
    )
    run_id = plan_resp.json()["run_id"]
    resp = client.post(
        "/simulate-disruption",
        json={
            "run_id": run_id,
            "disruption": {
                "disruption_type": "demand_spike",
                "description": "Test spike",
            },
        },
    )
    assert resp.status_code == 200
    assert resp.json()["final_decision"]["revision_reason"] is not None
