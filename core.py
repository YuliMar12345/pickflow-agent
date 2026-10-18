"""Lógica de la app de PICKFLOW-AGENT (sin Streamlit, para poder probarla por separado).

Reutiliza SIN cambios el agente (pickflow_agent.py) y los escenarios/pruebas de la Fase 3
(fase3_tests.py), de modo que lo que muestra la web es lo mismo que se evaluó en el documento.
"""
import contextlib, csv, io, json, math
from pathlib import Path

import fase3_tests as f3

ROOT = Path(__file__).resolve().parent
REF_CSV = ROOT / "referencia" / "resumen_fase3_documento.csv"

SCENARIO_INFO = {sid: (name, kind) for sid, name, kind in f3.SCENARIOS}
KIND_LABEL = {"normal": "Normal", "limit": "Caso límite", "adverse": "Adverso", "failure": "Falla esperada"}


def read_log(log_file):
    path = ROOT / log_file
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def run_scenario(sid, seed):
    """Ejecuta el agente desde cero en un escenario y devuelve todo lo necesario para mostrarlo."""
    r = f3.run_one(sid, 0, seed)          # rep 00 = ejecuciones hechas desde la web
    base = f3.baseline_fifo(seed, sid)
    events = read_log(r["log_file"])
    steps, cum = [], 0.0
    pending_decision = None
    for e in events:
        if e["event"] == "decision" and "order_id" in e["data"]:
            pending_decision = e["data"]
        elif e["event"] == "action":
            d, cum = e["data"], cum + e["data"]["total_minutes"]
            steps.append({
                "Paso": len(steps) + 1, "Pedido": d["order_id"], "Operario": d["picker_id"],
                "Ruta": " → ".join(d["route"]),
                "Utilidad": pending_decision["utility"] if pending_decision else None,
                "Viaje (min)": d["travel_minutes"], "Picking (min)": d["picking_minutes"],
                "Total (min)": d["total_minutes"], "Acumulado (min)": round(cum, 2),
            })
    reduction = None
    if base["total_minutes"] not in (None, 0) and r["total_minutes"] is not None and r["exception"] is None:
        reduction = (base["total_minutes"] - r["total_minutes"]) / base["total_minutes"] * 100
    stop = next((e["data"] for e in events if e["event"] == "decision" and e["data"].get("result") == "stop"), None)
    return {
        "scenario_id": sid, "scenario_name": SCENARIO_INFO[sid][0], "kind": SCENARIO_INFO[sid][1],
        "seed": seed, "exception": r["exception"], "completed": r["completed"],
        "attempted": r["attempted"], "pending": r["pending"], "total_minutes": r["total_minutes"],
        "baseline_minutes": base["total_minutes"], "reduction_pct": reduction,
        "steps": steps, "events": events, "stop_reason": stop, "log_file": r["log_file"],
        "log_text": (ROOT / r["log_file"]).read_text(encoding="utf-8"),
    }


def run_all_tests():
    """Ejecuta las 50 pruebas (10 escenarios x 5 repeticiones) + reproducibilidad, de cero."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        f3.main()
    rows = list(csv.DictReader((ROOT / "resultados" / "resumen_fase3.csv").open(encoding="utf-8-sig")))
    repro = json.loads((ROOT / "resultados" / "reproducibilidad.json").read_text(encoding="utf-8"))
    return {"rows": rows, "repro": repro, "stdout": buf.getvalue()}


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def compare_with_document(rows):
    """Compara los valores recién calculados con los publicados en el documento (Fase 3)."""
    ref = {r["id"]: r for r in csv.DictReader(REF_CSV.open(encoding="utf-8-sig"))}
    out = []
    for r in rows:
        ok = True
        for col in ("completion_mean_pct", "agent_time_mean_min", "agent_time_sd_min",
                    "baseline_time_mean_min", "reduction_mean_pct", "reduction_sd_pct"):
            a, b = _num(r[col]), _num(ref[r["id"]][col])
            if (a is None) != (b is None) or (a is not None and not math.isclose(a, b, abs_tol=1e-9)):
                ok = False
        ok = ok and (r["pass"] == ref[r["id"]]["pass"])
        out.append(ok)
    return out
