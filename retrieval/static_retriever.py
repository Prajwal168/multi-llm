from pathlib import Path
import sys
import json

# Allow direct execution:
# python retrieval/static_retriever.py
sys.path.append(str(Path(__file__).resolve().parent))

from embedder import Embedder
from vector_store import VectorStore


class StaticRetriever:
    """
    Retrieves relevant context from the static Vector Database.

    Responsibilities:
    - Convert task queries into embeddings.
    - Search ChromaDB.
    - Apply a relevance threshold.
    - Return retrieved context.
    - Return [] when no sufficiently relevant context is found.
    """

    def __init__(self, top_k=5, distance_threshold=1.0):

        self.top_k = top_k
        self.distance_threshold = distance_threshold

        self.embedder = Embedder()
        self.vector_store = VectorStore()

    def retrieve(self, tasks):

        retrieval_results = []

        for task in tasks:

            task_result = task.copy()

            query = task.get("query")

            # --------------------------------------------------
            # No query
            # --------------------------------------------------

            if not query:

                task_result["retrieved_context"] = []

                retrieval_results.append(task_result)

                continue

            # --------------------------------------------------
            # Create query embedding
            # --------------------------------------------------

            query_embedding = self.embedder.model.encode(
                query,
                convert_to_numpy=True
            ).tolist()

            # --------------------------------------------------
            # Search Vector DB
            # --------------------------------------------------

            search_results = self.vector_store.search(
                query_embedding,
                top_k=self.top_k
            )

            retrieved_context = []

            # --------------------------------------------------
            # Apply relevance threshold
            # --------------------------------------------------

            for result in search_results:

                distance = result["score"]

                # Lower distance = better match
                if distance <= self.distance_threshold:

                    retrieved_context.append({
                        "content": result["content"],
                        "domain": result["domain"],
                        "source": result["source"],
                        "score": distance
                    })

            # --------------------------------------------------
            # Attach context to task
            # --------------------------------------------------

            task_result["retrieved_context"] = retrieved_context

            retrieval_results.append(task_result)

        return retrieval_results


# ==========================================================
# Standalone Testing
# ==========================================================

if __name__ == "__main__":

    retriever = StaticRetriever(
        top_k=3,
        distance_threshold=1.0
    )

    test_tasks = [
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
            "task": "Explain SQL joins.",
            "knowledge_type": "programming",
            "query": "Explain SQL joins.",
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
        }
    ]

    results = retriever.retrieve(test_tasks)

    print(json.dumps(results, indent=4))