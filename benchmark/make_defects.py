"""
Builds the seeded-defect pool used for VCR (Eq. 9).

Takes subtask outputs that PASSED verification in an arm-B run and
creates defective variants matching the Verifier's own criteria:

  not_addressed      output does not do what the task asks
  unsupported_claim  adds a claim not supported by evidence / submission
  factual_error      a technical or factual claim is wrong
  incomplete         a required part is missing
  irrelevant_evidence  same output, but the evidence is swapped for
                       passages from a DIFFERENT task (topically
                       adjacent, not relevant) -- no LLM involved

The injection LLM is the Executor-side model. EVERY candidate is
written with human_confirmed = null: a human must open the file, check
that the defect is really present and really of that type, and set it
to true (or false to discard). defect_eval.py only uses confirmed ones.

    python -m benchmark.make_defects --run benchmark/runs/main --per-type 10 --out benchmark/defects/candidates.jsonl
"""

import argparse
import json
import random
from pathlib import Path

from ollama import Client

from . import config

INSTRUCTIONS = {
    "not_addressed": "Rewrite the output so it reads plausibly but does NOT actually do what the task asks (e.g. answers a neighbouring question instead).",
    "unsupported_claim": "Keep the output but insert ONE confident specific claim that is not supported by the provided evidence or the user's submission.",
    "factual_error": "Keep the output but change ONE factual or technical statement so it is wrong (e.g. wrong complexity, wrong exception type, wrong behaviour). Keep the tone confident.",
    "incomplete": "Remove one required part of the output entirely (a section, a step, or a required piece of code) without mentioning that it is missing.",
}

SYSTEM = ("You create controlled test defects for a verification benchmark. "
          "Return ONLY JSON: {\"defective_output\": \"...\", \"defect_description\": \"...\"}. "
          "Make exactly one defect of the requested type; change nothing else.")


def candidates_from_run(run_dir):
    recs = [json.loads(l) for l in (Path(run_dir) / "results.jsonl").open(encoding="utf-8") if l.strip()]
    pool = []
    for rec in recs:
        if rec["arm"] != "B" or rec.get("fault") != "none":
            continue
        ctx_by_task = {r["task_id"]: r["contexts"] for r in rec.get("retrieval", [])}
        out_by_task = {r["task_id"]: r["output"] for r in rec.get("results", [])}
        for r in rec.get("results", []):
            if r.get("status") != "passed":
                continue
            plan_t = next((t for t in rec["plan"] if t["task_id"] == r["task_id"]), {})
            pool.append({
                "source_run": rec["run_id"], "task_id": rec["task_id"], "subtask_id": r["task_id"],
                "task": r["task"], "type": r["type"], "output": r["output"],
                "context": ctx_by_task.get(r["task_id"], []),
                "dependency_outputs": {d: out_by_task.get(d, "") for d in r.get("depends_on", [])},
                "raw_query": rec["query"], "knowledge_type": plan_t.get("knowledge_type"),
            })
    return pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--per-type", type=int, default=10)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    if not config.EXECUTOR_MODEL:
        raise SystemExit("Set BENCH_EXECUTOR_MODEL first.")
    rng = random.Random(a.seed)
    client = Client(host=config.EXECUTOR_HOST)
    pool = candidates_from_run(a.run)
    if not pool:
        raise SystemExit("No passed arm-B subtask outputs found in that run.")

    out, n = [], 0
    for dtype in list(INSTRUCTIONS) + ["irrelevant_evidence"]:
        picks = rng.sample(pool, min(a.per_type, len(pool)))
        for p in picks:
            item = {"defect_id": f"D{n:04d}", "defect_type": dtype, **{k: p[k] for k in
                    ("source_run", "task_id", "subtask_id", "task", "type", "dependency_outputs", "raw_query")},
                    "clean_output": p["output"], "human_confirmed": None}
            n += 1
            if dtype == "irrelevant_evidence":
                others = [q for q in pool if q["task_id"] != p["task_id"] and q["context"]]
                if not others:
                    continue
                item["defective_output"] = p["output"]
                item["context"] = rng.choice(others)["context"]
                item["defect_description"] = "Evidence replaced with passages retrieved for a different task."
            else:
                user = (f"DEFECT TYPE: {dtype}\nINSTRUCTION: {INSTRUCTIONS[dtype]}\n\n"
                        f"TASK:\n{p['task']}\n\nEVIDENCE:\n" +
                        "\n---\n".join(c["content"] for c in p["context"]) +
                        f"\n\nORIGINAL OUTPUT:\n{p['output']}")
                resp = client.chat(model=config.EXECUTOR_MODEL, think=False, format="json",
                                   messages=[{"role": "system", "content": SYSTEM},
                                             {"role": "user", "content": user}],
                                   options={"temperature": 0.3, "num_predict": 3000})
                try:
                    j = json.loads(resp["message"]["content"])
                    item["defective_output"] = j["defective_output"]
                    item["defect_description"] = j.get("defect_description", "")
                except Exception:
                    continue
                item["context"] = p["context"]
            out.append(item)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for it in out:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{len(out)} candidates -> {a.out}. Set human_confirmed=true/false on each before running defect_eval.")


if __name__ == "__main__":
    main()
