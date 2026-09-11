import json
import concurrent.futures

from ollama import Client
import httpx


class PlannerLLM:

    def __init__(self, max_workers: int = 1):

        self.client = Client(
            host="http://10.35.206.48:11434"
        )

        self.model = "qwen3:8b"
        self.max_workers = max_workers

    def plan(self, task):

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a Retrieval Planner.

Your job is to classify the task into the most appropriate knowledge domain and generate a concise retrieval query.

Return ONLY valid JSON.

Schema:

{
    "knowledge_type": "<domain>",
    "query": "<optimized retrieval query>"
}

Examples:

Task:
Explain quantum entanglement.

Output:
{
    "knowledge_type": "physics",
    "query": "Quantum entanglement explained"
}

Task:
Describe climate change.

Output:
{
    "knowledge_type": "environment",
    "query": "Causes of climate change"
}
"""  # unchanged
                    },
                    {
                        "role": "user",
                        "content": task
                    }
                ],
                think=False,
                # Small fixed-shape JSON verdict, same as the
                # mediator/verifier — no reasoning trace needed, and
                # thinking mode was the thing burning 2000-3000
                # tokens per call here too.
                options={
                    "temperature": 0,
                    "num_predict": 200,
                }
            )

            return response["message"]["content"]

        except (httpx.HTTPError, OSError):

            return json.dumps({
                "knowledge_type": "unknown",
                "query": task
            })

    def plan_batch(self, tasks: list[str]) -> list[str]:
        """Run plan() for multiple tasks concurrently."""

        results = [None] * len(tasks)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_to_idx = {
                pool.submit(self.plan, task): idx
                for idx, task in enumerate(tasks)
            }

            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = json.dumps({
                        "knowledge_type": "unknown",
                        "query": tasks[idx],
                        "error": str(e)
                    })

        return results


if __name__ == "__main__":

    planner = PlannerLLM(max_workers=1)  # bump to 2 once OLLAMA_NUM_PARALLEL=2 is set

    tasks = [
        "Analyze the time complexity of merge sort.",
        "Explain quantum entanglement.",
        "Describe climate change."
    ]

    for t, r in zip(tasks, planner.plan_batch(tasks)):
        print(f"Task: {t}\nOutput: {r}\n")