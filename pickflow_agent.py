"""PICKFLOW-AGENT: simulador de picking reproducible; Python 3.10+, sin dependencias externas."""
import argparse, json, random
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

@dataclass
class Order:
    order_id: str
    items: list
    priority: int
    status: str = "pending"

@dataclass
class Picker:
    picker_id: str
    position: str
    available: bool = True

class WarehouseEnvironment:
    """Entorno estocástico: tiempo de viaje con variación aleatoria reproducible."""
    def __init__(self, seed=42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.locations = {"A1": (0,0), "A2": (1,0), "B1": (0,1), "B2": (1,1), "C1": (2,1)}
        self.orders = [
            Order("PED-001", ["A1","B2"], 5),
            Order("PED-002", ["A2"], 3),
            Order("PED-003", ["B1","C1"], 4),
            Order("PED-004", ["A1","C1"], 2),
        ]
        self.pickers = [Picker("OP-01","A1"), Picker("OP-02","B1")]
        self.elapsed_minutes = 0.0

    def perceive(self):
        return {
            "pending_orders": [asdict(o) for o in self.orders if o.status == "pending"],
            "available_pickers": [asdict(p) for p in self.pickers if p.available],
            "locations": self.locations,
            "elapsed_minutes": round(self.elapsed_minutes, 2)
        }

    def travel_time(self, a, b):
        x1,y1 = self.locations[a]; x2,y2 = self.locations[b]
        return max(0.25, abs(x1-x2)+abs(y1-y2)+self.rng.uniform(0,0.5))

    def execute_assignment(self, order_id, picker_id, route):
        order = next(o for o in self.orders if o.order_id == order_id)
        picker = next(p for p in self.pickers if p.picker_id == picker_id)
        current, travel = picker.position, 0.0
        for target in route:
            travel += self.travel_time(current, target)
            current = target
        picking = 0.75 * len(route)
        total = travel + picking
        self.elapsed_minutes += total
        picker.position = current
        order.status = "completed"
        return {"order_id":order_id, "picker_id":picker_id, "route":route,
                "travel_minutes":round(travel,2), "picking_minutes":round(picking,2),
                "total_minutes":round(total,2), "new_picker_position":current,
                "order_status":"completed"}

class JSONLLogger:
    def __init__(self, path, run_id, seed):
        self.path, self.run_id, self.seed = Path(path), run_id, seed
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
    def log(self, event, data):
        record = {"timestamp_utc":datetime.now(timezone.utc).isoformat(),
                  "run_id":self.run_id, "seed":self.seed, "event":event, "data":data}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False)+"\n")

class PickflowAgent:
    """Agente basado en utilidad con planificación voraz."""
    def __init__(self, logger):
        self.logger, self.completed, self.total_minutes = logger, 0, 0.0
        self.experience = {}

    @staticmethod
    def distance(origin, route, locations):
        current, total = origin, 0
        for target in route:
            x1,y1 = locations[current]; x2,y2 = locations[target]
            total += abs(x1-x2)+abs(y1-y2)
            current = target
        return total

    def decide(self, perception):
        orders, pickers = perception["pending_orders"], perception["available_pickers"]
        if not orders or not pickers:
            self.logger.log("decision", {"result":"stop", "reason":"sin pedidos u operarios"})
            return None
        candidates = []
        for order in orders:
            route = order["items"]
            for picker in pickers:
                dist = self.distance(picker["position"], route, perception["locations"])
                utility = 10*order["priority"] - 2*dist
                candidates.append((utility, order, picker, route, dist))
        candidates.sort(key=lambda c:(-c[0],-c[1]["priority"],c[1]["order_id"],c[2]["picker_id"]))
        utility, order, picker, route, dist = candidates[0]
        decision = {"order_id":order["order_id"], "picker_id":picker["picker_id"],
                    "route":route, "estimated_manhattan_distance":dist,
                    "priority":order["priority"], "utility":utility,
                    "rule":"maximizar 10*prioridad - 2*distancia estimada"}
        self.logger.log("decision", decision)
        return decision

    def act(self, env, decision):
        result = env.execute_assignment(decision["order_id"], decision["picker_id"], decision["route"])
        self.logger.log("action", result)
        self.completed += 1
        self.total_minutes += result["total_minutes"]
        key = str(decision["priority"])
        self.experience[key] = self.experience.get(key,0)+1
        self.logger.log("learning_update", {"completed_orders":self.completed,
                          "completed_by_priority":self.experience,
                          "note":"se registra experiencia; no modifica la política en esta versión"})
        return result

    def run(self, env):
        self.logger.log("run_start", {"environment":"warehouse_simulator",
                       "environment_stochastic":True, "seed":env.seed,
                       "agent_type":"utility-based with greedy planning"})
        while True:
            perception = env.perceive()
            self.logger.log("perception", perception)
            decision = self.decide(perception)
            if decision is None: break
            self.act(env, decision)
        summary = {"orders_completed":self.completed,
                   "total_simulated_minutes":round(self.total_minutes,2),
                   "average_minutes_per_order":round(self.total_minutes/self.completed,2) if self.completed else 0,
                   "experience_by_priority":self.experience,
                   "pending_orders":[o.order_id for o in env.orders if o.status=="pending"]}
        self.logger.log("run_end", summary)
        return summary

def main():
    parser = argparse.ArgumentParser(description="Ejecutar PICKFLOW-AGENT")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--log", type=Path, default=Path("logs/pickflow_log.jsonl"))
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime("pickflow-%Y%m%dT%H%M%SZ")
    env = WarehouseEnvironment(args.seed)
    logger = JSONLLogger(args.log, run_id, args.seed)
    summary = PickflowAgent(logger).run(env)
    print("PICKFLOW-AGENT: ejecución finalizada")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Registro guardado en: {args.log}")

if __name__ == "__main__":
    main()
