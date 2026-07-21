from ollama import Client


class PlannerLLM:

    def __init__(self):

        self.client = Client(
            host="http://10.134.108.244:11434"
        )

        self.model = "qwen3:8b"

    def plan(self, task):

        response = self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": """
You are a Retrieval Planner.

Your ONLY responsibility is to create a retrieval plan.

For every task:

1. Identify the knowledge domain.
2. Rewrite the task into the best retrieval query.
3. Return ONLY valid JSON.

Do NOT answer the user's question.
Do NOT explain your reasoning.
Do NOT use markdown.
Do NOT include extra text.

Return exactly this format:

{
    "knowledge_type": "...",
    "query": "..."
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


if __name__ == "__main__":

    planner = PlannerLLM()

    task = "Analyze the time complexity of merge sort."

    print("Task:")
    print(task)

    print("\nPlanner Output:\n")

    result = planner.plan(task)

    print(result)