import json


class StaticRetriever:
    """
    Retrieves context from the Static Knowledge Base.

    Version 1:
    Uses a simple in-memory knowledge base.

    Later:
    This will be replaced with a Vector Database.
    """

    def __init__(self):

        self.knowledge_base = {

            "programming": [
                "Recursion is a programming technique where a function calls itself.",
                "A recursive algorithm consists of a base case and a recursive case.",
                "Python supports recursion through function calls.",
                "Factorial is a common example of recursion."
            ],

            "networking": [
                "TCP uses a three-way handshake to establish a connection.",
                "TCP congestion control prevents excessive packet loss.",
                "UDP is a connectionless protocol."
            ],

            "database": [
                "SQL is used to query relational databases.",
                "Normalization reduces redundancy in databases.",
                "MongoDB is a NoSQL database."
            ],

            "machine_learning": [
                "Machine Learning enables systems to learn from data.",
                "Neural Networks are inspired by the human brain.",
                "RAG combines retrieval with generation."
            ]
        }

    def retrieve(self, routed_plan):

        retrieval_results = []

        for task in routed_plan:

            # Skip tasks that are not meant for Static RAG
            if task["retrieval_source"] != "static":
                continue

            # Create a copy of the task
            retrieved_task = task.copy()

            knowledge_type = task["knowledge_type"]

            # Retrieve context
            context = self.knowledge_base.get(
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

    retriever = StaticRetriever()

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
            "task": "Explain TCP.",
            "knowledge_type": "networking",
            "query": "Explain TCP.",
            "priority": "high",
            "planner": "rule_engine",
            "retrieval_source": "static"
        },

        {
            "task_id": 3,
            "task": "Explain quantum tunneling.",
            "knowledge_type": "physics",
            "query": "Quantum tunneling explained",
            "priority": "medium",
            "planner": "rule_engine",
            "retrieval_source": "static"
        },
        {
    "task_id": 3,
    "task": "Explain Flask Blueprints.",
    "knowledge_type": "programming",
    "query": "Explain Flask Blueprints.",
    "priority": "medium",
    "planner": "rule_engine",
    "retrieval_source": "static"
}

    ]

    retrieval_results = retriever.retrieve(routed_plan)

    print(json.dumps(retrieval_results, indent=4))