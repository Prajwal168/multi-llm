"""
Headless runner for the full pipeline (arms B, C, D).

Mirrors main.py step for step (mediator -> planner -> source selector ->
retrieval manager -> context builder -> executor.execute_stream) but
in-process, with timing and provenance captured. The human approval
checkpoint is auto-approved here and logged; its real effect (plan
rejection rate) is measured in the user study, not in this harness.

Place the benchmark/ folder in the project root, next to main.py, so
these imports resolve exactly as they do in main.py.
"""

import time

REQUIRED_KEYS = ("task_id", "task", "type", "priority", "depends_on", "retrieval")


def _plan_ok(t):
    """Same contract main.py's TaskItem enforces (else the API returns 422)."""
    if not isinstance(t, dict) or any(k not in t for k in REQUIRED_KEYS):
        return False
    if not isinstance(t["retrieval"], dict) or "required" not in t["retrieval"]:
        return False
    return isinstance(t["depends_on"], list)


def _source_type(src):
    return "web" if str(src or "").startswith("http") else "local"


class FullPipeline:

    def __init__(self, executor_host, executor_model, workers=1,
                 gate=True, max_retries=1):
        from dotenv import load_dotenv
        load_dotenv()

        from backend.mediator.mediator import generate_tasks
        from retrieval.planner import RetrievalPlanner
        from retrieval.source_selector import SourceSelector
        from retrieval.retrieval_manager import RetrievalManager
        from retrieval.context_builder import ContextBuilder
        from execution.executor import Executor

        self._generate = generate_tasks
        self.planner = RetrievalPlanner(max_workers=workers)
        self.selector = SourceSelector()
        self.manager = RetrievalManager(verifier_max_workers=workers)
        if not gate:
            # Arm D: accept any static result that cleared the distance
            # threshold (embedding similarity alone).
            self.manager.retrieval_verifier.verify_batch = (
                lambda pairs: [{"relevant": True, "reason": "gate_off"}
                               for _ in pairs])
        self.builder = ContextBuilder()
        self.executor = Executor(
            host=executor_host, model=executor_model,
            max_retries=max_retries, max_workers=workers)

    def run(self, query):
        rec = {"approved": None, "plan": [], "timings": {}}
        T = rec["timings"]
        t_all = time.monotonic()

        t = time.monotonic()
        plan = self._generate(query)
        T["mediator"] = round(time.monotonic() - t, 3)

        if not isinstance(plan, list):
            rec["plan_error"] = str(plan)[:500]
            T["total"] = round(time.monotonic() - t_all, 3)
            return rec
        if not all(_plan_ok(p) for p in plan):
            rec["plan_error"] = "plan failed TaskItem-style validation"
            rec["plan"] = plan
            T["total"] = round(time.monotonic() - t_all, 3)
            return rec

        rec["plan"] = plan
        rec["approved"] = True   # headless: checkpoint auto-approved

        t = time.monotonic()
        retrieval_plan = self.planner.create_plan(plan)
        T["retrieval_planner"] = round(time.monotonic() - t, 3)

        t = time.monotonic()
        routed = self.selector.select_source(retrieval_plan)
        T["source_selector"] = round(time.monotonic() - t, 3)

        t = time.monotonic()
        results = self.manager.retrieve(routed)
        T["retrieval_manager"] = round(time.monotonic() - t, 3)

        t = time.monotonic()
        packages = self.builder.build(plan, results, raw_query=query)
        T["context_builder"] = round(time.monotonic() - t, 3)

        routed_by_id = {r["task_id"]: r for r in routed}
        rec["retrieval"] = [{
            "task_id": r["task_id"],
            "planned_source": routed_by_id.get(r["task_id"], {}).get("retrieval_source"),
            "actual_source": r.get("retrieval_source"),
            "static_rejected_reason": r.get("static_rejected_reason"),
            "verification_reason": r.get("verification_reason"),
            "contexts": [{
                "source": c.get("source"),
                "source_type": _source_type(c.get("source")),
                "content": c.get("content"),
                "score": c.get("score"),
            } for c in r.get("retrieved_context", [])],
        } for r in results]

        t_exec = time.monotonic()
        events, final = [], []
        for ev in self.executor.execute_stream(packages):
            if ev["type"] == "done":
                final = ev["results"]
            else:
                events.append({
                    "t": round(time.monotonic() - t_exec, 3),
                    "type": ev["type"],
                    "task_id": ev.get("task_id"),
                    "status": ev.get("status"),
                })
        T["execution"] = round(time.monotonic() - t_exec, 3)
        T["total"] = round(time.monotonic() - t_all, 3)

        rec["events"] = events
        rec["results"] = final
        return rec
