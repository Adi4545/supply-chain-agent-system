const API = window.location.origin;

let currentRunId = null;

async function runPlan() {
  const btn = document.getElementById("runPlanBtn");
  btn.disabled = true;
  btn.textContent = "Running...";

  try {
    const res = await fetch(`${API}/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        objective: "Plan replenishment for product P001",
        product_id: "P001",
      }),
    });
    const data = await res.json();
    currentRunId = data.run_id;
    document.getElementById("disruptBtn").disabled = false;
    renderPlan(data);
    await loadSuppliers();
  } catch (err) {
    document.getElementById("finalDecision").textContent = "Error: " + err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Run Planning Pipeline";
  }
}

function renderPlan(data) {
  const d = data.final_decision;
  if (!d) return;

  document.getElementById("kpiInventory").textContent = "3,500";
  document.getElementById("kpiDemand").textContent = "—";
  document.getElementById("kpiReorder").textContent = d.order_quantity.toLocaleString();
  document.getElementById("kpiCost").textContent = "$" + d.expected_cost.toLocaleString(undefined, { maximumFractionDigits: 0 });
  document.getElementById("kpiRisk").textContent = d.risk_level;
  document.getElementById("kpiDelivery").textContent = d.expected_delivery_days + " days";

  const badge = document.getElementById("decisionBadge");
  badge.textContent = "Requires Human Approval";
  badge.className = "badge approval";

  document.getElementById("finalDecision").innerHTML = `
    <p><strong>${d.decision}</strong></p>
    <p>${d.reasoning_summary}</p>
    <p>Transport: ${d.transportation} | Confidence: ${(d.confidence * 100).toFixed(0)}%</p>
    ${d.revision_reason ? `<p>Revision: ${d.revision_reason}</p>` : ""}
  `;
  document.getElementById("trace").textContent = data.trace_summary;
}

async function loadSuppliers() {
  const res = await fetch(`${API}/suppliers?product_id=P001`);
  const suppliers = await res.json();
  const tbody = document.querySelector("#supplierTable tbody");
  tbody.innerHTML = suppliers.map(s => `
    <tr>
      <td>${s.name}</td>
      <td>$${s.unit_price}</td>
      <td>${s.lead_time_days} days</td>
      <td>${s.capacity.toLocaleString()}</td>
      <td>${(s.reliability * 100).toFixed(0)}%</td>
    </tr>
  `).join("");
}

async function applyDisruption() {
  if (!currentRunId) return;
  const type = document.getElementById("disruptionType").value;
  const btn = document.getElementById("disruptBtn");
  btn.disabled = true;

  try {
    const res = await fetch(`${API}/simulate-disruption`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        run_id: currentRunId,
        disruption: { disruption_type: type, description: `Simulated ${type}` },
      }),
    });
    const data = await res.json();
    renderPlan(data);
  } catch (err) {
    alert("Disruption failed: " + err.message);
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("runPlanBtn").addEventListener("click", runPlan);
document.getElementById("disruptBtn").addEventListener("click", applyDisruption);
loadSuppliers();
