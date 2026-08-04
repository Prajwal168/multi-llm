import json


class SourceSelector:
    """
    Decides where each retrieval task should retrieve
    its knowledge from.

    Version 1 Routing Logic:

    Rule Engine  -> Static RAG
    Planner LLM  -> Dynamic RAG
    """

    def __init__(self):
        pass

    def select_source(self, retrieval_plan):

        routed_plan = []

        for task in retrieval_plan:

            # Create a copy so we don't modify the original task
            routed_task = task.copy()

            # Route based on who created the retrieval plan
            if task["planner"] == "rule_engine":

                routed_task["retrieval_source"] = "static"

            elif task["planner"] == "planner_llm":

                routed_task["retrieval_source"] = "dynamic"

            else:

                routed_task["retrieval_source"] = "unknown"

            routed_plan.append(routed_task)

        return routed_plan


# ----------------------------------------------------
# Standalone Testing
# ----------------------------------------------------
if __name__ == "__main__":

    selector = SourceSelector()

    retrieval_plan = [

        {
            "task_id": 1,
            "task": "Explain recursion.",
            "knowledge_type": "programming",
            "query": "Explain recursion.",
            "priority": "high",
            "planner": "rule_engine"
        },

        {
            "task_id": 2,
            "task": "Explain quantum tunneling.",
            "knowledge_type": "physics",
            "query": "Quantum tunneling explained",
            "priority": "medium",
            "planner": "planner_llm"
        }

    ]

    routed_plan = selector.select_source(retrieval_plan)

    print(json.dumps(routed_plan, indent=4))