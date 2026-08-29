import json

from backend.mediator.mediator import generate_tasks

from retrieval.planner import RetrievalPlanner
from retrieval.source_selector import SourceSelector
from retrieval.retrieval_manager import RetrievalManager
from retrieval.context_builder import ContextBuilder
from execution.executor import Executor


# ==========================================================
# USER INPUT
# ==========================================================

user_prompt = input("Enter task: ")


# ==========================================================
# MEDIATOR
# ==========================================================

mediated_tasks = generate_tasks(user_prompt)


# ==========================================================
# CHECK MEDIATOR OUTPUT
# ==========================================================

if isinstance(mediated_tasks, str):

    # Conversational response
    print(mediated_tasks)

else:

    # ------------------------------------------------------
    # Safety check
    # ------------------------------------------------------

    if not isinstance(mediated_tasks, list):

        print(
            "Invalid Mediator output: expected a task list."
        )

    else:

        print("\nMediator Output:")
        print(
            json.dumps(
                mediated_tasks,
                indent=4
            )
        )


        # ==================================================
        # 1. RETRIEVAL PLANNER
        # ==================================================

        planner = RetrievalPlanner()

        retrieval_plan = planner.create_plan(
            mediated_tasks
        )

        print("\nRetrieval Plan:")
        print(
            json.dumps(
                retrieval_plan,
                indent=4
            )
        )


        # ==================================================
        # 2. SOURCE SELECTOR
        # ==================================================

        selector = SourceSelector()

        routed_plan = selector.select_source(
            retrieval_plan
        )

        print("\nRouted Retrieval Plan:")
        print(
            json.dumps(
                routed_plan,
                indent=4
            )
        )


        # ==================================================
        # 3. RETRIEVAL MANAGER
        # ==================================================

        manager = RetrievalManager()

        retrieval_results = manager.retrieve(
            routed_plan
        )

        print("\nRetrieval Results:")
        print(
            json.dumps(
                retrieval_results,
                indent=4
            )
        )


        # ==================================================
        # 4. CONTEXT BUILDER
        # ==================================================

        builder = ContextBuilder()

        execution_packages = builder.build(
            mediated_tasks,
            retrieval_results
        )

        print("\nFinal Execution Packages:")
        print(
            json.dumps(
                execution_packages,
                indent=4
            )
        )


        # ==================================================
        # 5. EXECUTOR (execution + verification, with retry)
        # ==================================================

        executor = Executor()

        execution_results = executor.execute(
            execution_packages
        )

        print("\nExecution Results (verified):")
        print(
            json.dumps(
                execution_results,
                indent=4
            )
        )