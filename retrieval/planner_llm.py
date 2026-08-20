import json

from ollama import Client
import httpx


class PlannerLLM:

    def __init__(self):

        self.client = Client(
            host="http://10.10.8.147:11434"
        )

        self.model = "qwen3:8b"

    def plan(self, task):

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """
You are a Retrieval Planner.

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
"""
                    },
                    {
                        "role": "user",
                        "content": task
                    }
                ]
            )

            return response["message"]["content"]

        except (httpx.HTTPError, OSError):

            return json.dumps({
                "knowledge_type": "unknown",
                "query": task
            })


if __name__ == "__main__":

    planner = PlannerLLM()

    task = "Analyze the time complexity of merge sort."

    print("Task:")
    print(task)

    print("\nPlanner Output:\n")

    result = planner.plan(task)

    print(result)