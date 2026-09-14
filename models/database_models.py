"""SQLAlchemy database models for supply chain entities."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class ProductORM(Base):
    """Product table."""

    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64))
    unit_cost: Mapped[float] = mapped_column(Float)
    selling_price: Mapped[float] = mapped_column(Float)


class SupplierORM(Base):
    """Supplier table."""

    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    product_ids_json: Mapped[str] = mapped_column(Text)
    unit_price: Mapped[float] = mapped_column(Float)
    capacity: Mapped[int] = mapped_column(Integer)
    lead_time_days: Mapped[int] = mapped_column(Integer)
    reliability: Mapped[float] = mapped_column(Float)
    disruption_probability: Mapped[float] = mapped_column(Float, default=0.05)

    @property
    def product_ids(self) -> list[str]:
        """Deserialize product IDs."""
        return json.loads(self.product_ids_json)

    @product_ids.setter
    def product_ids(self, value: list[str]) -> None:
        """Serialize product IDs."""
        self.product_ids_json = json.dumps(value)


class WarehouseORM(Base):
    """Warehouse table."""

    __tablename__ = "warehouses"

    warehouse_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    location: Mapped[str] = mapped_column(String(128))
    capacity: Mapped[int] = mapped_column(Integer)
    current_inventory_json: Mapped[str] = mapped_column(Text, default="{}")

    @property
    def current_inventory(self) -> dict[str, int]:
        """Deserialize inventory map."""
        return json.loads(self.current_inventory_json)

    @current_inventory.setter
    def current_inventory(self, value: dict[str, int]) -> None:
        """Serialize inventory map."""
        self.current_inventory_json = json.dumps(value)


class DemandRecordORM(Base):
    """Demand history table."""

    __tablename__ = "demand_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime] = mapped_column(DateTime)
    product_id: Mapped[str] = mapped_column(String(32))
    demand_quantity: Mapped[int] = mapped_column(Integer)


class TransportOptionORM(Base):
    """Transport option table."""

    __tablename__ = "transport_options"

    option_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    mode: Mapped[str] = mapped_column(String(64))
    carrier: Mapped[str] = mapped_column(String(128))
    cost_per_unit: Mapped[float] = mapped_column(Float)
    delivery_time_days: Mapped[int] = mapped_column(Integer)
    capacity: Mapped[int] = mapped_column(Integer)
    reliability: Mapped[float] = mapped_column(Float)
    product_ids_json: Mapped[str] = mapped_column(Text, default='["P001"]')

    @property
    def product_ids(self) -> list[str]:
        """Deserialize product IDs."""
        return json.loads(self.product_ids_json)


def create_db_engine(db_url: str):
    """Create SQLAlchemy engine."""
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    return create_engine(db_url, connect_args=connect_args)


def create_session_factory(db_url: str) -> sessionmaker[Session]:
    """Create session factory and ensure tables exist."""
    engine = create_db_engine(db_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
