from pathlib import Path
import sys
import json
import difflib

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

    Changes vs. the original version:
      1. Queries are normalized (collapse whitespace / trim) before
         embedding, so cosmetic differences like a trailing space
         don't cause "what is SQL" and "what is  SQL " to be treated
         as different queries.
      2. A query that is present but whitespace-only (e.g. "   ")
         is now treated the same as a missing query, instead of
         silently being embedded as-is.
      3. Query embeddings for a batch of tasks are computed in a
         single batched `encode()` call instead of one call per
         task, since most embedding backends have meaningful fixed
         overhead per call. Repeated identical (normalized) queries
         within a batch reuse the same embedding.
      4. Within a single task's results, near-duplicate chunks (e.g.
         two heavily overlapping adjacent chunks from the chunker)
         are filtered out so `top_k` isn't spent on redundant
         content. To make room for this, more candidates than
         `top_k` are fetched from the vector store before filtering.
      5. A failure retrieving context for one task (embedding error,
         vector store error) no longer aborts the whole batch — that
         task gets `retrieved_context: []` and the rest still run.
    """

    def __init__(
        self,
        top_k=5,
        distance_threshold=0.5,
        over_fetch_factor=3,
        dedup_similarity_threshold=0.9
    ):

        self.top_k = top_k
        self.distance_threshold = distance_threshold

        # How many extra candidates to pull from the vector store
        # before threshold-filtering and dedup, so that removing
        # near-duplicates still leaves up to `top_k` results.
        self.over_fetch_factor = over_fetch_factor

        # Two chunk contents at or above this text-similarity ratio
        # are treated as near-duplicates; the better-scoring one
        # (lower distance) is kept.
        self.dedup_similarity_threshold = dedup_similarity_threshold

        self.embedder = Embedder()
        self.vector_store = VectorStore()

    # ==========================================================
    # QUERY NORMALIZATION
    # ==========================================================

    def _normalize_query(self, query):

        """
        Collapses internal/leading/trailing whitespace so cosmetic
        differences in query text don't change embedding or caching
        behavior. Returns "" for an empty or whitespace-only query.
        """

        if not query:
            return ""

        return " ".join(str(query).split())

    # ==========================================================
    # NEAR-DUPLICATE DETECTION
    # ==========================================================

    def _is_near_duplicate(self, content, kept_contents):

        """
        Checks whether `content` is a near-duplicate of any already
        kept chunk, using text similarity rather than embeddings —
        the vector store's search results here don't include the
        chunk vectors, only the text and its distance to the query.
        """

        normalized = " ".join(content.split()).lower()

        for kept in kept_contents:

            ratio = difflib.SequenceMatcher(
                None, normalized, kept
            ).ratio()

            if ratio >= self.dedup_similarity_threshold:
                return True

        return False

    def retrieve(self, tasks):

        retrieval_results = [None] * len(tasks)

        # --------------------------------------------------
        # Normalize every query up front and batch-embed the
        # unique ones in a single encode() call.
        # --------------------------------------------------

        normalized_queries = [
            self._normalize_query(task.get("query"))
            for task in tasks
        ]

        unique_queries = sorted({q for q in normalized_queries if q})

        query_embeddings = {}

        if unique_queries:

            try:

                vectors = self.embedder.model.encode(
                    unique_queries,
                    convert_to_numpy=True,
                    normalize_embeddings=True
                )

                for query, vector in zip(unique_queries, vectors):
                    query_embeddings[query] = vector.tolist()

            except Exception:
                # If batch embedding fails outright, leave
                # query_embeddings empty; each task falls back to
                # retrieved_context: [] below rather than crashing
                # the whole batch.
                query_embeddings = {}

        for index, task in enumerate(tasks):

            task_result = task.copy()

            normalized_query = normalized_queries[index]

            # --------------------------------------------------
            # No query, or a query embedding wasn't available.
            # --------------------------------------------------

            if not normalized_query or normalized_query not in query_embeddings:

                task_result["retrieved_context"] = []

                retrieval_results[index] = task_result

                continue

            query_embedding = query_embeddings[normalized_query]

            # --------------------------------------------------
            # Search Vector DB. Over-fetch so that filtering out
            # near-duplicates still leaves room for `top_k` results.
            # A per-task failure here doesn't abort the batch.
            # --------------------------------------------------

            try:

                search_results = self.vector_store.search(
                    query_embedding,
                    top_k=self.top_k * self.over_fetch_factor
                )

            except Exception:

                task_result["retrieved_context"] = []

                retrieval_results[index] = task_result

                continue

            # Defensive: don't assume the vector store guarantees
            # ascending-distance ordering.
            search_results = sorted(
                search_results,
                key=lambda result: result["score"]
            )

            retrieved_context = []
            kept_contents = []

            for result in search_results:

                distance = result["score"]

                # Lower distance = better match
                if distance > self.distance_threshold:
                    continue

                content = result["content"]

                if self._is_near_duplicate(content, kept_contents):
                    continue

                retrieved_context.append({
                    "content": content,
                    "domain": result["domain"],
                    "source": result["source"],
                    "score": distance
                })

                kept_contents.append(
                    " ".join(content.split()).lower()
                )

                if len(retrieved_context) >= self.top_k:
                    break

            # --------------------------------------------------
            # Attach context to task
            # --------------------------------------------------

            task_result["retrieved_context"] = retrieved_context

            retrieval_results[index] = task_result

        return retrieval_results


# ==========================================================
# Standalone Testing
# ==========================================================

if __name__ == "__main__":

    retriever = StaticRetriever(
        top_k=3,
        distance_threshold=0.5
    )

    test_tasks = [
        {
            "task_id": 1,
            "task": "Explain the concept of recursion in Python.",
            "knowledge_type": "programming",
            "query": "Explain recursion.",
            "priority": "high",
            "planner": "rule_engine",
            "retrieval_source": "static"
        },
        {
            "task_id": 2,
            "task": "what is  SQL ",
            "knowledge_type": "programming",
            "query": "what is  SQL",
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
            "task_id": 4,
            "task": "Example for  recursion .",
            "knowledge_type": "programming",
            "query": "Recursion example",
            "priority": "medium",
            "planner": "rule_engine",
            "retrieval_source": "static"
        },
        {
            "task_id": 5,
            "task": "explain the types of joins in sql .",
            "knowledge_type": "programming",
            "query": "Types of joins in SQL",
            "priority": "medium",
            "planner": "rule_engine",
            "retrieval_source": "static"
        }
    ]

    results = retriever.retrieve(test_tasks)

    print(json.dumps(results, indent=4))