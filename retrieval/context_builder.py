import json


class ContextBuilder:
    """
    Builds the final Execution Packages.

    Responsibilities:
    - Merge retrieval results back into the original task list.
    - Preserve tasks that did not require retrieval.
    - Restore the original execution order.
    """

    def build(self, original_tasks, retrieval_results):

        # Create a lookup table for retrieved tasks
        retrieval_lookup = {
            task["task_id"]: task
            for task in retrieval_results
        }

        execution_packages = []

        for task in original_tasks:

            task_id = task["task_id"]

            # Retrieval task
            if task_id in retrieval_lookup:

                retrieved_task = retrieval_lookup[task_id]

                execution_package = {

                    "task_id": retrieved_task["task_id"],
                    "task": retrieved_task["task"],
                    "type": retrieved_task["type"],
                    "priority": retrieved_task["priority"],
                    "knowledge_type": retrieved_task["knowledge_type"],
                    "query": retrieved_task["query"],
                    "retrieved_context": retrieved_task["retrieved_context"]

                }

            # No Retrieval task
            else:

                execution_package = {

                    "task_id": task["task_id"],

                    "task": task["task"],

                    "type": task["type"],

                    "priority": task["priority"],

                    "knowledge_type": None,

                    "query": None,

                    "retrieved_context": []

                }

            execution_packages.append(execution_package)

        execution_packages.sort(
            key=lambda x: x["task_id"]
        )

        return execution_packages


# --------------------------------------------------
# Standalone Testing
# --------------------------------------------------

if __name__ == "__main__":

    builder = ContextBuilder()

    original_tasks = [

        {
            "task_id": 1,
            "task": "Explain recursion.",
            "type": "concept",
            "priority": "high",
            "retrieval": {
                "required": True
            }
        },

        {
            "task_id": 2,
            "task": "Generate a Python recursion program.",
            "type": "code_generation",
            "priority": "high",
            "retrieval": {
                "required": True
            }
        },

        {
            "task_id": 3,
            "task": "Explain the generated program.",
            "type": "explanation",
            "priority": "medium",
            "retrieval": {
                "required": False
            }
        },

        {
            "task_id": 4,
            "task": "Test the generated program.",
            "type": "testing",
            "priority": "medium",
            "retrieval": {
                "required": False
            }
        },

        {
            "task_id": 5,
            "task": "Explain quantum tunneling.",
            "type": "concept",
            "priority": "medium",
            "retrieval": {
                "required": True
            }
        }

    ]

    retrieval_results = [

        {
            "task_id": 1,
            "task": "Explain recursion.",
            "type": "concept",
            "priority": "high",
            "knowledge_type": "programming",
            "query": "Explain recursion.",
            "retrieved_context": [
                "Recursion is a programming technique.",
                "Python supports recursion."
            ]
        },

        {
            "task_id": 2,
            "task": "Generate a Python recursion program.",
            "type": "code_generation",
            "priority": "high",
            "knowledge_type": "programming",
            "query": "Python recursion",
            "retrieved_context": [
                "Recursion uses a base case."
            ]
        },

        {
            "task_id": 5,
            "task": "Explain quantum tunneling.",
            "type": "concept",
            "priority": "medium",
            "knowledge_type": "physics",
            "query": "Quantum tunneling explained",
            "retrieved_context": [
                "Quantum tunneling allows particles to pass through barriers."
            ]
        }

    ]

    execution_packages = builder.build(
        original_tasks,
        retrieval_results
    )

    print(json.dumps(execution_packages, indent=4))