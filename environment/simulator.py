"""Simulated supply chain environment backed by SQLAlchemy."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

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
    """SQLAlchemy-backed simulated supply chain environment with an in-memory cache."""

    def __init__(self, db_url: str | None = None, seed: int | None = None) -> None:
        settings = get_settings()
        self.db_url = db_url or settings.db_url
        self.random_seed = seed if seed is not None else settings.random_seed
        self._session_factory = create_session_factory(self.db_url)
        self._seeded = False
        self._products: dict[str, Product] = {}
        self._suppliers: dict[str, Supplier] = {}
        self._warehouses: dict[str, Warehouse] = {}
        self._transport: dict[str, TransportOption] = {}
        self._demand: dict[str, list[DemandRecord]] = {}

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        """Yield a database session that always closes."""
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def invalidate_cache(self) -> None:
        """Drop cached entities so the next read reloads from the database."""
        self._products.clear()
        self._suppliers.clear()
        self._warehouses.clear()
        self._transport.clear()
        self._demand.clear()

    def _warm_cache(self) -> None:
        """Load all entities into memory after seed or mutation."""
        with self._session_scope() as session:
            self._products = {p.product_id: orm_to_product(p) for p in session.query(ProductORM).all()}
            self._suppliers = {s.supplier_id: orm_to_supplier(s) for s in session.query(SupplierORM).all()}
            self._warehouses = {w.warehouse_id: orm_to_warehouse(w) for w in session.query(WarehouseORM).all()}
            self._transport = {
                t.option_id: orm_to_transport(t) for t in session.query(TransportOptionORM).all()
            }
            demand_rows = session.query(DemandRecordORM).order_by(DemandRecordORM.date).all()
            self._demand = {}
            for row in demand_rows:
                self._demand.setdefault(row.product_id, []).append(orm_to_demand(row))

    def seed(self) -> None:
        """Clear and re-seed the database with deterministic synthetic data."""
        with self._session_scope() as session:
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
        self._seeded = True
        self._warm_cache()

    def seed_if_needed(self) -> None:
        """Seed once when the database is empty."""
        if self._seeded and self._products:
            return
        with self._session_scope() as session:
            has_products = session.query(ProductORM).first() is not None
        if has_products:
            self._seeded = True
            self._warm_cache()
            return
        self.seed()

    def get_product(self, product_id: str) -> Product:
        """Return product by ID."""
        if not self._products:
            self._warm_cache()
        product = self._products.get(product_id)
        if product is None:
            raise MissingEntityError("Product", product_id)
        return product

    def list_products(self) -> list[Product]:
        """Return all products."""
        if not self._products:
            self._warm_cache()
        return list(self._products.values())

    def get_suppliers(self, product_id: str) -> list[Supplier]:
        """Return suppliers that serve the given product."""
        self.get_product(product_id)
        if not self._suppliers:
            self._warm_cache()
        result = [s for s in self._suppliers.values() if product_id in s.product_ids]
        if not result:
            raise MissingEntityError("Suppliers for product", product_id)
        return result

    def get_supplier(self, supplier_id: str) -> Supplier:
        """Return supplier by ID."""
        if not self._suppliers:
            self._warm_cache()
        supplier = self._suppliers.get(supplier_id)
        if supplier is None:
            raise MissingEntityError("Supplier", supplier_id)
        return supplier

    def get_demand_history(
        self,
        product_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[DemandRecord]:
        """Return demand history for a product."""
        self.get_product(product_id)
        if product_id not in self._demand:
            self._warm_cache()
        records = list(self._demand.get(product_id, []))
        if start_date:
            records = [r for r in records if r.date >= start_date]
        if end_date:
            records = [r for r in records if r.date <= end_date]
        if not records:
            raise MissingEntityError("Demand history for product", product_id)
        return records

    def get_inventory(self, product_id: str, warehouse_id: str | None = None) -> int:
        """Return total or warehouse-specific inventory."""
        self.get_product(product_id)
        if not self._warehouses:
            self._warm_cache()
        if warehouse_id:
            warehouse = self._warehouses.get(warehouse_id)
            if warehouse is None:
                raise MissingEntityError("Warehouse", warehouse_id)
            return warehouse.current_inventory.get(product_id, 0)
        return sum(w.current_inventory.get(product_id, 0) for w in self._warehouses.values())

    def get_warehouses(self) -> list[Warehouse]:
        """Return all warehouses."""
        if not self._warehouses:
            self._warm_cache()
        return list(self._warehouses.values())

    def get_warehouse(self, warehouse_id: str) -> Warehouse:
        """Return warehouse by ID."""
        if not self._warehouses:
            self._warm_cache()
        warehouse = self._warehouses.get(warehouse_id)
        if warehouse is None:
            raise MissingEntityError("Warehouse", warehouse_id)
        return warehouse

    def get_transport_options(self, product_id: str) -> list[TransportOption]:
        """Return transport options for a product."""
        self.get_product(product_id)
        if not self._transport:
            self._warm_cache()
        result = list(self._transport.values())
        if not result:
            raise MissingEntityError("Transport options for product", product_id)
        return result

    def get_transport_option(self, option_id: str) -> TransportOption:
        """Return transport option by ID."""
        if not self._transport:
            self._warm_cache()
        option = self._transport.get(option_id)
        if option is None:
            raise MissingEntityError("TransportOption", option_id)
        return option
