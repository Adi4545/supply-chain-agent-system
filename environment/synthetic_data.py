"""Deterministic synthetic data generators for the simulated environment."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from models.database_models import (
    DemandRecordORM,
    ProductORM,
    SupplierORM,
    TransportOptionORM,
    WarehouseORM,
)
from models.schemas import DemandRecord, Product, Supplier, TransportOption, Warehouse


def generate_canonical_products() -> list[ProductORM]:
    """Return canonical product seed data."""
    return [
        ProductORM(
            product_id="P001",
            name="Industrial Widget A",
            category="components",
            unit_cost=25.0,
            selling_price=45.0,
        ),
        ProductORM(
            product_id="P002",
            name="Industrial Widget B",
            category="components",
            unit_cost=18.0,
            selling_price=32.0,
        ),
    ]


def generate_canonical_suppliers() -> list[SupplierORM]:
    """Return canonical supplier seed data for P001 scenario."""
    suppliers = [
        SupplierORM(
            supplier_id="SUP_A",
            name="Supplier A (Low Cost)",
            unit_price=22.0,
            capacity=15000,
            lead_time_days=7,
            reliability=0.88,
            disruption_probability=0.08,
        ),
        SupplierORM(
            supplier_id="SUP_B",
            name="Supplier B (Fast)",
            unit_price=28.0,
            capacity=8000,
            lead_time_days=3,
            reliability=0.92,
            disruption_probability=0.05,
        ),
        SupplierORM(
            supplier_id="SUP_C",
            name="Supplier C (Balanced)",
            unit_price=24.5,
            capacity=12000,
            lead_time_days=5,
            reliability=0.90,
            disruption_probability=0.06,
        ),
    ]
    for s in suppliers:
        s.product_ids = ["P001", "P002"]
    return suppliers


def generate_canonical_warehouses() -> list[WarehouseORM]:
    """Return canonical warehouse with P001 inventory of 3500."""
    wh = WarehouseORM(
        warehouse_id="WH01",
        location="Central Distribution Hub",
        capacity=50000,
    )
    wh.current_inventory = {"P001": 3500, "P002": 1200}
    return [wh]


def generate_canonical_transport() -> list[TransportOptionORM]:
    """Return canonical transport options."""
    options = [
        TransportOptionORM(
            option_id="TRUCK",
            mode="ground",
            carrier="FastFreight Logistics",
            cost_per_unit=1.50,
            delivery_time_days=2,
            capacity=20000,
            reliability=0.93,
        ),
        TransportOptionORM(
            option_id="RAIL",
            mode="rail",
            carrier="Continental Rail",
            cost_per_unit=0.80,
            delivery_time_days=4,
            capacity=50000,
            reliability=0.89,
        ),
        TransportOptionORM(
            option_id="AIR",
            mode="air",
            carrier="ExpressAir Cargo",
            cost_per_unit=4.50,
            delivery_time_days=1,
            capacity=5000,
            reliability=0.96,
        ),
    ]
    for opt in options:
        opt.product_ids_json = '["P001", "P002"]'
    return options


def generate_demand_history(
    product_id: str,
    seed: int,
    days: int = 90,
    base_demand: int = 400,
) -> list[DemandRecordORM]:
    """Generate deterministic demand history with seasonality and spikes."""
    rng = random.Random(seed)
    records: list[DemandRecordORM] = []
    start = datetime(2025, 6, 1)

    for day in range(days):
        date = start + timedelta(days=day)
        # Weekly seasonality: higher mid-week
        weekday_factor = 1.0 + 0.15 * (1 if date.weekday() in (1, 2, 3) else 0)
        # Monthly seasonality
        month_factor = 1.0 + 0.1 * ((date.month % 6) / 6)
        quantity = int(base_demand * weekday_factor * month_factor)
        # Occasional spikes (~5% of days)
        if rng.random() < 0.05:
            quantity = int(quantity * rng.uniform(1.5, 2.5))
        records.append(
            DemandRecordORM(
                date=date,
                product_id=product_id,
                demand_quantity=max(quantity, 0),
            )
        )
    return records


def orm_to_product(orm: ProductORM) -> Product:
    """Convert ORM to Pydantic Product."""
    return Product(
        product_id=orm.product_id,
        name=orm.name,
        category=orm.category,
        unit_cost=orm.unit_cost,
        selling_price=orm.selling_price,
    )


def orm_to_supplier(orm: SupplierORM) -> Supplier:
    """Convert ORM to Pydantic Supplier."""
    return Supplier(
        supplier_id=orm.supplier_id,
        name=orm.name,
        product_ids=orm.product_ids,
        unit_price=orm.unit_price,
        capacity=orm.capacity,
        lead_time_days=orm.lead_time_days,
        reliability=orm.reliability,
        disruption_probability=orm.disruption_probability,
    )


def orm_to_warehouse(orm: WarehouseORM) -> Warehouse:
    """Convert ORM to Pydantic Warehouse."""
    return Warehouse(
        warehouse_id=orm.warehouse_id,
        location=orm.location,
        capacity=orm.capacity,
        current_inventory=orm.current_inventory,
    )


def orm_to_demand(orm: DemandRecordORM) -> DemandRecord:
    """Convert ORM to Pydantic DemandRecord."""
    return DemandRecord(
        date=orm.date,
        product_id=orm.product_id,
        demand_quantity=orm.demand_quantity,
    )


def orm_to_transport(orm: TransportOptionORM) -> TransportOption:
    """Convert ORM to Pydantic TransportOption."""
    return TransportOption(
        option_id=orm.option_id,
        mode=orm.mode,
        carrier=orm.carrier,
        cost_per_unit=orm.cost_per_unit,
        delivery_time_days=orm.delivery_time_days,
        capacity=orm.capacity,
        reliability=orm.reliability,
    )
