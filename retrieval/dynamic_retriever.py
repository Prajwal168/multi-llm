import json


class DynamicRetriever:
    """
    Retrieves context from a Dynamic Knowledge Source.

    Version 1:
    Uses a simple in-memory knowledge base.

    Later:
    This will be replaced with
    - Web Search
    - Search APIs
    - Online Knowledge Sources
    """

    def __init__(self):

        self.dynamic_knowledge = {

            "physics": [
                "Quantum tunneling is a quantum mechanical phenomenon in which particles pass through a potential energy barrier.",
                "Quantum tunneling occurs because particles exhibit wave-like behavior."
            ],

            "biology": [
                "Photosynthesis converts light energy into chemical energy.",
                "Chlorophyll absorbs sunlight for photosynthesis."
            ],

            "environment": [
                "Climate change is mainly caused by greenhouse gas emissions.",
                "Global warming results in rising average temperatures."
            ],

            "history": [
                "The Industrial Revolution began in Britain during the 18th century."
            ],

            "economics": [
                "Inflation is a sustained increase in the general price level."
            ]

        }

    def retrieve(self, routed_plan):

        retrieval_results = []

        for task in routed_plan:

            # Skip tasks that are not meant for Dynamic RAG
            if task["retrieval_source"] != "dynamic":
                continue

            # Create a copy of the task
            retrieved_task = task.copy()

            knowledge_type = task["knowledge_type"]

            # Retrieve context
            context = self.dynamic_knowledge.get(
                knowledge_type,
                []
            )

            # Add retrieved context
            retrieved_task["retrieved_context"] = context

            retrieval_results.append(retrieved_task)

        return retrieval_results


# ----------------------------------------------------
# Standalone Testing
# ----------------------------------------------------

if __name__ == "__main__":

    retriever = DynamicRetriever()

    routed_plan = [

        {
            "task_id": 1,
            "task": "Explain quantum tunneling.",
            "knowledge_type": "physics",
            "query": "Quantum tunneling explained",
            "priority": "high",
            "planner": "planner_llm",
            "retrieval_source": "dynamic"
        },

        {
            "task_id": 2,
            "task": "Describe photosynthesis.",
            "knowledge_type": "biology",
            "query": "Photosynthesis process",
            "priority": "high",
            "planner": "planner_llm",
            "retrieval_source": "dynamic"
        },

        {
            "task_id": 3,
            "task": "Explain recursion.",
            "knowledge_type": "programming",
            "query": "Explain recursion",
            "priority": "high",
            "planner": "rule_engine",
            "retrieval_source": "static"
        },

        {
    "task_id": 4,
    "task": "Explain dark matter.",
    "knowledge_type": "astronomy",
    "query": "Dark matter explained",
    "priority": "medium",
    "planner": "planner_llm",
    "retrieval_source": "dynamic"
}

    ]

    retrieval_results = retriever.retrieve(routed_plan)

    print(json.dumps(retrieval_results, indent=4))