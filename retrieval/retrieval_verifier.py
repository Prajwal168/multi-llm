import json
import concurrent.futures

from ollama import Client
import httpx


class RetrievalVerifier:
    """
    Judges whether static retrieval's context actually addresses the
    task it was retrieved for — a semantic check on top of the
    distance-score confidence gate in RetrievalManager.

    Why this exists:
    A chunk can sit close to the query in embedding space (a good
    distance score) while still being about the wrong concept — e.g.
    "operator overloading" chunks scoring well for a "method
    overloading" query, because the two concepts are close neighbors
    in embedding space. Distance scores alone can't catch that; this
    reads the actual retrieved text against the actual task text and
    asks whether it genuinely addresses it.

    Mirrors PlannerLLM's shape and settings on purpose (same client,
    same model, same temperature=0 / think=False rationale, same
    batched-via-ThreadPoolExecutor pattern) so it fits the same
    concurrency budget already tuned against the Ollama server's
    single-slot behavior (see the WinError 10060 note in planner.py).
    """

    def __init__(self, max_workers: int = 1):

        self.client = Client(
            host="http://10.99.39.48:11434"
        )

        self.model = "qwen3:8b"
        self.max_workers = max_workers

    def verify(self, task_text, retrieved_context):

        context_text = "\n---\n".join(
            chunk["content"] for chunk in retrieved_context
        )

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a Retrieval Verifier.

Given a TASK and RETRIEVED CONTEXT, decide whether the context
contains information that directly addresses the task's specific
subject matter — not just a related or adjacent topic.

Return ONLY valid JSON.

Schema:

{
    "relevant": true/false,
    "reason": "<short reason>"
}

Examples:

TASK:
Explain the concept of method overloading in Python.

CONTEXT:
Operator overloading lets classes intercept normal Python operations
via specially named methods such as __add__ and __str__.

Output:
{
    "relevant": false,
    "reason": "Context discusses operator overloading, a related but distinct concept from method overloading."
}

TASK:
Explain the concept of recursion in Python.

CONTEXT:
Python supports recursive functions—functions that call themselves
either directly or indirectly in order to loop.

Output:
{
    "relevant": true,
    "reason": "Context directly defines and explains recursion, matching the task."
}
"""  # unchanged
                    },
                    {
                        "role": "user",
                        "content": f"TASK:\n{task_text}\n\nCONTEXT:\n{context_text}"
                    }
                ],
                think=False,
                # Small fixed-shape JSON verdict, same rationale as
                # the mediator/planner/verifier — no reasoning trace
                # needed, and thinking mode was the thing burning
                # 2000-3000 tokens per call in those stages too.
                options={
                    "temperature": 0,
                    "num_predict": 150,
                }
            )

            return json.loads(response["message"]["content"])

        except (httpx.HTTPError, OSError, json.JSONDecodeError):

            # Fail closed, not open: if the verifier itself breaks
            # (timeout, bad JSON, network error), treat the context
            # as NOT relevant rather than silently trusting
            # unverified static content. This trades availability
            # for safety — a verifier outage makes the pipeline more
            # conservative (more dynamic fallbacks) instead of
            # quietly letting possibly-wrong static content through.
            return {
                "relevant": False,
                "reason": "verifier_error"
            }

    def verify_batch(self, pairs):
        """
        Runs verify() for multiple (task_text, retrieved_context)
        pairs concurrently, the same way PlannerLLM.plan_batch()
        batches low-confidence tasks instead of blocking on one
        full Ollama round-trip at a time.
        """

        results = [None] * len(pairs)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:

            future_to_idx = {
                pool.submit(self.verify, task_text, context): idx
                for idx, (task_text, context) in enumerate(pairs)
            }

            for future in concurrent.futures.as_completed(future_to_idx):

                idx = future_to_idx[future]

                try:
                    results[idx] = future.result()

                except Exception as e:

                    results[idx] = {
                        "relevant": False,
                        "reason": f"verifier_error: {e}"
                    }

        return results


if __name__ == "__main__":

    verifier = RetrievalVerifier(max_workers=1)

    pairs = [
        (
            "Explain the concept of method overloading in Python.",
            [
                {"content": "Operator overloading lets classes intercept normal Python operations via specially named methods such as __add__ and __str__."}
            ]
        ),
        (
            "Explain the concept of recursion in Python.",
            [
                {"content": "Python supports recursive functions—functions that call themselves either directly or indirectly in order to loop."}
            ]
        ),
    ]

    for (task_text, context), verdict in zip(pairs, verifier.verify_batch(pairs)):
        print(f"Task: {task_text}\nVerdict: {verdict}\n")