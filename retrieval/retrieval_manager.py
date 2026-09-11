import json

try:
    from .static_retriever import StaticRetriever
    from .dynamic_retriever import DynamicRetriever
    from .retrieval_verifier import RetrievalVerifier

except ImportError:

    from static_retriever import StaticRetriever
    from dynamic_retriever import DynamicRetriever
    from retrieval_verifier import RetrievalVerifier


class RetrievalManager:
    """
    Coordinates the retrieval process.

    Responsibilities:
    - Execute Static Retrieval.
    - Verify static results are actually relevant to the task
      (LLM-judged), not just non-empty.
    - Execute Dynamic Retrieval.
    - Handle Static -> Dynamic fallback.

    Changes vs. the original version:

      Previously, a static result was accepted whenever
      `retrieved_context` was non-empty, with no check on whether
      that context was actually relevant to the task. A chunk can
      sit close to the query in embedding space (a good distance
      score) while still being about the wrong concept — e.g.
      "operator overloading" chunks scoring well for a "method
      overloading" query, because the two concepts sit close
      together in embedding space. Distance scores alone can't
      catch that.

      This version adds an LLM relevance check (RetrievalVerifier)
      for every non-empty static result: it reads the actual task
      text against the actual retrieved content and judges whether
      it genuinely addresses the task, rather than trusting a
      distance score as a proxy for relevance.

      An earlier version of this gate also included a score-based
      pre-filter (require N chunks under some distance threshold)
      to avoid spending an LLM call on obviously-thin results. That
      was removed after empirical testing showed it was miscalibrated
      in practice — it rejected genuinely good static matches (e.g. a
      "recursion" query whose single best chunk scored 0.377 but
      didn't clear a "2 chunks under 0.40" bar) and sent them to
      dynamic retrieval, where they were replaced by noisier scraped
      content. Tuning that threshold correctly would need much more
      calibration data than was available; verifying every non-empty
      result directly avoids that whole class of miscalibration bug,
      at the cost of one more LLM round-trip per static task with any
      content at all (see verifier_max_workers below for the
      concurrency implication of that).

      A task whose static result is empty, or judged not relevant,
      falls back to dynamic retrieval.
    """

    def __init__(
        self,
        verifier_max_workers=1
    ):

        self.static_retriever = StaticRetriever()
        self.dynamic_retriever = DynamicRetriever()

        # verifier_max_workers must not exceed the Ollama server's
        # actual concurrent slot capacity (OLLAMA_NUM_PARALLEL), the
        # same class of issue that caused the WinError 10060 timeout
        # elsewhere in this pipeline. Keep this in step with
        # PlannerLLM's max_workers rather than tuning it separately.
        #
        # Since every non-empty static task now costs one verifier
        # call (there's no score-based pre-filter thinning that
        # count down anymore), this is the setting to watch first if
        # verification starts to bottleneck a run with many static
        # tasks.
        self.retrieval_verifier = RetrievalVerifier(
            max_workers=verifier_max_workers
        )

    def retrieve(self, routed_plan):

        retrieval_results = []

        # -----------------------------
        # Dynamic tasks (either routed dynamic from the start,
        # or fallen back to dynamic after a static miss/rejection)
        # are collected here and sent to DynamicRetriever in ONE
        # batched call, so its internal ThreadPoolExecutor actually
        # has more than one task to run concurrently instead of one
        # full web-search cycle at a time.
        # -----------------------------

        pending_dynamic = []

        # -----------------------------
        # Static results with non-empty context, waiting on LLM
        # relevance verification, collected here so they can be
        # verified in one batched call.
        # -----------------------------

        pending_verification = []

        for task in routed_plan:

            # -----------------------------
            # Static Retrieval
            # -----------------------------
            if task["retrieval_source"] == "static":

                static_result = self.static_retriever.retrieve([task])

                retrieved_task = static_result[0] if static_result else None

                if retrieved_task and retrieved_task["retrieved_context"]:

                    pending_verification.append(retrieved_task)
                    continue

                # -----------------------------
                # Static returned nothing
                # Fallback to Dynamic
                # -----------------------------

                fallback_task = task.copy()
                fallback_task["retrieval_source"] = "dynamic"

                pending_dynamic.append(fallback_task)

            # -----------------------------
            # Dynamic Retrieval
            # -----------------------------
            elif task["retrieval_source"] == "dynamic":

                pending_dynamic.append(task)

        # -----------------------------
        # Batched LLM relevance verification for every non-empty
        # static result.
        # -----------------------------

        if pending_verification:

            verdicts = self.retrieval_verifier.verify_batch([
                (task_result["task"], task_result["retrieved_context"])
                for task_result in pending_verification
            ])

            for task_result, verdict in zip(pending_verification, verdicts):

                if verdict.get("relevant"):

                    task_result["verification_reason"] = verdict.get("reason")

                    retrieval_results.append(task_result)

                else:

                    # -----------------------------
                    # Verifier rejected the static result
                    # Fallback to Dynamic
                    # -----------------------------

                    fallback_task = task_result.copy()
                    fallback_task["retrieval_source"] = "dynamic"
                    fallback_task["static_rejected_reason"] = verdict.get("reason")

                    pending_dynamic.append(fallback_task)

        # -----------------------------
        # Run all pending dynamic tasks together, concurrently.
        # -----------------------------

        if pending_dynamic:

            dynamic_results = self.dynamic_retriever.retrieve(
                pending_dynamic
            )

            retrieval_results.extend(dynamic_results)

        return retrieval_results


# --------------------------------------------------
# Standalone Testing
# --------------------------------------------------

if __name__ == "__main__":

    manager = RetrievalManager()

    routed_plan = [

        {
            "task_id": 1,
            "task": "Explain recursion.",
            "knowledge_type": "programming",
            "query": "Explain recursion.",
            "priority": "high",
            "planner": "rule_engine",
            "retrieval_source": "static"
        },

        {
            "task_id": 2,
            "task": "Explain quantum tunneling.",
            "knowledge_type": "physics",
            "query": "Quantum tunneling explained",
            "priority": "medium",
            "planner": "planner_llm",
            "retrieval_source": "dynamic"
        },

        {
            "task_id": 3,
            "task": "Explain dark matter.",
            "knowledge_type": "astronomy",
            "query": "Dark matter explained",
            "priority": "medium",
            "planner": "planner_llm",
            "retrieval_source": "dynamic"
        },
        {
            "task_id": 4,
            "task": "Explain quantum tunneling.",
            "knowledge_type": "physics",
            "query": "Quantum tunneling explained",
            "priority": "medium",
            "planner": "rule_engine",
            "retrieval_source": "static"
        },

        {
            "task_id": 5,
            "task": "Explain the concept of method overloading in Python.",
            "knowledge_type": "programming",
            "query": "Explain the concept of method overloading in Python.",
            "priority": "high",
            "planner": "rule_engine",
            "retrieval_source": "static"
        },

    ]

    results = manager.retrieve(routed_plan)

    print(json.dumps(results, indent=4))