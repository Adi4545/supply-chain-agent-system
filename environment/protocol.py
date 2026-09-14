"""Environment Protocol defining the data access facade."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from models.schemas import DemandRecord, Product, Supplier, TransportOption, Warehouse


@runtime_checkable
class Environment(Protocol):
    """Protocol for supply chain data access — simulator or real ERP."""

    def get_product(self, product_id: str) -> Product:
        """Return product by ID or raise MissingEntityError."""
        ...

    def list_products(self) -> list[Product]:
        """Return all products."""
        ...

    def get_suppliers(self, product_id: str) -> list[Supplier]:
        """Return suppliers for a product."""
        ...

    def get_supplier(self, supplier_id: str) -> Supplier:
        """Return supplier by ID or raise MissingEntityError."""
        ...

    def get_demand_history(
        self,
        product_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[DemandRecord]:
        """Return historical demand records for a product."""
        ...

    def get_inventory(self, product_id: str, warehouse_id: str | None = None) -> int:
        """Return current inventory quantity for a product."""
        ...

    def get_warehouses(self) -> list[Warehouse]:
        """Return all warehouses."""
        ...

    def get_warehouse(self, warehouse_id: str) -> Warehouse:
        """Return warehouse by ID or raise MissingEntityError."""
        ...

    def get_transport_options(self, product_id: str) -> list[TransportOption]:
        """Return available transport options for a product."""
        ...

    def get_transport_option(self, option_id: str) -> TransportOption:
        """Return transport option by ID or raise MissingEntityError."""
        ...

    def seed(self) -> None:
        """Initialize or re-seed the environment with synthetic data."""
        ...
