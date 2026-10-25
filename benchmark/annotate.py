"""
Exports the human-annotation sheets the paper's metrics need.

    python -m benchmark.annotate --run benchmark/runs/main --tasks benchmark/tasks/tasks.json

Writes, into <run>/annotation/:
  tda_sheet.csv        one row per gold subtask per run   -> fill `covered` (0/1)
  rrp_sheet.csv        one row per passage delivered      -> fill `relevant` (0/1)
  tsr_sheet.csv        one row per run                    -> fill content_ok / evidence_ok / format_ok (0/1)
                       (verification_ok is pre-filled from system statuses)
  isolation_sheet.csv  (fault runs only) one row per non-faulted, independent gold subtask -> fill `survived` (0/1)

Annotators should be blind to the arm: sort/shuffle by `blind_id`
and hide the `arm` column while labeling.

After labeling, save as *_annotated.csv in the same folder (metrics.py reads those).
"""

import argparse
import csv
import json
import random
from pathlib import Path

from .tasks_io import load_tasks


def _load(run_dir):
    p = Path(run_dir) / "results.jsonl"
    return [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]


def plan_texts(rec):
    if rec["arm"] == "A":
        return [str(x) for x in rec.get("plan", [])]
    return [t.get("task", "") for t in rec.get("plan", []) if isinstance(t, dict)]


def delivered_passages(rec):
    """Every passage that reached generation, with the subtask it was for."""
    if rec["arm"] == "A":
        return [("request-level", rec["query"], c) for c in rec.get("contexts", [])]
    task_text = {t["task_id"]: t["task"] for t in rec.get("plan", []) if isinstance(t, dict)}
    rows = []
    for r in rec.get("retrieval", []):
        for c in r.get("contexts", []):
            rows.append((r["task_id"], task_text.get(r["task_id"], ""), c))
    return rows


def final_text(rec):
    if rec["arm"] == "A":
        return rec.get("answer", "")
    return "\n\n".join(f"### Task {r['task_id']} [{r['status']}]\n{r['output']}"
                       for r in rec.get("results", []))


def descendants(gold, root):
    kids = {g["id"]: [] for g in gold}
    for g in gold:
        for d in g["depends_on"]:
            kids[d].append(g["id"])
    seen, stack = set(), [root]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(kids.get(n, []))
    return seen


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def export(run_dir, tasks_path, seed=0):
    tasks = {t["id"]: t for t in load_tasks(tasks_path)}
    recs = _load(run_dir)
    rng = random.Random(seed)
    blind = {}

    def bid(rec):
        if rec["run_id"] not in blind:
            blind[rec["run_id"]] = f"R{len(blind) + 1:05d}"
        return blind[rec["run_id"]]

    tda, rrp, tsr, iso = [], [], [], []
    for rec in recs:
        task = tasks[rec["task_id"]]
        base = {"blind_id": bid(rec), "run_id": rec["run_id"], "arm": rec["arm"],
                "task_id": rec["task_id"], "stratum": rec["stratum"], "repeat": rec["repeat"]}

        if rec.get("fault") == "component":
            faulted = task["faulted_gold_id"]
            hit = descendants(task["gold_subtasks"], faulted)
            out = final_text(rec)
            for g in task["gold_subtasks"]:
                if g["id"] in hit:
                    continue
                iso.append({**base, "gold_id": g["id"], "gold_text": g["text"],
                            "faulted_gold_id": faulted, "final_output": out, "survived": ""})
            continue
        if rec.get("fault") in ("ddg_block", "verifier_outage"):
            continue

        # TDA
        plan = plan_texts(rec)
        joined = "\n".join(f"- {p}" for p in plan)
        for g in task["gold_subtasks"]:
            tda.append({**base, "gold_id": g["id"], "gold_text": g["text"],
                        "system_plan": joined, "covered": 0 if not plan else ""})

        # RRP
        for sub_id, sub_text, c in delivered_passages(rec):
            rrp.append({**base, "subtask_id": sub_id, "subtask_text": sub_text,
                        "source": c.get("source"), "source_type": c.get("source_type"),
                        "passage": c.get("content"), "relevant": ""})

        # TSR
        if rec["arm"] == "A":
            sv = rec.get("self_validation") or {}
            ver_ok = 1 if sv.get("status") == "passed" else 0
        else:
            res = rec.get("results", [])
            ver_ok = 1 if res and all(r.get("status") == "passed" for r in res) else 0
        tsr.append({**base, "query": rec["query"],
                    "success_criteria": json.dumps(task["success_criteria"], ensure_ascii=False),
                    "final_output": final_text(rec),
                    "content_ok": "", "evidence_ok": "", "format_ok": "",
                    "verification_ok": ver_ok})

    ann = Path(run_dir) / "annotation"
    ann.mkdir(exist_ok=True)
    for name, rows in (("tda", tda), ("rrp", rrp), ("tsr", tsr), ("isolation", iso)):
        if rows:
            rng.shuffle(rows)   # arms interleaved -> blind labeling
            write_csv(ann / f"{name}_sheet.csv", rows, list(rows[0].keys()))
            print(f"{name}_sheet.csv: {len(rows)} rows")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--tasks", default="benchmark/tasks/tasks.json")
    a = ap.parse_args()
    export(a.run, a.tasks)
