"""
RQ3 / VCR: run the independent Verifier AND the baseline's
self-evaluation over the SAME confirmed seeded-defect artifacts, with
the same evidence.

    python -m benchmark.defect_eval --defects benchmark/defects/candidates.jsonl --out benchmark/defects/eval.jsonl

A detection = status "failed". Two kinds of non-verdict are logged
separately and excluded from VCR by metrics.py:
  * transport errors (Verifier status "error")
  * parse failures (Verifier returned unparseable JSON / bad status,
    which verifier.py maps to "failed" and would otherwise inflate VCR)
"""

import argparse
import json
import re
from pathlib import Path

from ollama import Client

from . import config

SELF_EVAL_SYSTEM = """You previously wrote the response below for the given task.
Validate your own response: is it correct, complete, and supported by the
context and the user's submission?
Return ONLY valid JSON: {"status": "passed" or "failed", "reason": "<short reason>"}"""


def self_eval(client, d):
    user = f"TASK:\n{d['task']}\n"
    if d.get("raw_query"):
        user += f"\nUSER'S ORIGINAL SUBMISSION:\n{d['raw_query']}\n"
    if d.get("context"):
        user += "\nCONTEXT:\n" + "\n---\n".join(c["content"] for c in d["context"]) + "\n"
    if d.get("dependency_outputs"):
        user += "\nDEPENDENCY OUTPUTS:\n" + "\n".join(f"[{k}] {v}" for k, v in d["dependency_outputs"].items()) + "\n"
    user += f"\nYOUR RESPONSE:\n{d['defective_output']}\n"
    try:
        r = client.chat(model=config.CONTROL_MODEL, think=False, format="json",
                        messages=[{"role": "system", "content": SELF_EVAL_SYSTEM},
                                  {"role": "user", "content": user}],
                        options={"temperature": 0, "num_predict": 300})
    except Exception as e:
        return {"status": "error", "reason": f"{type(e).__name__}: {e}"}
    raw = r["message"]["content"].strip()
    try:
        j = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        try:
            j = json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            j = None
    if not isinstance(j, dict) or j.get("status") not in ("passed", "failed"):
        return {"status": "failed", "reason": "Verifier LLM did not return parseable JSON (self_eval): " + raw[:120]}
    return {"status": j["status"], "reason": j.get("reason", "")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--defects", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    from execution.verifier import Verifier
    from . import instrument
    instrument.install_llm()

    verifier = Verifier()
    client = Client(host=config.CONTROL_HOST)

    defects = [json.loads(l) for l in open(a.defects, encoding="utf-8") if l.strip()]
    defects = [d for d in defects if d.get("human_confirmed") is True]
    if not defects:
        raise SystemExit("No defects with human_confirmed=true.")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for d in defects:
            v = verifier.verify(
                task={"task": d["task"], "type": d["type"]},
                output=d["defective_output"],
                retrieved_context=d["context"],
                dependency_outputs=d["dependency_outputs"] or None,
                raw_query=d["raw_query"])
            s = self_eval(client, d)
            for name, res in (("verifier", v), ("self_eval", s)):
                f.write(json.dumps({
                    "defect_id": d["defect_id"], "defect_type": d["defect_type"],
                    "task_id": d["task_id"], "evaluator": name,
                    "status": res["status"], "reason": res["reason"],
                }, ensure_ascii=False) + "\n")
            print(d["defect_id"], d["defect_type"], "verifier:", v["status"], "self_eval:", s["status"])


if __name__ == "__main__":
    main()
