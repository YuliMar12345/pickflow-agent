"""Fase 3 de PICKFLOW-AGENT: pruebas del agente implementado en Fase 2.
Python 3.10+, solo biblioteca estándar. Ejecutar: python fase3_tests.py
"""
import csv, json, random, statistics, sys
from pathlib import Path
from datetime import datetime, timezone
from copy import deepcopy
from pickflow_agent import WarehouseEnvironment, PickflowAgent, JSONLLogger, Order, Picker

ROOT = Path(__file__).resolve().parent
OUT, LOGS = ROOT / "resultados", ROOT / "logs"
OUT.mkdir(exist_ok=True); LOGS.mkdir(exist_ok=True)
BASE_ORDERS = [
    Order("PED-001", ["A1", "B2"], 5),
    Order("PED-002", ["A2"], 3),
    Order("PED-003", ["B1", "C1"], 4),
    Order("PED-004", ["A1", "C1"], 2),
]
BASE_PICKERS = [Picker("OP-01", "A1"), Picker("OP-02", "B1")]
SCENARIOS = [
    ("S01", "Carga estándar", "normal"),
    ("S02", "Carga baja: un pedido", "limit"),
    ("S03", "Carga alta: seis pedidos", "normal"),
    ("S04", "Prioridad alta", "limit"),
    ("S05", "Prioridad baja", "limit"),
    ("S06", "Un operario disponible", "limit"),
    ("S07", "Ubicaciones repetidas", "limit"),
    ("S08", "Entorno adverso: mayor variabilidad de viaje", "adverse"),
    ("S09", "Falla esperada: ubicación inválida", "failure"),
    ("S10", "Falla esperada: sin operarios disponibles", "failure"),
]

def configure(sid, seed):
    env = WarehouseEnvironment(seed)
    env.orders = deepcopy(BASE_ORDERS)
    env.pickers = deepcopy(BASE_PICKERS)
    if sid == "S02": env.orders = [deepcopy(BASE_ORDERS[0])]
    elif sid == "S03":
        env.orders = deepcopy(BASE_ORDERS) + [Order("PED-005", ["A2", "C1"], 4), Order("PED-006", ["B2"], 1)]
    elif sid == "S04":
        for o in env.orders: o.priority = 5
    elif sid == "S05":
        for o in env.orders: o.priority = 1
    elif sid == "S06": env.pickers = [deepcopy(BASE_PICKERS[0])]
    elif sid == "S07": env.orders[0].items = ["A1", "A1", "C1"]
    elif sid == "S08":
        def high_variance(a, b, _env=env):
            x1,y1 = _env.locations[a]; x2,y2 = _env.locations[b]
            return max(0.25, abs(x1-x2)+abs(y1-y2)+_env.rng.uniform(0,1.5))
        env.travel_time = high_variance
    elif sid == "S09": env.orders[0].items = ["Z99"]
    elif sid == "S10": env.pickers = []
    return env

def baseline_fifo(seed, sid):
    """Línea base de comparación: atiende pedidos en orden de llegada y asigna al operario más cercano."""
    env = configure(sid, seed)
    if sid == "S09": return {"completed": 0, "total_minutes": None, "pending": len(env.orders), "error": "ubicación inválida no comparable"}
    if sid == "S10": return {"completed": 0, "total_minutes": 0.0, "pending": len(env.orders), "error": None}
    total = 0.0; completed = 0
    for order in env.orders:
        candidates = []
        for picker in env.pickers:
            try: dist = PickflowAgent.distance(picker.position, order.items, env.locations)
            except KeyError: continue
            candidates.append((dist, picker.picker_id, picker))
        if not candidates: break
        _, _, picker = min(candidates, key=lambda x:(x[0], x[1]))
        result = env.execute_assignment(order.order_id, picker.picker_id, order.items)
        total += result["total_minutes"]; completed += 1
    return {"completed": completed, "total_minutes": round(total, 4), "pending": len(env.orders)-completed, "error": None}

def run_one(sid, rep, seed):
    env = configure(sid, seed)
    log_path = LOGS / f"{sid}_rep{rep:02d}_seed{seed}.jsonl"
    run_id = f"{sid}-rep{rep:02d}-seed{seed}"
    logger = JSONLLogger(log_path, run_id, seed)
    agent = PickflowAgent(logger)
    started = datetime.now(timezone.utc).isoformat()
    error = None
    try:
        summary = agent.run(env)
        completed = summary["orders_completed"]
        total = summary["total_simulated_minutes"]
        pending = len(summary["pending_orders"])
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        logger.log("test_exception", {"exception_type":type(exc).__name__, "message":str(exc), "scenario":sid})
        completed = sum(o.status == "completed" for o in env.orders)
        pending = sum(o.status == "pending" for o in env.orders)
        total = round(agent.total_minutes, 4)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp_utc":datetime.now(timezone.utc).isoformat(),"run_id":run_id,"seed":seed,
                            "event":"test_evaluation","data":{"scenario":sid,"exception":error,
                            "completed":completed,"pending":pending}}, ensure_ascii=False)+"\n")
    return {"scenario_id":sid,"repetition":rep,"seed":seed,"started_utc":started,
            "completed":completed,"attempted":len(env.orders),"pending":pending,
            "total_minutes":total,"exception":error,"log_file":str(log_path.relative_to(ROOT)),
            "env":env}

def main():
    summary_rows=[]; details=[]
    for sid, name, kind in SCENARIOS:
        reps=[]
        for rep in range(1,6):
            seed=20261018 + int(sid[-2:])*100 + rep
            r=run_one(sid,rep,seed)
            baseline=baseline_fifo(seed,sid)
            r["scenario_name"]=name; r["kind"]=kind; r["baseline_completed"]=baseline["completed"]
            r["baseline_minutes"]=baseline["total_minutes"]
            if baseline["total_minutes"] not in (None,0) and r["total_minutes"] is not None:
                r["reduction_pct"]=(baseline["total_minutes"]-r["total_minutes"])/baseline["total_minutes"]*100
            else: r["reduction_pct"]=None
            reps.append(r); details.append({k:v for k,v in r.items() if k!="env"})
        if kind == "failure":
            if sid == "S09":
                # Existing implementation raises KeyError; this is recorded as a robustness defect, not a pass.
                pass_flags=[r["exception"] is None and r["pending"]==0 for r in reps]
                threshold="manejo controlado de ubicación inválida"
            else:
                pass_flags=[r["exception"] is None and r["completed"]==0 and r["pending"]==r["attempted"] for r in reps]
                threshold="no asignar pedidos si no hay operarios; registrar condición"
            summary_rows.append({"id":sid,"scenario":name,"repetitions":5,"completion_mean_pct":round(statistics.mean([r["completed"]/r["attempted"]*100 for r in reps]),2),
                "agent_time_mean_min":"N/A","agent_time_sd_min":"N/A","baseline_time_mean_min":"N/A",
                "reduction_mean_pct":"N/A","reduction_sd_pct":"N/A","acceptance_threshold":threshold,
                "pass":all(pass_flags),"notes":reps[0]["exception"] or "Sin excepción; pedidos permanecen pendientes"})
        else:
            comp=[r["completed"]/r["attempted"]*100 for r in reps]
            times=[r["total_minutes"] for r in reps]
            bases=[r["baseline_minutes"] for r in reps]
            reductions=[r["reduction_pct"] for r in reps if r["reduction_pct"] is not None]
            mean_comp=statistics.mean(comp); mean_time=statistics.mean(times); sd_time=statistics.stdev(times)
            mean_base=statistics.mean(bases); mean_red=statistics.mean(reductions); sd_red=statistics.stdev(reductions)
            # Two criteria reported separately: completion >=90%; original SMART goal reduction >=20%.
            complete_pass=mean_comp>=90
            reduction_pass=mean_red>=20
            summary_rows.append({"id":sid,"scenario":name,"repetitions":5,"completion_mean_pct":round(mean_comp,2),
                "agent_time_mean_min":round(mean_time,3),"agent_time_sd_min":round(sd_time,3),"baseline_time_mean_min":round(mean_base,3),
                "reduction_mean_pct":round(mean_red,2),"reduction_sd_pct":round(sd_red,2),
                "acceptance_threshold":"finalización >=90%; meta SMART de reducción >=20% evaluada aparte",
                "pass":complete_pass,"notes":f"meta_reduccion_20_cumple={reduction_pass}"})
    # Repeatability: same scenario and seed twice should yield same decisions/actions/times (timestamps excluded).
    a=run_one("S01",99,420042); b=run_one("S01",100,420042)
    def events(path):
        out=[]
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            x=json.loads(line)
            if x["event"] in ("decision","action","run_end"):
                out.append((x["event"],x["data"]))
        return out
    repeatable=events(ROOT/a["log_file"])==events(ROOT/b["log_file"])
    (OUT/"reproducibilidad.json").write_text(json.dumps({"same_seed":420042,"repeatable":repeatable,
        "runs":[a["log_file"],b["log_file"]]},indent=2,ensure_ascii=False),encoding="utf-8")
    with (OUT/"resumen_fase3.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(summary_rows[0])); w.writeheader(); w.writerows(summary_rows)
    with (OUT/"detalle_repeticiones.csv").open("w",newline="",encoding="utf-8-sig") as f:
        cols=[k for k in details[0] if k!="env"]
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(details)
    (OUT/"detalle_repeticiones.json").write_text(json.dumps(details,indent=2,ensure_ascii=False),encoding="utf-8")
    print("PICKFLOW-AGENT — Fase 3")
    print(f"Escenarios: {len(SCENARIOS)}; repeticiones por escenario: 5; ejecuciones: {len(details)}")
    print(f"Reproducibilidad con misma semilla: {'CUMPLE' if repeatable else 'NO CUMPLE'}")
    for r in summary_rows:
        if r["id"] in ("S09","S10"):
            print(f'{r["id"]} {r["scenario"]}: manejo de falla={"CUMPLE" if r["pass"] else "NO CUMPLE"}; {r["notes"]}')
        else:
            print(f'{r["id"]} {r["scenario"]}: completitud={r["completion_mean_pct"]:.1f}%; tiempo={r["agent_time_mean_min"]:.2f}±{r["agent_time_sd_min"]:.2f} min; reducción FIFO={r["reduction_mean_pct"]:.1f}±{r["reduction_sd_pct"]:.1f}%; meta 20%={"CUMPLE" if r["reduction_mean_pct"]>=20 else "NO CUMPLE"}')
    print("Resultados guardados en resultados/ y logs/.")

if __name__ == "__main__": main()
