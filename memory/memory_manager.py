"""Pluggable memory management for short and long-term storage."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from core.time import utc_now
from models.database_models import Base, create_db_engine, create_session_factory
from models.schemas import FinalDecision


class MemoryManager(ABC):
    """Abstract memory interface — swap SQLite for vector DB without agent changes."""

    @abstractmethod
    def record_decision(self, run_id: str, decision: FinalDecision, context: dict[str, Any]) -> None:
        """Store a planning decision for long-term retrieval."""
        ...

    @abstractmethod
    def get_supplier_performance(self, supplier_id: str) -> dict[str, Any]:
        """Return historical supplier performance metrics."""
        ...

    @abstractmethod
    def get_demand_patterns(self, product_id: str) -> dict[str, Any]:
        """Return historical demand patterns."""
        ...

    @abstractmethod
    def record_disruption(self, disruption: dict[str, Any]) -> None:
        """Record a disruption event."""
        ...

    @abstractmethod
    def get_past_decisions(self, product_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return recent planning decisions for a product."""
        ...


# SQLite-backed tables for long-term memory
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class DecisionRecordORM(Base):
    """Stored planning decisions."""

    __tablename__ = "decision_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64))
    product_id: Mapped[str] = mapped_column(String(32))
    decision_json: Mapped[str] = mapped_column(Text)
    context_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DisruptionRecordORM(Base):
    """Stored disruption events."""

    __tablename__ = "disruption_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    disruption_type: Mapped[str] = mapped_column(String(64))
    details_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class SQLiteMemoryStore(MemoryManager):
    """SQLite/JSON-backed long-term memory store."""

    def __init__(self, db_url: str) -> None:
        engine = create_db_engine(db_url)
        Base.metadata.create_all(engine)
        self._session_factory = create_session_factory(db_url)

    def _session(self) -> Session:
        return self._session_factory()

    def record_decision(self, run_id: str, decision: FinalDecision, context: dict[str, Any]) -> None:
        session = self._session()
        try:
            record = DecisionRecordORM(
                run_id=run_id,
                product_id=context.get("product_id", "P001"),
                decision_json=decision.model_dump_json(),
                context_json=json.dumps(context),
            )
            session.add(record)
            session.commit()
        finally:
            session.close()

    def get_supplier_performance(self, supplier_id: str) -> dict[str, Any]:
        return {
            "supplier_id": supplier_id,
            "avg_delay_days": 0.5,
            "fulfillment_rate": 0.94,
            "historical_orders": 12,
        }

    def get_demand_patterns(self, product_id: str) -> dict[str, Any]:
        return {
            "product_id": product_id,
            "seasonality": "mid-week peak",
            "avg_monthly_demand": 12000,
            "volatility": 0.15,
        }

    def record_disruption(self, disruption: dict[str, Any]) -> None:
        session = self._session()
        try:
            record = DisruptionRecordORM(
                disruption_type=disruption.get("disruption_type", "unknown"),
                details_json=json.dumps(disruption),
            )
            session.add(record)
            session.commit()
        finally:
            session.close()

    def get_past_decisions(self, product_id: str, limit: int = 10) -> list[dict[str, Any]]:
        session = self._session()
        try:
            records = (
                session.query(DecisionRecordORM)
                .filter(DecisionRecordORM.product_id == product_id)
                .order_by(DecisionRecordORM.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "run_id": r.run_id,
                    "decision": json.loads(r.decision_json),
                    "context": json.loads(r.context_json),
                    "created_at": r.created_at.isoformat(),
                }
                for r in records
            ]
        finally:
            session.close()
