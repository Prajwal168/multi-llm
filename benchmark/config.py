"""
Central configuration for the benchmark.

Everything here can be overridden with environment variables so no
source edit is needed between machines.

BENCH_EXECUTOR_MODEL has NO default on purpose. executor.py currently
defaults to "qwen3.8:27b", which looks like a typo; the benchmark
refuses to start arms B/D until you pin the exact tag from
`ollama list` on the executor host.
"""

import os

CONTROL_HOST = os.getenv("BENCH_CONTROL_HOST", "http://192.19.12.9:11434")
EXECUTOR_HOST = os.getenv("BENCH_EXECUTOR_HOST", "http://192.19.12.9:11434")

CONTROL_MODEL = os.getenv("BENCH_CONTROL_MODEL", "qwen3:8b")
EXECUTOR_MODEL = os.getenv("BENCH_EXECUTOR_MODEL")  # required for arms B, D

# Arms (paper Section IV-B, plus the two ablations needed to separate
# structure from model capacity and to answer RQ2)
ARMS = {
    "A": "Baseline: one qwen3:8b call (plan + answer + self-validate)",
    "B": "Full system, larger Executor model",
    "C": "Full system, Executor = qwen3:8b (structure-only effect)",
    "D": "Full system, relevance gate OFF (distance threshold only)",
}

STRATA = ["S1", "S2", "S3", "S4", "S5"]

# Baseline: "unfiltered set of retrieved context" -> plain top-k from the
# same Chroma corpus, no distance threshold, no dedup, no LLM gate.
BASELINE_TOP_K = 5
# The baseline must plan + answer every subtask + self-validate in ONE
# call, so it gets a larger generation cap than a single Executor call.
BASELINE_NUM_PREDICT = 6000

# Stage names, derived from the file that issued each Ollama call.
STAGE_BY_FILE = {
    "mediator.py": "mediator",
    "planner_llm.py": "retrieval_planner",
    "retrieval_verifier.py": "relevance_gate",
    "executor.py": "executor",
    "verifier.py": "verifier",
    "baseline.py": "baseline",
    "defect_eval.py": "defect_eval",
    "make_defects.py": "make_defects",
}

VERIFIER_PARSE_FAIL_PREFIXES = (
    "Verifier LLM did not return parseable JSON",
    "Verifier LLM returned an invalid status",
)
