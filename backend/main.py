from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.mediator.mediator import generate_tasks

from retrieval.planner import RetrievalPlanner
from retrieval.source_selector import SourceSelector
from retrieval.retrieval_manager import RetrievalManager
from retrieval.context_builder import ContextBuilder
from execution.executor import Executor


app = FastAPI()


# ==========================================================
# CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
# REQUEST MODELS
# ==========================================================

class MediatorRequest(BaseModel):
    query: str


class RetrievalRequest(BaseModel):
    tasks: list


class ExecutionRequest(BaseModel):
    execution_packages: list

# ==========================================================
# MEDIATOR ENDPOINT
# ==========================================================

@app.post("/api/mediator")
def run_mediator(request: MediatorRequest):

    result = generate_tasks(request.query)

    return {
        "result": result
    }


# ==========================================================
# RETRIEVAL ENDPOINT
# ==========================================================

@app.post("/api/retrieval")
def run_retrieval(request: RetrievalRequest):

    # ------------------------------------------------------
    # 1. Retrieval Planner
    # ------------------------------------------------------

    planner = RetrievalPlanner()

    retrieval_plan = planner.create_plan(
        request.tasks
    )


    # ------------------------------------------------------
    # 2. Source Selector
    # ------------------------------------------------------

    selector = SourceSelector()

    routed_plan = selector.select_source(
        retrieval_plan
    )


    # ------------------------------------------------------
    # 3. Retrieval Manager
    # ------------------------------------------------------

    manager = RetrievalManager()

    retrieval_results = manager.retrieve(
        routed_plan
    )


    # ------------------------------------------------------
    # 4. Context Builder
    # ------------------------------------------------------

    builder = ContextBuilder()

    execution_packages = builder.build(
        request.tasks,
        retrieval_results
    )

    


    # ------------------------------------------------------
    # Return complete retrieval pipeline result
    # ------------------------------------------------------

    return {
        "retrieval_plan": retrieval_plan,
        "routed_plan": routed_plan,
        "retrieval_results": retrieval_results,
        "execution_packages": execution_packages
    }


# ==========================================================
# EXECUTION ENDPOINT
# ==========================================================

@app.post("/api/execution")
def run_execution(request: ExecutionRequest):

    executor = Executor()

    results = executor.execute(
        request.execution_packages
    )

    return {
        "results": results
    }