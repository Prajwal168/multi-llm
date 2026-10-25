"""
Runs benchmark arms over the task set and appends one JSON line per
(arm, task, repeat) to <out>/results.jsonl. Resumable.

Examples
--------
# main comparison
python -m benchmark.run_benchmark --arms A B C D --repeats 5 --out benchmark/runs/main

# concurrency sweep (arm B, dependent tasks), one run dir per setting
python -m benchmark.run_benchmark --arms B --strata S3 --workers 2 --repeats 3 --out benchmark/runs/sweep-w2

# failure isolation (RQ4): garbled instruction in one independent branch
python -m benchmark.run_benchmark --arms A B C --strata S3 --fault component --out benchmark/runs/fault-component

# transport faults (Section IV-E)
python -m benchmark.run_benchmark --arms B --fault ddg_block --only S2-01 S2-03 S5-02 --out benchmark/runs/fault-ddg
python -m benchmark.run_benchmark --arms B --fault verifier_outage --fault-k 2 --out benchmark/runs/fault-verifier-k2
python -m benchmark.run_benchmark --arms B --fault verifier_outage --fault-k 4 --out benchmark/runs/fault-verifier-k4
"""

import argparse
import json
import time
import traceback
from pathlib import Path

from . import config, instrument
from .mem_sampler import MemSampler
from .tasks_io import load_tasks, describe


def preflight(arms):
    from ollama import Client
    need = {}
    if "A" in arms or any(a in arms for a in "BCD"):
        need[config.CONTROL_HOST] = {config.CONTROL_MODEL}
    if any(a in arms for a in "BD"):
        if not config.EXECUTOR_MODEL:
            raise SystemExit(
                "BENCH_EXECUTOR_MODEL is not set. Pin the exact tag from "
                "`ollama list` on the executor host (executor.py's default "
                "'qwen3.8:27b' looks like a typo).")
        need.setdefault(config.EXECUTOR_HOST, set()).add(config.EXECUTOR_MODEL)
    for host, models in need.items():
        listed = Client(host=host).list()
        names = set()
        for m in listed.models:
            n = getattr(m, "model", None)
            if n:
                names.add(n)
        for want in models:
            if want not in names and f"{want}:latest" not in names:
                raise SystemExit(f"Model '{want}' not found on {host}. Available: {sorted(names)}")
    print("Preflight OK.")


def make_outage_hook(k):
    import httpx
    state = {"n": 0}

    def hook(stage):
        if stage == "verifier.py" and state["n"] < k:
            state["n"] += 1
            return httpx.ConnectError("injected verifier outage")
        return None
    return hook


def build_runner(arm, workers):
    if arm == "A":
        from .baseline import Baseline
        return Baseline(config.CONTROL_HOST, config.CONTROL_MODEL,
                        config.BASELINE_TOP_K, config.BASELINE_NUM_PREDICT)
    from .pipeline_runner import FullPipeline
    if arm == "B":
        return FullPipeline(config.EXECUTOR_HOST, config.EXECUTOR_MODEL, workers, gate=True)
    if arm == "C":
        return FullPipeline(config.CONTROL_HOST, config.CONTROL_MODEL, workers, gate=True)
    if arm == "D":
        return FullPipeline(config.EXECUTOR_HOST, config.EXECUTOR_MODEL, workers, gate=False)
    raise ValueError(arm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="benchmark/tasks/tasks.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--arms", nargs="+", default=["A", "B", "C", "D"])
    ap.add_argument("--strata", nargs="+", default=None)
    ap.add_argument("--only", nargs="+", default=None, help="task ids")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--workers", type=int, default=1,
                    help="the single shared max-concurrency setting (paper III-D)")
    ap.add_argument("--fault", choices=["component", "ddg_block", "verifier_outage"], default=None)
    ap.add_argument("--fault-k", type=int, default=2, help="verifier_outage: calls to fail per run")
    ap.add_argument("--skip-preflight", action="store_true")
    args = ap.parse_args()

    tasks = load_tasks(args.tasks)
    print("Task set:", describe(tasks))
    if args.strata:
        tasks = [t for t in tasks if t["stratum"] in args.strata]
    if args.only:
        tasks = [t for t in tasks if t["id"] in args.only]
    if args.fault == "component":
        tasks = [t for t in tasks if "fault_query" in t]
    if not tasks:
        raise SystemExit("No tasks selected.")

    if not args.skip_preflight:
        preflight(args.arms)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    results_path = out / "results.jsonl"

    done = set()
    if results_path.exists():
        for line in results_path.open(encoding="utf-8"):
            if line.strip():
                done.add(json.loads(line)["run_id"])

    instrument.install_llm()
    instrument.install_web(out / "web_snapshots")
    if args.fault == "ddg_block":
        instrument.WEB_FAULTS.add("ddg")

    sampler = MemSampler({"control": config.CONTROL_HOST, "executor": config.EXECUTOR_HOST},
                         out / "mem_samples.jsonl")
    sampler.start()

    try:
        for arm in args.arms:
            runner = build_runner(arm, args.workers)
            for repeat in range(args.repeats):
                for task in tasks:
                    fault = args.fault or "none"
                    run_id = f"{arm}|{task['id']}|{repeat}|{fault}|w{args.workers}"
                    if run_id in done:
                        continue
                    query = task["fault_query"] if args.fault == "component" else task["query"]

                    instrument.reset()
                    instrument.fault_hook = (make_outage_hook(args.fault_k)
                                             if args.fault == "verifier_outage" else None)
                    rec = {
                        "run_id": run_id, "arm": arm, "task_id": task["id"],
                        "stratum": task["stratum"], "repeat": repeat,
                        "workers": args.workers, "fault": fault,
                        "fault_k": args.fault_k if args.fault == "verifier_outage" else None,
                        "query": query,
                        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    }
                    t0 = time.monotonic()
                    try:
                        rec.update(runner.run(query))
                        rec["error"] = None
                    except Exception as exc:
                        rec["error"] = f"{type(exc).__name__}: {exc}"
                        rec["traceback"] = traceback.format_exc()[-2000:]
                    rec["wall_seconds"] = round(time.monotonic() - t0, 3)
                    rec["calls"], rec["web"] = instrument.snapshot()

                    with results_path.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    print(f"[{run_id}] {rec['wall_seconds']}s error={rec['error']}")
    finally:
        instrument.fault_hook = None
        sampler.stop()


if __name__ == "__main__":
    main()
