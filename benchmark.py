import json
import statistics
import time
from datetime import datetime
from pathlib import Path

import requests


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "http://127.0.0.1:8000"
OUTPUT_FILE = "benchmark_30_results.json"

# IMPORTANT:
# This is the value currently configured in backend/main.py.
OLLAMA_MAX_WORKERS = 3


# ============================================================
# SAME 30-QUERY BENCHMARK
# ============================================================

QUERIES = [
    "Explain recursion and give a simple Python example.",
    "Explain how a Python dictionary works.",
    "Explain object-oriented programming in Python.",
    "Explain what an API is and how REST APIs work.",
    "Explain the difference between a process and a thread.",

    "Write a Python function to calculate factorial.",
    "Write a Python function to check whether a string is a palindrome.",
    "Write a Python program to find the largest number in a list.",
    "Write a Python function to remove duplicates from a list.",
    "Write a Python program to count word frequency in a text.",

    "Debug this Python code: x=[1,2,3]; print(x[3])",
    "Debug this Python code: for i in range(5) print(i)",
    "Debug this Python code: numbers=[1,2,3]; numbers.append[4]",
    "Debug this Python code: result=10/0",
    "Debug this Python code: name=None; print(name.upper())",

    "Explain why binary search has O(log n) time complexity.",
    "What is the time complexity of finding the maximum value in an unsorted list?",
    "Why can nested loops result in O(n^2) time complexity?",
    "What are the advantages and disadvantages of recursion?",
    "How does caching improve program performance?",

    "Compare Python lists and tuples.",
    "Compare Python lists, sets, and dictionaries.",
    "Compare BFS and DFS.",
    "Explain synchronous versus asynchronous programming.",
    "Compare SQL and NoSQL databases.",

    "Explain binary search, provide Python code, and explain its complexity.",
    "Explain recursion with a Python example and compare recursion with iteration.",
    "Design a Python program that reads numbers, removes duplicates, sorts them, and calculates their average.",
    "Give an efficient Python solution for the Two Sum problem.",
    "Design a simple REST API in Python including endpoints, request handling, and error handling."
]


# ============================================================
# JSON / STATISTICS HELPERS
# ============================================================

def percentile(values, p):
    if not values:
        return None

    values = sorted(values)

    if len(values) == 1:
        return values[0]

    index = (len(values) - 1) * (p / 100)
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)

    if lower == upper:
        return values[lower]

    fraction = index - lower

    return (
        values[lower]
        + (values[upper] - values[lower]) * fraction
    )


def latency_stats(values):
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "std_dev": None,
            "p95": None,
            "p99": None
        }

    return {
        "count": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "std_dev": (
            statistics.stdev(values)
            if len(values) > 1
            else 0
        ),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99)
    }


def save_results(data):
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
            default=str
        )


def response_json(response):
    try:
        return response.json()
    except Exception:
        return {
            "_response_text": response.text,
            "_status_code": response.status_code
        }


# ============================================================
# MEDIATOR
# ============================================================

def call_mediator(query):

    start = time.perf_counter()

    response = requests.post(
        f"{BASE_URL}/api/mediator",
        json={
            "query": query
        },
        timeout=600
    )

    elapsed = time.perf_counter() - start

    data = response_json(response)

    response.raise_for_status()

    return {
        "latency_seconds": elapsed,
        "status_code": response.status_code,
        "response": data
    }


# ============================================================
# EXTRACT TASKS FROM MEDIATOR
# ============================================================

def extract_tasks(mediator_data):

    result = mediator_data.get("result")

    if isinstance(result, dict):

        # Common possibility
        if isinstance(result.get("tasks"), list):
            return result["tasks"]

    if isinstance(result, list):
        return result

    if isinstance(result, str):

        # Try parsing JSON if mediator returned JSON as string
        try:
            parsed = json.loads(result)

            if isinstance(parsed, dict):
                if isinstance(parsed.get("tasks"), list):
                    return parsed["tasks"]

            if isinstance(parsed, list):
                return parsed

        except Exception:
            pass

    raise ValueError(
        "Could not extract task list from mediator response."
    )


# ============================================================
# RETRIEVAL
# ============================================================

def call_retrieval(tasks, raw_query):

    start = time.perf_counter()

    # IMPORTANT:
    # This matches RetrievalRequest in backend/main.py
    payload = {
        "tasks": tasks,
        "raw_query": raw_query
    }

    response = requests.post(
        f"{BASE_URL}/api/retrieval",
        json=payload,
        timeout=1800
    )

    elapsed = time.perf_counter() - start

    data = response_json(response)

    response.raise_for_status()

    return {
        "latency_seconds": elapsed,
        "status_code": response.status_code,

        # Preserve exactly what we sent
        "request": payload,

        # Complete retrieval response
        "response": data
    }


# ============================================================
# EXECUTION
# ============================================================

def call_execution(execution_packages):

    start = time.perf_counter()

    # IMPORTANT:
    # ExecutionRequest in backend/main.py ONLY contains
    # execution_packages.
    payload = {
        "execution_packages": execution_packages
    }

    response = requests.post(
        f"{BASE_URL}/api/execution",
        json=payload,
        stream=True,
        timeout=3600
    )

    response.raise_for_status()

    events = []
    raw_lines = []

    # Client-side event arrival timeline
    for line in response.iter_lines(
        decode_unicode=True
    ):

        if not line:
            continue

        received_at = (
            time.perf_counter() - start
        )

        raw_lines.append(line)

        try:
            event = json.loads(line)

        except json.JSONDecodeError:
            event = {
                "_raw_line": line,
                "_parse_error": True
            }

        events.append({
            "received_at_seconds": received_at,
            "event": event
        })

    elapsed = time.perf_counter() - start

    return {
        "latency_seconds": elapsed,
        "status_code": response.status_code,

        # Request sent to execution API
        "request": payload,

        # EVERY event returned by executor
        "events": events,

        # Original NDJSON lines
        "raw_ndjson_lines": raw_lines
    }


# ============================================================
# EXECUTION EVENT ANALYSIS
# ============================================================

def analyze_execution(execution_data):

    events = execution_data.get(
        "events",
        []
    )

    executed = []
    verified = []
    retries = []
    errors = []

    passed = 0
    failed = 0

    for item in events:

        event = item.get(
            "event",
            {}
        )

        if not isinstance(event, dict):
            continue

        event_type = str(
            event.get("type", "")
        ).lower()

        status = str(
            event.get("status", "")
        ).lower()

        # -----------------------------------------------
        # Executed events
        # -----------------------------------------------

        if event_type == "executed":
            executed.append(item)

        # -----------------------------------------------
        # Verified events
        # -----------------------------------------------

        if event_type == "verified":
            verified.append(item)

            if status == "passed":
                passed += 1

            elif status in (
                "failed",
                "unverified_failed"
            ):
                failed += 1

        # -----------------------------------------------
        # Retry events
        # -----------------------------------------------

        if (
            "retry" in event_type
            or "retry" in status
        ):
            retries.append(item)

        # -----------------------------------------------
        # Error events
        # -----------------------------------------------

        if (
            event_type == "error"
            or status == "error"
        ):
            errors.append(item)

    # -----------------------------------------------
    # Final "done" event
    # -----------------------------------------------

    done_events = [
        item
        for item in events
        if isinstance(
            item.get("event"),
            dict
        )
        and str(
            item["event"].get("type", "")
        ).lower() == "done"
    ]

    final_result = (
        done_events[-1]["event"]
        if done_events
        else None
    )

    return {
        "total_events": len(events),

        "executed_event_count":
            len(executed),

        "verified_event_count":
            len(verified),

        "retry_event_count":
            len(retries),

        "error_event_count":
            len(errors),

        "verification_passed":
            passed,

        "verification_failed":
            failed,

        "done_event_count":
            len(done_events),

        "final_done_event":
            final_result,

        "query_execution_success":
            (
                len(errors) == 0
                and failed == 0
            )
    }


# ============================================================
# BUILD OVERALL SUMMARY
# ============================================================

def build_summary(results, benchmark_wall_time):

    query_records = results["queries"]

    successful_queries = sum(
        1
        for q in query_records
        if q.get("status") == "success"
    )

    failed_queries = sum(
        1
        for q in query_records
        if q.get("status") != "success"
    )

    total_tasks = 0
    total_passed = 0
    total_failed = 0
    total_retries = 0

    total_latencies = []
    mediator_latencies = []
    retrieval_latencies = []
    execution_latencies = []

    task_counts = []

    for q in query_records:

        metrics = q.get(
            "metrics",
            {}
        )

        task_count = metrics.get(
            "task_count",
            0
        )

        total_tasks += task_count
        task_counts.append(task_count)

        total_passed += metrics.get(
            "verification_passed",
            0
        )

        total_failed += metrics.get(
            "verification_failed",
            0
        )

        total_retries += metrics.get(
            "retries",
            0
        )

        if metrics.get(
            "total_latency_seconds"
        ) is not None:

            total_latencies.append(
                metrics[
                    "total_latency_seconds"
                ]
            )

        if metrics.get(
            "mediator_latency_seconds"
        ) is not None:

            mediator_latencies.append(
                metrics[
                    "mediator_latency_seconds"
                ]
            )

        if metrics.get(
            "retrieval_latency_seconds"
        ) is not None:

            retrieval_latencies.append(
                metrics[
                    "retrieval_latency_seconds"
                ]
            )

        if metrics.get(
            "execution_latency_seconds"
        ) is not None:

            execution_latencies.append(
                metrics[
                    "execution_latency_seconds"
                ]
            )

    verification_total = (
        total_passed + total_failed
    )

    verification_rate = (
        total_passed /
        verification_total *
        100
        if verification_total
        else 0
    )

    queries_with_retries = sum(
        1
        for q in query_records
        if q.get(
            "metrics",
            {}
        ).get(
            "retries",
            0
        ) > 0
    )

    return {

        "benchmark_completed": (
            len(query_records) ==
            len(QUERIES)
        ),

        "total_queries":
            len(QUERIES),

        "completed_queries":
            len(query_records),

        "successful_queries":
            successful_queries,

        "failed_or_error_queries":
            failed_queries,

        "query_success_rate_percent":
            (
                successful_queries /
                len(query_records) *
                100
                if query_records
                else 0
            ),

        "total_tasks":
            total_tasks,

        "average_tasks_per_query":
            (
                statistics.mean(task_counts)
                if task_counts
                else 0
            ),

        "verification": {

            "total_verification_results":
                verification_total,

            "passed":
                total_passed,

            "failed":
                total_failed,

            "pass_rate_percent":
                verification_rate
        },

        "retries": {

            "total_retries":
                total_retries,

            "queries_with_retries":
                queries_with_retries
        },

        "latency_seconds": {

            "end_to_end":
                latency_stats(
                    total_latencies
                ),

            "mediator":
                latency_stats(
                    mediator_latencies
                ),

            "retrieval":
                latency_stats(
                    retrieval_latencies
                ),

            "execution_plus_verification":
                latency_stats(
                    execution_latencies
                )
        },

        "benchmark_wall_clock_seconds":
            benchmark_wall_time,

        "benchmark_wall_clock_minutes":
            benchmark_wall_time / 60
    }


# ============================================================
# MAIN
# ============================================================

def main():

    benchmark_start = time.perf_counter()

    results = {

        "benchmark_info": {

            "benchmark_name":
                "30 Query End-to-End Pipeline Benchmark",

            "timestamp":
                datetime.now().isoformat(),

            "api_base_url":
                BASE_URL,

            "ollama_host":
                "http://192.19.11.136:11434",

            "ollama_max_workers":
                OLLAMA_MAX_WORKERS,

            "total_test_queries":
                len(QUERIES),

            "models": {

                "mediator":
                    "qwen3:8b",

                "planner":
                    "qwen3:8b",

                "retrieval_verifier":
                    "qwen3:8b",

                "executor":
                    "qwen3:8b",

                "verifier":
                    "qwen3:8b",

                "synthesizer":
                    "qwen3:8b"
            },

            "test_queries":
                QUERIES
        },

        "queries": [],

        "summary": {}
    }

    print("=" * 70)
    print("30-QUERY END-TO-END BENCHMARK")
    print("=" * 70)

    print(
        f"API:       {BASE_URL}"
    )

    print(
        f"Workers:   {OLLAMA_MAX_WORKERS}"
    )

    print(
        f"Queries:   {len(QUERIES)}"
    )

    print(
        f"Output:    {OUTPUT_FILE}"
    )

    print("=" * 70)


    # ========================================================
    # RUN EACH QUERY
    # ========================================================

    for query_id, query in enumerate(
        QUERIES,
        start=1
    ):

        print("\n")
        print("=" * 70)
        print(
            f"QUERY {query_id}/{len(QUERIES)}"
        )
        print(query)
        print("=" * 70)

        query_start = time.perf_counter()

        record = {

            "query_id":
                query_id,

            "query":
                query,

            "timestamp":
                datetime.now().isoformat()
        }


        try:

            # =================================================
            # 1. MEDIATOR
            # =================================================

            print("\n[1/3] Mediator...")

            mediator = call_mediator(
                query
            )

            record["mediator"] = mediator

            print(
                f"Mediator: "
                f"{mediator['latency_seconds']:.2f}s"
            )


            # =================================================
            # EXTRACT TASKS
            # =================================================

            mediator_response = (
                mediator["response"]
            )

            tasks = extract_tasks(
                mediator_response
            )

            record["mediator"]["extracted_tasks"] = tasks

            print(
                f"Mediator tasks: "
                f"{len(tasks)}"
            )


            # =================================================
            # 2. RETRIEVAL
            # =================================================

            print("\n[2/3] Retrieval...")

            retrieval = call_retrieval(
                tasks,
                query
            )

            record["retrieval"] = retrieval

            print(
                f"Retrieval: "
                f"{retrieval['latency_seconds']:.2f}s"
            )


            # =================================================
            # GET EXECUTION PACKAGES
            # =================================================

            retrieval_response = (
                retrieval["response"]
            )

            execution_packages = (
                retrieval_response.get(
                    "execution_packages",
                    []
                )
            )

            record["retrieval"][
                "execution_package_count"
            ] = len(
                execution_packages
            )


            # =================================================
            # 3. EXECUTION
            # =================================================

            print(
                "\n[3/3] "
                "Execution + Verification..."
            )

            execution = call_execution(
                execution_packages
            )

            record["execution"] = execution

            execution_analysis = (
                analyze_execution(
                    execution
                )
            )

            record["execution"][
                "analysis"
            ] = execution_analysis


            # =================================================
            # METRICS
            # =================================================

            total_elapsed = (
                time.perf_counter()
                - query_start
            )

            passed = execution_analysis[
                "verification_passed"
            ]

            failed = execution_analysis[
                "verification_failed"
            ]

            retries = execution_analysis[
                "retry_event_count"
            ]

            task_count = len(
                execution_packages
            )

            query_success = (
                execution_analysis[
                    "query_execution_success"
                ]
            )


            record["metrics"] = {

                "total_latency_seconds":
                    total_elapsed,

                "mediator_latency_seconds":
                    mediator[
                        "latency_seconds"
                    ],

                "retrieval_latency_seconds":
                    retrieval[
                        "latency_seconds"
                    ],

                "execution_latency_seconds":
                    execution[
                        "latency_seconds"
                    ],

                "task_count":
                    task_count,

                "verification_passed":
                    passed,

                "verification_failed":
                    failed,

                "retries":
                    retries,

                "query_success":
                    query_success,

                "execution_percentage_of_total":
                    (
                        execution[
                            "latency_seconds"
                        ]
                        /
                        total_elapsed
                        *
                        100
                    )
                    if total_elapsed
                    else 0,

                "tasks_per_execution_second":
                    (
                        task_count /
                        execution[
                            "latency_seconds"
                        ]
                    )
                    if execution[
                        "latency_seconds"
                    ] > 0
                    else 0
            }


            record["status"] = (
                "success"
                if query_success
                else "failed"
            )


            print(
                f"\nResult: "
                f"{record['status'].upper()}"
            )

            print(
                f"Tasks: {task_count} | "
                f"Passed: {passed} | "
                f"Failed: {failed} | "
                f"Retries: {retries}"
            )

            print(
                f"Total: "
                f"{total_elapsed:.2f}s"
            )


        except Exception as e:

            total_elapsed = (
                time.perf_counter()
                - query_start
            )

            record["status"] = "error"

            record["error"] = {

                "type":
                    type(e).__name__,

                "message":
                    str(e)
            }

            record["metrics"] = {

                "total_latency_seconds":
                    total_elapsed,

                "query_success":
                    False
            }

            print(
                f"\nERROR: "
                f"{type(e).__name__}: {e}"
            )


        # =====================================================
        # SAVE CHECKPOINT
        # =====================================================

        results["queries"].append(
            record
        )

        current_wall_time = (
            time.perf_counter()
            - benchmark_start
        )

        results["summary"] = build_summary(
            results,
            current_wall_time
        )

        save_results(
            results
        )

        print(
            f"\nSaved checkpoint -> "
            f"{OUTPUT_FILE}"
        )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    benchmark_wall_time = (
        time.perf_counter()
        - benchmark_start
    )

    results["summary"] = build_summary(
        results,
        benchmark_wall_time
    )

    save_results(
        results
    )


    summary = results["summary"]

    print("\n")
    print("=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)

    print(
        f"Queries:             "
        f"{summary['completed_queries']}/"
        f"{summary['total_queries']}"
    )

    print(
        f"Successful:          "
        f"{summary['successful_queries']}"
    )

    print(
        f"Failed/Error:        "
        f"{summary['failed_or_error_queries']}"
    )

    print(
        f"Total tasks:         "
        f"{summary['total_tasks']}"
    )

    print(
        f"Tasks/query:         "
        f"{summary['average_tasks_per_query']:.2f}"
    )

    print(
        f"Verification pass:   "
        f"{summary['verification']['pass_rate_percent']:.2f}%"
    )

    print(
        f"Total retries:       "
        f"{summary['retries']['total_retries']}"
    )

    e2e = summary[
        "latency_seconds"
    ]["end_to_end"]

    if e2e["count"]:

        print(
            f"Mean E2E:            "
            f"{e2e['mean']:.2f}s"
        )

        print(
            f"Median E2E:          "
            f"{e2e['median']:.2f}s"
        )

        print(
            f"Min E2E:             "
            f"{e2e['min']:.2f}s"
        )

        print(
            f"Max E2E:             "
            f"{e2e['max']:.2f}s"
        )

        print(
            f"P95 E2E:             "
            f"{e2e['p95']:.2f}s"
        )

        print(
            f"P99 E2E:             "
            f"{e2e['p99']:.2f}s"
        )

    print(
        f"\nTotal benchmark time: "
        f"{benchmark_wall_time / 60:.2f} minutes"
    )

    print(
        f"\nFull results saved to:"
        f" {Path(OUTPUT_FILE).resolve()}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()