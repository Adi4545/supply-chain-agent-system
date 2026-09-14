"""Simulated supply chain environment backed by SQLAlchemy."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from config.settings import get_settings
from core.exceptions import MissingEntityError
from environment.synthetic_data import (
    generate_canonical_products,
    generate_canonical_suppliers,
    generate_canonical_transport,
    generate_canonical_warehouses,
    generate_demand_history,
    orm_to_demand,
    orm_to_product,
    orm_to_supplier,
    orm_to_transport,
    orm_to_warehouse,
)
from models.database_models import (
    DemandRecordORM,
    ProductORM,
    SupplierORM,
    TransportOptionORM,
    WarehouseORM,
    create_session_factory,
)
from models.schemas import DemandRecord, Product, Supplier, TransportOption, Warehouse


class SimulatedEnvironment:
    """SQLAlchemy-backed simulated supply chain environment."""

    def __init__(self, db_url: str | None = None, seed: int | None = None) -> None:
        settings = get_settings()
        self.db_url = db_url or settings.db_url
        self.random_seed = seed if seed is not None else settings.random_seed
        self._session_factory = create_session_factory(self.db_url)

    def _session(self) -> Session:
        """Create a new database session."""
        return self._session_factory()

    def seed(self) -> None:
        """Clear and re-seed the database with deterministic synthetic data."""
        session = self._session()
        try:
            session.query(DemandRecordORM).delete()
            session.query(TransportOptionORM).delete()
            session.query(SupplierORM).delete()
            session.query(WarehouseORM).delete()
            session.query(ProductORM).delete()
            session.commit()

            for product in generate_canonical_products():
                session.add(product)
            for supplier in generate_canonical_suppliers():
                session.add(supplier)
            for warehouse in generate_canonical_warehouses():
                session.add(warehouse)
            for transport in generate_canonical_transport():
                session.add(transport)
            for record in generate_demand_history("P001", self.random_seed):
                session.add(record)
            for record in generate_demand_history("P002", self.random_seed + 1, base_demand=280):
                session.add(record)
            session.commit()
        finally:
            session.close()

    def get_product(self, product_id: str) -> Product:
        """Return product by ID."""
        session = self._session()
        try:
            orm = session.get(ProductORM, product_id)
            if orm is None:
                raise MissingEntityError("Product", product_id)
            return orm_to_product(orm)
        finally:
            session.close()

    def list_products(self) -> list[Product]:
        """Return all products."""
        session = self._session()
        try:
            return [orm_to_product(p) for p in session.query(ProductORM).all()]
        finally:
            session.close()

    def get_suppliers(self, product_id: str) -> list[Supplier]:
        """Return suppliers that serve the given product."""
        self.get_product(product_id)  # validate product exists
        session = self._session()
        try:
            suppliers = session.query(SupplierORM).all()
            result = [
                orm_to_supplier(s)
                for s in suppliers
                if product_id in s.product_ids
            ]
            if not result:
                raise MissingEntityError("Suppliers for product", product_id)
            return result
        finally:
            session.close()

    def get_supplier(self, supplier_id: str) -> Supplier:
        """Return supplier by ID."""
        session = self._session()
        try:
            orm = session.get(SupplierORM, supplier_id)
            if orm is None:
                raise MissingEntityError("Supplier", supplier_id)
            return orm_to_supplier(orm)
        finally:
            session.close()

    def get_demand_history(
        self,
        product_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[DemandRecord]:
        """Return demand history for a product."""
        self.get_product(product_id)
        session = self._session()
        try:
            query = session.query(DemandRecordORM).filter(
                DemandRecordORM.product_id == product_id
            )
            if start_date:
                query = query.filter(DemandRecordORM.date >= start_date)
            if end_date:
                query = query.filter(DemandRecordORM.date <= end_date)
            records = query.order_by(DemandRecordORM.date).all()
            if not records:
                raise MissingEntityError("Demand history for product", product_id)
            return [orm_to_demand(r) for r in records]
        finally:
            session.close()

    def get_inventory(self, product_id: str, warehouse_id: str | None = None) -> int:
        """Return total or warehouse-specific inventory."""
        self.get_product(product_id)
        session = self._session()
        try:
            if warehouse_id:
                wh = session.get(WarehouseORM, warehouse_id)
                if wh is None:
                    raise MissingEntityError("Warehouse", warehouse_id)
                return wh.current_inventory.get(product_id, 0)
            warehouses = session.query(WarehouseORM).all()
            return sum(w.current_inventory.get(product_id, 0) for w in warehouses)
        finally:
            session.close()

    def get_warehouses(self) -> list[Warehouse]:
        """Return all warehouses."""
        session = self._session()
        try:
            return [orm_to_warehouse(w) for w in session.query(WarehouseORM).all()]
        finally:
            session.close()

    def get_warehouse(self, warehouse_id: str) -> Warehouse:
        """Return warehouse by ID."""
        session = self._session()
        try:
            orm = session.get(WarehouseORM, warehouse_id)
            if orm is None:
                raise MissingEntityError("Warehouse", warehouse_id)
            return orm_to_warehouse(orm)
        finally:
            session.close()

    def get_transport_options(self, product_id: str) -> list[TransportOption]:
        """Return transport options for a product."""
        self.get_product(product_id)
        session = self._session()
        try:
            options = session.query(TransportOptionORM).all()
            result = [
                orm_to_transport(o)
                for o in options
                if product_id in o.product_ids
            ]
            if not result:
                raise MissingEntityError("Transport options for product", product_id)
            return result
        finally:
            session.close()

    def get_transport_option(self, option_id: str) -> TransportOption:
        """Return transport option by ID."""
        session = self._session()
        try:
            orm = session.get(TransportOptionORM, option_id)
            if orm is None:
                raise MissingEntityError("TransportOption", option_id)
            return orm_to_transport(orm)
        finally:
            session.close()
