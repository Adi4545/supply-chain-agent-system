"""OR-Tools mixed-integer optimization engine for supply chain planning."""

from __future__ import annotations

from pydantic import BaseModel, Field

from models.schemas import RiskLevel, Supplier, SupplierAllocation, TransportOption


class OptimizationInput(BaseModel):
    """Input to the optimization engine."""

    product_id: str
    demand: int = Field(ge=0)
    current_inventory: int = Field(ge=0)
    safety_stock: int = Field(ge=0)
    reorder_quantity: int = Field(ge=0)
    suppliers: list[Supplier]
    transport_options: list[TransportOption]
    selected_transport_id: str | None = None
    supplier_risk: float = Field(default=0.3, ge=0, le=1)
    transport_risk: float = Field(default=0.2, ge=0, le=1)
    budget: float | None = None
    delivery_deadline_days: int | None = None
    warehouse_capacity: int | None = None
    holding_cost_rate: float = 0.02
    stockout_penalty: float = 50.0
    risk_penalty_multiplier: float = 1000.0


class CostBreakdown(BaseModel):
    """Detailed cost components."""

    procurement_cost: float = 0.0
    transport_cost: float = 0.0
    holding_cost: float = 0.0
    stockout_penalty: float = 0.0
    risk_penalty: float = 0.0
    total_cost: float = 0.0


class OptimizationResult(BaseModel):
    """Output from the optimization solver."""

    feasible: bool
    supplier_allocation: list[SupplierAllocation] = Field(default_factory=list)
    selected_transport_id: str = ""
    transport_mode: str = ""
    total_cost: float = 0.0
    cost_breakdown: CostBreakdown = Field(default_factory=CostBreakdown)
    expected_delivery_days: int = 0
    risk_level: RiskLevel = RiskLevel.MEDIUM
    infeasibility_reasons: list[str] = Field(default_factory=list)
    stockout_units: int = 0


def optimize(inp: OptimizationInput) -> OptimizationResult:
    """Solve supply chain allocation using OR-Tools MILP."""
    from ortools.linear_solver import pywraplp

    reasons: list[str] = []

    if not inp.suppliers:
        return OptimizationResult(
            feasible=False,
            infeasibility_reasons=["No suppliers available"],
        )

    if inp.reorder_quantity <= 0:
        return OptimizationResult(
            feasible=True,
            supplier_allocation=[],
            total_cost=0.0,
            cost_breakdown=CostBreakdown(),
            expected_delivery_days=0,
            risk_level=RiskLevel.LOW,
        )

    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        return OptimizationResult(
            feasible=False,
            infeasibility_reasons=["OR-Tools SCIP solver unavailable"],
        )

    # Decision variables: quantity from each supplier
    qty_vars: dict[str, pywraplp.Variable] = {}
    for s in inp.suppliers:
        qty_vars[s.supplier_id] = solver.IntVar(0, s.capacity, f"qty_{s.supplier_id}")

    # Transport selection (binary)
    transport = next(
        (t for t in inp.transport_options if t.option_id == inp.selected_transport_id),
        inp.transport_options[0] if inp.transport_options else None,
    )
    if transport is None:
        return OptimizationResult(
            feasible=False,
            infeasibility_reasons=["No transport options available"],
        )

    # Slack for unmet demand (stockout)
    stockout_var = solver.IntVar(0, inp.demand, "stockout")

    # Constraint: total supply + current inventory + stockout >= demand + safety_stock
    total_supply = solver.Sum(list(qty_vars.values()))
    solver.Add(
        total_supply + inp.current_inventory + stockout_var >= inp.demand + inp.safety_stock
    )

    # Constraint: meet reorder quantity target
    solver.Add(total_supply >= inp.reorder_quantity)

    # Supplier capacity constraints (already in variable bounds)

    # Warehouse capacity
    if inp.warehouse_capacity is not None:
        new_total = inp.current_inventory + total_supply
        if new_total > inp.warehouse_capacity:
            solver.Add(total_supply <= inp.warehouse_capacity - inp.current_inventory)

    # Budget constraint
    if inp.budget is not None:
        procurement_expr = solver.Sum(
            qty_vars[s.supplier_id] * s.unit_price for s in inp.suppliers
        )
        transport_expr = total_supply * transport.cost_per_unit
        solver.Add(procurement_expr + transport_expr <= inp.budget)

    # Delivery deadline: prefer suppliers meeting deadline
    if inp.delivery_deadline_days is not None:
        for s in inp.suppliers:
            total_days = s.lead_time_days + transport.delivery_time_days
            if total_days > inp.delivery_deadline_days:
                # Soft constraint: penalize but don't hard block
                pass

    # Objective: minimize cost
    procurement_cost = solver.Sum(
        qty_vars[s.supplier_id] * s.unit_price for s in inp.suppliers
    )
    transport_cost = total_supply * transport.cost_per_unit
    holding_cost = total_supply * inp.holding_cost_rate
    stockout_cost = stockout_var * inp.stockout_penalty
    risk_cost = (inp.supplier_risk + inp.transport_risk) * inp.risk_penalty_multiplier

    solver.Minimize(procurement_cost + transport_cost + holding_cost + stockout_cost + risk_cost)

    status = solver.Solve()

    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        # Diagnose infeasibility
        if inp.budget is not None:
            min_cost = min(s.unit_price for s in inp.suppliers) * inp.reorder_quantity
            if min_cost > inp.budget:
                reasons.append(f"Budget {inp.budget} insufficient; min cost ~{min_cost:.0f}")
        if inp.warehouse_capacity is not None:
            if inp.current_inventory + inp.reorder_quantity > inp.warehouse_capacity:
                reasons.append("Warehouse capacity exceeded")
        if not reasons:
            reasons.append("Solver could not find feasible solution")
        return OptimizationResult(feasible=False, infeasibility_reasons=reasons)

    # Extract solution
    allocation: list[SupplierAllocation] = []
    total_procurement = 0.0
    max_delivery = 0

    for s in inp.suppliers:
        qty = int(qty_vars[s.supplier_id].solution_value())
        if qty > 0:
            delivery_days = s.lead_time_days + transport.delivery_time_days
            max_delivery = max(max_delivery, delivery_days)
            cost = qty * s.unit_price
            total_procurement += cost
            allocation.append(
                SupplierAllocation(
                    supplier_id=s.supplier_id,
                    quantity=qty,
                    unit_price=s.unit_price,
                    expected_delivery_days=delivery_days,
                )
            )

    total_qty = sum(a.quantity for a in allocation)
    total_transport = total_qty * transport.cost_per_unit
    total_holding = total_qty * inp.holding_cost_rate
    stockout_units = int(stockout_var.solution_value())
    total_stockout_pen = stockout_units * inp.stockout_penalty
    total_risk_pen = (inp.supplier_risk + inp.transport_risk) * inp.risk_penalty_multiplier
    grand_total = (
        total_procurement + total_transport + total_holding + total_stockout_pen + total_risk_pen
    )

    overall_risk = (inp.supplier_risk + inp.transport_risk) / 2
    if overall_risk < 0.25:
        risk_level = RiskLevel.LOW
    elif overall_risk < 0.5:
        risk_level = RiskLevel.MEDIUM
    elif overall_risk < 0.75:
        risk_level = RiskLevel.HIGH
    else:
        risk_level = RiskLevel.CRITICAL

    return OptimizationResult(
        feasible=True,
        supplier_allocation=allocation,
        selected_transport_id=transport.option_id,
        transport_mode=transport.mode,
        total_cost=round(grand_total, 2),
        cost_breakdown=CostBreakdown(
            procurement_cost=round(total_procurement, 2),
            transport_cost=round(total_transport, 2),
            holding_cost=round(total_holding, 2),
            stockout_penalty=round(total_stockout_pen, 2),
            risk_penalty=round(total_risk_pen, 2),
            total_cost=round(grand_total, 2),
        ),
        expected_delivery_days=max_delivery,
        risk_level=risk_level,
        stockout_units=stockout_units,
    )
