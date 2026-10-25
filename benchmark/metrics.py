"""
Computes every measurement the paper defines and nothing else.

Paper-defined metrics (Section IV-C):
  TDA  (Eq. 7)   from annotation/tda_sheet_annotated.csv
  RRP  (Eq. 8)   from annotation/rrp_sheet_annotated.csv (local/web split)
  VCR  (Eq. 9)   from defects/eval.jsonl
  TSR  (Eq. 10)  from annotation/tsr_sheet_annotated.csv
Additional measurements the paper lists:
  latency, token usage, number of retries, retrieval coverage,
  source diversity, failure-isolation rate, plan rejection rate,
  human ratings of transparency and trust (+ debuggability, Sec. IV-F),
  memory consumption (Sec. VI), concurrency behaviour (III-D / V),
  transport-fault recovery (IV-E).

    python -m benchmark.metrics --run benchmark/runs/main \
        --run benchmark/runs/sweep-w2 --run benchmark/runs/fault-component \
        --defects-eval benchmark/defects/eval.jsonl --out benchmark/metrics_out

Aggregation: per-task mean over repeats, then 95% bootstrap CI over
TASKS (repeats of one task are not independent). Paired tests are also
done over tasks: Wilcoxon signed-rank on per-task means, and exact
McNemar on majority-vote task outcomes for binary metrics (TSR).
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from . import stats as S

PAIRS = [("A", "B"), ("A", "C"), ("C", "B"), ("D", "B")]   # reported as "second - first"
TIMEOUT_MARKERS = ("timed out", "timeout", "10060", "connecterror", "readtimeout")


# ----------------------------------------------------------------- loading
def load_records(run_dirs):
    recs = []
    for d in run_dirs:
        p = Path(d) / "results.jsonl"
        if not p.exists():
            continue
        for line in p.open(encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                r["_dir"] = str(d)
                recs.append(r)
    return recs


def read_annotated(run_dirs, name):
    frames = []
    for d in run_dirs:
        p = Path(d) / "annotation" / f"{name}_sheet_annotated.csv"
        if p.exists():
            frames.append(pd.read_csv(p))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ------------------------------------------------- per-run operational rows
def record_row(rec):
    calls = rec.get("calls", [])
    stage_of = lambda c: config.STAGE_BY_FILE.get(c["stage"], c["stage"])
    row = {
        "arm": rec["arm"], "task_id": rec["task_id"], "stratum": rec["stratum"],
        "repeat": rec["repeat"], "workers": rec.get("workers"), "fault": rec.get("fault", "none"),
        "fault_k": rec.get("fault_k"),
        "total_s": (rec.get("timings") or {}).get("total"),
        "wall_s": rec.get("wall_seconds"),
        "errored": int(bool(rec.get("error"))),
        "llm_calls": len(calls),
    }
    pt = sum(c.get("prompt_tokens") or 0 for c in calls)
    ct = sum(c.get("completion_tokens") or 0 for c in calls)
    row.update(prompt_tokens=pt, completion_tokens=ct, total_tokens=pt + ct)
    for c in calls:
        k = f"tok_{stage_of(c)}"
        row[k] = row.get(k, 0) + (c.get("prompt_tokens") or 0) + (c.get("completion_tokens") or 0)
    for k, v in (rec.get("timings") or {}).items():
        row[f"t_{k}"] = v

    results = rec.get("results", []) or []
    row["exec_regenerations"] = sum(max((r.get("attempts") or 1) - 1, 0) for r in results)
    row["verifier_transport_errors"] = sum(1 for c in calls if stage_of(c) == "verifier" and c.get("error"))
    row["real_timeouts"] = sum(
        1 for c in calls
        if c.get("error") and "injected" not in c["error"]
        and any(m in c["error"].lower() for m in TIMEOUT_MARKERS))
    row["verifier_parse_failures"] = sum(
        1 for r in results
        if str(r.get("reason", "")).startswith(config.VERIFIER_PARSE_FAIL_PREFIXES))

    # retrieval coverage & source diversity
    if rec["arm"] == "A":
        ctxs = rec.get("contexts", [])
        row["retrieval_coverage"] = 1.0 if ctxs else 0.0
    else:
        required = [t["task_id"] for t in rec.get("plan", [])
                    if isinstance(t, dict) and t.get("retrieval", {}).get("required")]
        have = {r["task_id"] for r in rec.get("retrieval", []) if r.get("contexts")}
        row["retrieval_coverage"] = (len([t for t in required if t in have]) / len(required)
                                     if required else np.nan)
        ctxs = [c for r in rec.get("retrieval", []) for c in r.get("contexts", [])]
    row["sources_local"] = len({c["source"] for c in ctxs if c.get("source_type") == "local"})
    row["sources_web"] = len({c["source"] for c in ctxs if c.get("source_type") == "web"})

    # fault-recovery facts
    if rec["arm"] != "A":
        row["all_completed"] = int(bool(results) and not any(
            str(r.get("output", "")).startswith("EXECUTION ERROR") or r.get("status") == "error"
            for r in results))
        for s in ("passed", "failed", "unverified_failed", "error"):
            row[f"n_{s}"] = sum(1 for r in results if r.get("status") == s)
    web = rec.get("web", [])
    row["tavily_calls"] = sum(1 for w in web if "tavily" in w["url"] and w.get("status") == 200)
    row["ddg_failures"] = sum(1 for w in web if "duckduckgo" in w["url"] and w.get("error"))
    return row


# ------------------------------------------------------------- aggregation
def _slices(df):
    for arm in sorted(df.arm.unique()):
        yield arm, "ALL", df[df.arm == arm]
        for st in sorted(df[df.arm == arm].stratum.unique()):
            yield arm, st, df[(df.arm == arm) & (df.stratum == st)]


def summarize(df, cols):
    rows = []
    for arm, st, sub in _slices(df):
        for col in cols:
            if col not in sub:
                continue
            per_task = sub.groupby("task_id")[col].mean()
            if per_task.notna().sum() == 0:
                continue
            m, lo, hi = S.bootstrap_ci(per_task.values)
            rows.append({"arm": arm, "stratum": st, "metric": col, "mean": m,
                         "ci_lo": lo, "ci_hi": hi, "n_tasks": int(per_task.notna().sum())})
    return pd.DataFrame(rows)


def pooled(df, val, extra_filter=None, label=None):
    """Pooled ratio sum(val)/count with task-cluster bootstrap."""
    rows = []
    if df.empty:
        return pd.DataFrame(rows)
    for arm, st, sub in _slices(df):
        if extra_filter is not None:
            sub = sub[extra_filter(sub)]
        if sub.empty:
            continue
        g = sub.groupby("task_id")[val].agg(["sum", "count"])
        m, lo, hi = S.bootstrap_ratio_ci(g["sum"].values, g["count"].values)
        rows.append({"arm": arm, "stratum": st, "subset": label or "all", "value": m,
                     "ci_lo": lo, "ci_hi": hi, "n_tasks": len(g), "n_items": int(g["count"].sum())})
    return pd.DataFrame(rows)


def paired(df, metric, binary=False):
    """Task-level paired tests between arms (second - first)."""
    rows = []
    for st in ["ALL"] + sorted(df.stratum.unique()):
        sub = df if st == "ALL" else df[df.stratum == st]
        pv = sub.pivot_table(index="task_id", columns="arm", values=metric, aggfunc="mean")
        for a, b in PAIRS:
            if a not in pv or b not in pv:
                continue
            x, y = pv[a], pv[b]
            n, p = S.wilcoxon_paired(y.values, x.values)
            row = {"metric": metric, "stratum": st, "comparison": f"{b} - {a}",
                   "mean_diff": float(np.nanmean((y - x).values)) if n else np.nan,
                   "n_tasks": n, "wilcoxon_p": p}
            if binary and n:
                ok = ~(x.isna() | y.isna())
                bb, cc, pm = S.mcnemar_exact((y[ok] >= 0.5).astype(int).values,
                                              (x[ok] >= 0.5).astype(int).values)
                row.update(mcnemar_b_only_second=bb, mcnemar_c_only_first=cc, mcnemar_p=pm)
            rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------- the metrics
def tda(ann):
    d = ann.dropna(subset=["covered"])
    per_run = (d.groupby(["arm", "stratum", "task_id", "repeat"])["covered"].mean()
                 .reset_index().rename(columns={"covered": "TDA"}))
    return per_run


def rrp(ann):
    return ann.dropna(subset=["relevant"])


def tsr(ann):
    d = ann.dropna(subset=["content_ok", "evidence_ok", "format_ok", "verification_ok"]).copy()
    d["TSR"] = ((d.content_ok == 1) & (d.evidence_ok == 1) &
                (d.format_ok == 1) & (d.verification_ok == 1)).astype(int)
    return d


def vcr(path):
    p = Path(path)
    if not p.exists():
        return None, None, None
    d = pd.DataFrame([json.loads(l) for l in p.open(encoding="utf-8") if l.strip()])
    d["parse_fail"] = d.reason.astype(str).apply(
        lambda r: r.startswith(config.VERIFIER_PARSE_FAIL_PREFIXES))
    excluded = (d.groupby("evaluator").agg(
        total=("status", "size"),
        transport_errors=("status", lambda s: int((s == "error").sum())),
        parse_failures=("parse_fail", "sum")).reset_index())
    v = d[d.status.isin(["passed", "failed"]) & ~d.parse_fail].copy()
    v["detected"] = (v.status == "failed").astype(int)
    rows = []
    for ev in sorted(v.evaluator.unique()):
        for dt in ["ALL"] + sorted(v.defect_type.unique()):
            sub = v[(v.evaluator == ev) & ((v.defect_type == dt) | (dt == "ALL"))]
            m, lo, hi = S.bootstrap_ci(sub.detected.values)
            rows.append({"evaluator": ev, "defect_type": dt, "VCR": m, "ci_lo": lo,
                         "ci_hi": hi, "n_defects": len(sub)})
    pv = v.pivot_table(index="defect_id", columns="evaluator", values="detected").dropna()
    test = None
    if {"verifier", "self_eval"} <= set(pv.columns) and len(pv):
        b, c, p = S.mcnemar_exact(pv["verifier"].astype(int).values, pv["self_eval"].astype(int).values)
        test = pd.DataFrame([{"comparison": "verifier vs self_eval", "n_paired": len(pv),
                              "only_verifier_detects": b, "only_self_eval_detects": c, "mcnemar_p": p}])
    return pd.DataFrame(rows), excluded, test


def memory(run_dirs):
    frames = []
    for d in run_dirs:
        p = Path(d) / "mem_samples.jsonl"
        if p.exists():
            frames.append(pd.DataFrame([json.loads(l) for l in p.open() if l.strip()]))
    if not frames:
        return pd.DataFrame()
    m = pd.concat(frames, ignore_index=True)
    out = []
    for (host, model), g in m[m.host != "harness_process"].groupby(["host", "model"]):
        out.append({"host": host, "model": model,
                    "peak_size_GB": g["size"].max() / 1e9,
                    "peak_vram_GB": g["size_vram"].max() / 1e9})
    h = m[m.host == "harness_process"]
    if not h.empty:
        out.append({"host": "harness_process", "model": "-", "peak_size_GB": h["rss"].max() / 1e9,
                    "peak_vram_GB": np.nan})
    return pd.DataFrame(out)


def study(study_dir):
    out = {}
    ev = Path(study_dir) / "study_events.jsonl"
    if ev.exists():
        e = pd.DataFrame([json.loads(l) for l in ev.open() if l.strip()])
        e = e[e.event.isin(["approve", "reject"])]
        if not e.empty:
            g = e.groupby("condition").event.agg(
                n="size", rejections=lambda s: int((s == "reject").sum())).reset_index()
            g["plan_rejection_rate"] = g.rejections / g.n
            out["plan_rejection"] = g
    rt = Path(study_dir) / "ratings.csv"
    if rt.exists():
        r = pd.read_csv(rt)
        rows = []
        for cond, g in r.groupby("condition"):
            for item in ("transparency", "trust", "debuggability"):
                if item in g and g[item].notna().any():
                    m, lo, hi = S.bootstrap_ci(g[item].dropna().values)
                    rows.append({"condition": cond, "item": item, "mean": m, "ci_lo": lo,
                                 "ci_hi": hi, "n_ratings": int(g[item].notna().sum())})
        out["ratings"] = pd.DataFrame(rows)
    return out


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True)
    ap.add_argument("--defects-eval", default="benchmark/defects/eval.jsonl")
    ap.add_argument("--study-dir", default="benchmark/user_study")
    ap.add_argument("--main-workers", type=int, default=1)
    ap.add_argument("--out", default="benchmark/metrics_out")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tables = {}

    recs = load_records(a.run)
    if not recs:
        raise SystemExit("No results found.")
    ops = pd.DataFrame([record_row(r) for r in recs])
    main_ops = ops[(ops.fault == "none") & (ops.workers == a.main_workers)]

    # operational measurements
    op_cols = ["total_s", "prompt_tokens", "completion_tokens", "total_tokens", "llm_calls",
               "exec_regenerations", "verifier_transport_errors", "retrieval_coverage",
               "sources_local", "sources_web", "real_timeouts", "verifier_parse_failures"]
    op_cols += [c for c in ops.columns if c.startswith(("t_", "tok_"))]
    tables["operational"] = summarize(main_ops, op_cols)
    tables["latency_paired"] = paired(main_ops, "total_s")
    tables["tokens_paired"] = paired(main_ops, "total_tokens")

    # annotation-based metrics
    tda_ann = read_annotated(a.run, "tda")
    if not tda_ann.empty:
        t = tda(tda_ann)
        tables["TDA"] = summarize(t, ["TDA"])
        tables["TDA_paired"] = paired(t, "TDA")
    rrp_ann = read_annotated(a.run, "rrp")
    if not rrp_ann.empty:
        r = rrp(rrp_ann)
        tables["RRP"] = pd.concat([
            pooled(r, "relevant", label="all"),
            pooled(r, "relevant", lambda s: s.source_type == "local", "local"),
            pooled(r, "relevant", lambda s: s.source_type == "web", "web")], ignore_index=True)
        per_task = (r.groupby(["arm", "stratum", "task_id"])["relevant"].mean()
                      .reset_index().rename(columns={"relevant": "RRP"}))
        tables["RRP_paired"] = paired(per_task, "RRP")
    tsr_ann = read_annotated(a.run, "tsr")
    if not tsr_ann.empty:
        t = tsr(tsr_ann)
        tables["TSR"] = summarize(t, ["TSR"])
        tables["TSR_paired"] = paired(t, "TSR", binary=True)
    iso_ann = read_annotated(a.run, "isolation")
    if not iso_ann.empty:
        tables["failure_isolation"] = pooled(iso_ann.dropna(subset=["survived"]), "survived")

    # VCR
    v_tab, v_excl, v_test = vcr(a.defects_eval)
    if v_tab is not None:
        tables["VCR"], tables["VCR_excluded_nonverdicts"] = v_tab, v_excl
        if v_test is not None:
            tables["VCR_paired"] = v_test

    # concurrency sweep (arm B, dependent tasks)
    sweep = ops[(ops.arm == "B") & (ops.stratum == "S3") & (ops.fault == "none")]
    if sweep.workers.nunique() > 0:
        tables["concurrency_sweep"] = (sweep.groupby("workers").agg(
            runs=("task_id", "size"), mean_total_s=("total_s", "mean"),
            real_timeouts=("real_timeouts", "sum"), errored_runs=("errored", "sum"),
            exec_regenerations=("exec_regenerations", "sum")).reset_index())

    # transport-fault recovery
    fl = ops[(ops.fault.isin(["ddg_block", "verifier_outage"]))]
    if not fl.empty:
        tables["transport_fault_recovery"] = (fl.groupby(["arm", "fault", "fault_k"], dropna=False).agg(
            runs=("task_id", "size"), fraction_all_tasks_completed=("all_completed", "mean"),
            passed=("n_passed", "sum"), failed=("n_failed", "sum"),
            unverified_failed=("n_unverified_failed", "sum"), verdict_error=("n_error", "sum"),
            verifier_transport_errors=("verifier_transport_errors", "sum"),
            tavily_calls=("tavily_calls", "sum"), ddg_failures=("ddg_failures", "sum")).reset_index())

    m = memory(a.run)
    if not m.empty:
        tables["memory"] = m
    for k, v in study(a.study_dir).items():
        tables[k] = v

    md = []
    for name, df in tables.items():
        if df is None or len(df) == 0:
            continue
        df.to_csv(out / f"{name}.csv", index=False)
        md.append(f"\n=== {name} ===\n{df.round(3).to_string(index=False)}\n")
    (out / "summary.txt").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print(f"\nTables written to {out}/")


if __name__ == "__main__":
    main()
