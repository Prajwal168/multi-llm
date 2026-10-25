"""
Offline self-test of the harness's own logic (annotation export,
metrics, stats) using synthetic data. Needs no Ollama, no project code.

    python -m benchmark.selftest
"""

import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

from . import annotate
from .tasks_io import load_tasks

TASKS = "benchmark/tasks/tasks.json"


def fake_call(stage, ptok=100, ctok=200, err=None):
    return {"stage": stage, "model": "m", "prompt_tokens": ptok, "completion_tokens": ctok,
            "seconds": 1.0, "error": err}


def fake_record(task, arm, repeat, rng, fault="none"):
    base = {"run_id": f"{arm}|{task['id']}|{repeat}|{fault}|w1", "arm": arm, "task_id": task["id"],
            "stratum": task["stratum"], "repeat": repeat, "workers": 1, "fault": fault,
            "query": task.get("fault_query") if fault == "component" else task["query"],
            "wall_seconds": 5.0, "error": None, "web": []}
    if arm == "A":
        base.update(plan=[g["text"] for g in task["gold_subtasks"][:-1]], answer="ans",
                    self_validation={"status": "passed", "reason": "ok"},
                    contexts=[{"source": "doc.pdf", "source_type": "local", "content": "c", "score": .3}],
                    timings={"total": 8.0}, calls=[fake_call("baseline.py")])
    else:
        n = len(task["gold_subtasks"])
        base.update(
            plan=[{"task_id": i + 1, "task": g["text"], "type": "concept", "priority": "high",
                   "depends_on": [], "retrieval": {"required": True}}
                  for i, g in enumerate(task["gold_subtasks"])],
            retrieval=[{"task_id": i + 1, "planned_source": "static", "actual_source": "static",
                        "contexts": [{"source": "doc.pdf", "source_type": "local", "content": "c", "score": .2},
                                     {"source": "http://x.org", "source_type": "web", "content": "w", "score": .3}]}
                       for i in range(n)],
            results=[{"task_id": i + 1, "task": "t", "type": "concept", "depends_on": [],
                      "output": "out", "status": rng.choice(["passed", "passed", "failed"]),
                      "reason": "r", "attempts": rng.choice([1, 2])} for i in range(n)],
            timings={"total": 20.0, "mediator": 2.0},
            calls=[fake_call("mediator.py"), fake_call("executor.py"),
                   fake_call("verifier.py", err="ConnectError: injected" if repeat == 0 else None)])
    return base


def main():
    rng = random.Random(1)
    tasks = load_tasks(TASKS)
    tmp = Path(tempfile.mkdtemp())
    main_dir, fault_dir = tmp / "main", tmp / "fault"
    for d in (main_dir, fault_dir):
        d.mkdir()

    with open(main_dir / "results.jsonl", "w") as f:
        for arm in "ABCD":
            for t in tasks:
                for rep in range(2):
                    f.write(json.dumps(fake_record(t, arm, rep, rng)) + "\n")
    with open(fault_dir / "results.jsonl", "w") as f:
        for arm in "AB":
            for t in [t for t in tasks if "fault_query" in t]:
                f.write(json.dumps(fake_record(t, arm, 0, rng, fault="component")) + "\n")

    for d in (main_dir, fault_dir):
        annotate.export(d, TASKS)

    # "annotate" randomly
    for d in (main_dir, fault_dir):
        ann = d / "annotation"
        for name, cols in (("tda", ["covered"]), ("rrp", ["relevant"]),
                           ("tsr", ["content_ok", "evidence_ok", "format_ok"]),
                           ("isolation", ["survived"])):
            p = ann / f"{name}_sheet.csv"
            if not p.exists():
                continue
            df = pd.read_csv(p)
            for c in cols:
                df[c] = [rng.choice([0, 1, 1]) for _ in range(len(df))]
            if name == "tda":
                df["covered"] = df["covered"].where(df["system_plan"].notna(), 0)
            df.to_csv(ann / f"{name}_sheet_annotated.csv", index=False)

    # synthetic defect eval
    dpath = tmp / "eval.jsonl"
    with open(dpath, "w") as f:
        for i in range(30):
            for ev, p in (("verifier", .75), ("self_eval", .3)):
                f.write(json.dumps({"defect_id": f"D{i}", "defect_type": ["factual_error", "incomplete"][i % 2],
                                    "task_id": "S1-01", "evaluator": ev,
                                    "status": "failed" if rng.random() < p else "passed", "reason": "r"}) + "\n")

    r = subprocess.run([sys.executable, "-m", "benchmark.metrics", "--run", str(main_dir),
                        "--run", str(fault_dir), "--defects-eval", str(dpath),
                        "--study-dir", str(tmp / "none"), "--out", str(tmp / "out")],
                       capture_output=True, text=True)
    print(r.stdout[-3500:])
    if r.returncode:
        print(r.stderr)
        raise SystemExit("SELFTEST FAILED")
    print("SELFTEST OK ->", tmp / "out")


if __name__ == "__main__":
    main()
