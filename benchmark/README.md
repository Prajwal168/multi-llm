# Benchmark for "A Multi-Agent Deliberation Framework for Locally Hosted LLMs"

Built strictly from the paper: RQ1-RQ5, the four defined metrics
(TDA, RRP, VCR, TSR), the "additional measurements" list, and the
controls in Sections IV-B, IV-D, V and VI. No metrics were added.

Install: copy this `benchmark/` folder into the project root (next to
`main.py`), then `pip install -r benchmark/requirements.txt`.
Run everything from the project root with `python -m benchmark.<module>`.

## What is here

| File | Role |
|---|---|
| `tasks/tasks.json` (+ `build_tasks.py`) | **Seed task set: 15 tasks (3 per stratum S1-S5)** with gold subtasks + dependencies, tags (`needs_web`, `near_synonym`, `user_submission`), success criteria, and fault queries for the S3 tasks |
| `baseline.py` | Arm A: one qwen3:8b call, plan + answer + self-validate, unfiltered top-k context |
| `pipeline_runner.py` | Arms B/C/D: in-process replica of main.py's flow with timings + provenance |
| `instrument.py` | Wraps every Ollama call (tokens, latency, errors), snapshots web pages, injects faults |
| `run_benchmark.py` | Runs arms x tasks x repeats, resumable, incl. fault and concurrency modes |
| `annotate.py` | Exports the blind human-annotation sheets (TDA, RRP, TSR, isolation) |
| `make_defects.py`, `defect_eval.py` | Seeded-defect pool and VCR evaluation (Verifier vs baseline self-evaluation) |
| `metrics.py`, `stats.py` | Every table, bootstrap CIs, Wilcoxon, exact McNemar |
| `mem_sampler.py` | Memory on both Ollama hosts during runs |
| `study_router.py`, `user_study/` | RQ5: approve/reject logging, ratings template, protocol |
| `selftest.py` | Offline test of annotate/metrics/stats with synthetic data (passes) |

Arms: **A** baseline · **B** full system, larger Executor · **C** full system, Executor = qwen3:8b · **D** full system, relevance gate off.
A vs C = structural effect; C vs B = model-capacity effect; D vs B = the LLM relevance gate (RQ2).

## Run order

```bash
# 0. pin the executor model (executor.py's default 'qwen3.8:27b' looks like a typo)
export BENCH_EXECUTOR_MODEL="<exact tag from `ollama list` on the executor host>"

# 1. main comparison (RQ1, RQ2, RQ4, latency, tokens, retries, coverage, diversity, memory)
python -m benchmark.run_benchmark --arms A B C D --repeats 5 --workers 1 --out benchmark/runs/main

# 2. concurrency sweep (Sections III-D, V). Raise OLLAMA_NUM_PARALLEL on the server first.
python -m benchmark.run_benchmark --arms B --strata S3 --workers 2 --repeats 3 --out benchmark/runs/sweep-w2

# 3. failure isolation (RQ4)
python -m benchmark.run_benchmark --arms A B C --strata S3 --fault component --repeats 3 --out benchmark/runs/fault-component

# 4. transport faults (Section IV-E, fifth point)
python -m benchmark.run_benchmark --arms B --fault ddg_block --only S2-01 S2-03 S5-02 --out benchmark/runs/fault-ddg
python -m benchmark.run_benchmark --arms B --fault verifier_outage --fault-k 2 --repeats 2 --out benchmark/runs/fault-verifier-k2
python -m benchmark.run_benchmark --arms B --fault verifier_outage --fault-k 4 --repeats 2 --out benchmark/runs/fault-verifier-k4

# 5. annotation sheets, label them, save as *_annotated.csv in the same folder
python -m benchmark.annotate --run benchmark/runs/main
python -m benchmark.annotate --run benchmark/runs/fault-component

# 6. seeded defects (VCR): generate, HUMAN-CONFIRM each (human_confirmed true/false), evaluate
python -m benchmark.make_defects --run benchmark/runs/main --per-type 10 --out benchmark/defects/candidates.jsonl
python -m benchmark.defect_eval --defects benchmark/defects/candidates.jsonl --out benchmark/defects/eval.jsonl

# 7. user study (RQ5): see user_study/study_protocol.md

# 8. all tables
python -m benchmark.metrics --run benchmark/runs/main --run benchmark/runs/sweep-w2 \
  --run benchmark/runs/fault-component --run benchmark/runs/fault-ddg \
  --run benchmark/runs/fault-verifier-k2 --run benchmark/runs/fault-verifier-k4
```

Sanity check before any of this: `python -m benchmark.selftest`.

## Still needed from you (cannot be automated)

1. **Extend the task set to ~125 tasks (about 25 per stratum).** `tasks.json` is a 15-task seed in the final schema; add tasks in `build_tasks.py` and re-run it. Confirm the `needs_web` tags (the harness records actual source, so you can check post hoc).
2. **Human annotation**: gold subtask coverage (TDA), passage relevance (RRP), TSR criteria, isolation survival. Write short annotation guidelines, use 2+ annotators, and double-annotate a subset. Sheets are shuffled and carry a `blind_id`; hide the `arm` column while labeling.
3. **Confirm every seeded defect** in `candidates.jsonl`.
4. **UI flags for the RQ5 conditions** and the two `fetch` calls to `/api/study/event`.

## Known validity issues, handled or flagged

- **Verifier parse failures**: `verifier.py` maps unparseable output to `failed`, which would inflate VCR. `metrics.py` excludes parse failures and transport errors from VCR and reports their counts (`VCR_excluded_nonverdicts`, `verifier_parse_failures`). `think=True` with `num_predict=800` is the likely cause; decide it before the final run.
- **Executor model tag**: the runner refuses to start B/D until `BENCH_EXECUTOR_MODEL` is set and exists on the host.
- **`OLLAMA_MAX_WORKERS = 1`** in main.py means concurrent execution never happens; the harness takes `--workers` instead. The paper's concurrency claims need it above 1 on a server with `OLLAMA_NUM_PARALLEL` set.
- **Approval checkpoint** is auto-approved in the headless runs; its effect is measured only in the user study.
- **Baseline generation cap** is 6000 tokens (`config.py`) because it must produce plan + all answers + validation in one call. This is a choice the paper does not specify; state it in the write-up.
- **Definitions the paper leaves open** (operationalized here, confirm they match your intent): failure-isolation rate = share of gold subtasks that are independent of the faulted one and still come out correct; retrieval coverage = share of retrieval-required subtasks ending with non-empty context; source diversity = distinct sources per task, local and web separately.
- **Seed-set caveat**: with 3 tasks per stratum the CIs are very wide. The selftest numbers are synthetic and mean nothing.
