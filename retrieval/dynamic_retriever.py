import json
import requests


class DynamicRetriever:
    """
    Retrieves context from a Dynamic Knowledge Source.

    Version 2:
    Uses Wikipedia's public API as the dynamic knowledge source.

    The task's query is used for searching.
    """

    def __init__(self, top_k=3):

        self.top_k = top_k

        self.api_url = "https://en.wikipedia.org/w/api.php"

        # Identify our application when accessing Wikipedia
        self.headers = {
            "User-Agent": "MultiLLM-RAG/1.0 (educational project)"
        }

    # ==========================================================
    # Wikipedia Search
    # ==========================================================

    def search_wikipedia(self, query):

        try:

            # --------------------------------------------------
            # Search Wikipedia
            # --------------------------------------------------

            search_params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": self.top_k,
                "format": "json"
            }

            response = requests.get(
                self.api_url,
                params=search_params,
                headers=self.headers,
                timeout=10
            )

            response.raise_for_status()

            search_data = response.json()

            search_results = search_data.get(
                "query",
                {}
            ).get(
                "search",
                []
            )

            if not search_results:
                return []

            # --------------------------------------------------
            # Get page IDs
            # --------------------------------------------------

            page_ids = [
                str(result["pageid"])
                for result in search_results
            ]

            # --------------------------------------------------
            # Retrieve page content
            # --------------------------------------------------

            content_params = {
                "action": "query",
                "pageids": "|".join(page_ids),
                "prop": "extracts",
                "explaintext": True,
                "exintro": True,
                "format": "json"
            }

            content_response = requests.get(
                self.api_url,
                params=content_params,
                headers=self.headers,
                timeout=10
            )

            content_response.raise_for_status()

            content_data = content_response.json()

            pages = content_data.get(
                "query",
                {}
            ).get(
                "pages",
                {}
            )

            contexts = []

            # --------------------------------------------------
            # Build Retrieved Context
            # --------------------------------------------------

            for result in search_results:

                page_id = str(result["pageid"])

                page = pages.get(
                    page_id,
                    {}
                )

                extract = page.get(
                    "extract",
                    ""
                ).strip()

                if not extract:
                    continue

                title = page.get(
                    "title",
                    ""
                )

                contexts.append({
                    "content": extract,
                    "source": "Wikipedia",
                    "title": title,
                    "url": (
                        "https://en.wikipedia.org/wiki/"
                        + title.replace(" ", "_")
                    )
                })

            return contexts

        except requests.RequestException as error:

            print(
                f"Dynamic retrieval error: {error}"
            )

            return []

        except Exception as error:

            print(
                f"Unexpected dynamic retrieval error: {error}"
            )

            return []

    # ==========================================================
    # Main Retrieval Function
    # ==========================================================

    def retrieve(self, routed_plan):

        retrieval_results = []

        for task in routed_plan:

            # --------------------------------------------------
            # Only process Dynamic tasks
            # --------------------------------------------------

            if task["retrieval_source"] != "dynamic":
                continue

            # --------------------------------------------------
            # Copy original task
            # --------------------------------------------------

            retrieved_task = task.copy()

            # --------------------------------------------------
            # Get query
            # --------------------------------------------------

            query = task.get(
                "query",
                ""
            )

            # --------------------------------------------------
            # No query
            # --------------------------------------------------

            if not query:

                retrieved_task["retrieved_context"] = []

                retrieval_results.append(
                    retrieved_task
                )

                continue

            # --------------------------------------------------
            # Perform Dynamic Retrieval
            # --------------------------------------------------

            context = self.search_wikipedia(
                query
            )

            # --------------------------------------------------
            # Attach retrieved context
            # --------------------------------------------------

            retrieved_task["retrieved_context"] = context

            retrieval_results.append(
                retrieved_task
            )

        return retrieval_results


# ==========================================================
# Standalone Testing
# ==========================================================

if __name__ == "__main__":

    retriever = DynamicRetriever(
        top_k=3
    )

    routed_plan = [

        {
            "task_id": 1,
            "task": "Explain quantum tunneling.",
            "knowledge_type": "physics",
            "query": "Quantum tunneling",
            "priority": "high",
            "planner": "planner_llm",
            "retrieval_source": "dynamic"
        },

        {
            "task_id": 2,
            "task": "Describe photosynthesis.",
            "knowledge_type": "biology",
            "query": "Photosynthesis",
            "priority": "high",
            "planner": "planner_llm",
            "retrieval_source": "dynamic"
        },

        {
            "task_id": 3,
            "task": "Explain recursion.",
            "knowledge_type": "programming",
            "query": "Python recursion",
            "priority": "high",
            "planner": "rule_engine",
            "retrieval_source": "static"
        },

        {
            "task_id": 4,
            "task": "Explain dark matter.",
            "knowledge_type": "astronomy",
            "query": "Dark matter",
            "priority": "medium",
            "planner": "planner_llm",
            "retrieval_source": "dynamic"
        }
    ]

    retrieval_results = retriever.retrieve(
        routed_plan
    )

    print(
        json.dumps(
            retrieval_results,
            indent=4,
            ensure_ascii=False
        )
    )