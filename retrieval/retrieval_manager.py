import json

try:
    from .static_retriever import StaticRetriever
    from .dynamic_retriever import DynamicRetriever

except ImportError:

    from static_retriever import StaticRetriever
    from dynamic_retriever import DynamicRetriever


class RetrievalManager:
    """
    Coordinates the retrieval process.

    Responsibilities:
    - Execute Static Retrieval.
    - Execute Dynamic Retrieval.
    - Handle Static -> Dynamic fallback.
    """

    def __init__(self):

        self.static_retriever = StaticRetriever()
        self.dynamic_retriever = DynamicRetriever()

    def retrieve(self, routed_plan):

        retrieval_results = []

        for task in routed_plan:

            # -----------------------------
            # Static Retrieval
            # -----------------------------
            if task["retrieval_source"] == "static":

                static_result = self.static_retriever.retrieve([task])

                if static_result:

                    retrieved_task = static_result[0]

                    # Static context found
                    if retrieved_task["retrieved_context"]:

                        retrieval_results.append(retrieved_task)
                        continue

                # -----------------------------
                # Static failed
                # Fallback to Dynamic
                # -----------------------------

                fallback_task = task.copy()
                fallback_task["retrieval_source"] = "dynamic"

                dynamic_result = self.dynamic_retriever.retrieve(
                    [fallback_task]
                )

                retrieval_results.extend(dynamic_result)

            # -----------------------------
            # Dynamic Retrieval
            # -----------------------------
            elif task["retrieval_source"] == "dynamic":

                dynamic_result = self.dynamic_retriever.retrieve(
                    [task]
                )

                retrieval_results.extend(dynamic_result)

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

        
    ]

    results = manager.retrieve(routed_plan)

    print(json.dumps(results, indent=4))