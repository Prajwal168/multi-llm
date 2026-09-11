import json

from dotenv import load_dotenv

# --------------------------------------------------------
# Load .env BEFORE any local modules are imported below.
#
# RetrievalManager -> DynamicRetriever reads TAVILY_API_KEY
# via os.environ.get() at __init__ time. If load_dotenv()
# ran after that import chain executed (or not at all),
# os.environ wouldn't have the key yet and the Tavily
# fallback would silently be unavailable.
# --------------------------------------------------------

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.mediator.mediator import generate_tasks

from retrieval.planner import RetrievalPlanner
from retrieval.source_selector import SourceSelector
from retrieval.retrieval_manager import RetrievalManager
from retrieval.context_builder import ContextBuilder
from execution.executor import Executor


app = FastAPI()


# ==========================================================
# CONCURRENCY
# ==========================================================
#
# Single manually-tuned value for how many concurrent requests any
# component is allowed to send to the Ollama host at once (planner
# LLM batching, execution). Must not exceed the server's actual
# concurrent slot capacity (OLLAMA_NUM_PARALLEL) — going over that
# just queues requests behind each other with no data on the
# socket, which trips a connection timeout (WinError 10060) rather
# than running in parallel. Bump this in one place once the server
# is confirmed to have more concurrent slot capacity (both
# OLLAMA_NUM_PARALLEL set server-side *and* enough VRAM for it).

OLLAMA_MAX_WORKERS = 1


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


class RetrievalFlag(BaseModel):
    required: bool


class TaskItem(BaseModel):
    # Pydantic coerces a numeric-looking string ("3") to int here,
    # and rejects anything that genuinely isn't numeric (e.g. "abc")
    # with a 422 at the API boundary — instead of a mixed-type
    # task_id silently propagating and surfacing as a TypeError
    # three components downstream in ContextBuilder.build().
    task_id: int
    task: str
    type: str
    priority: str
    depends_on: list[int] = []
    retrieval: RetrievalFlag


class RetrievalRequest(BaseModel):
    tasks: list[TaskItem]
    # The user's original, unmodified submission (e.g. a pasted code
    # block, a document, a full question) — the mediator's task list
    # only ever holds short labels like "Explain the provided code
    # snippet", so this is what lets execution actually see the thing
    # being explained/tested/analyzed instead of nothing at all.
    raw_query: str = ""


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
    # 0. Normalize validated tasks back to plain dicts.
    #
    # TaskItem already guaranteed task_id is int (or the request
    # was rejected with a 422 before we got here). The rest of the
    # pipeline (RetrievalPlanner, ContextBuilder, etc.) expects
    # plain dicts with subscript/`.get()` access, not Pydantic
    # model instances.
    # ------------------------------------------------------

    tasks = [task.model_dump() for task in request.tasks]

    # ------------------------------------------------------
    # 1. Retrieval Planner
    # ------------------------------------------------------

    planner = RetrievalPlanner(max_workers=OLLAMA_MAX_WORKERS)

    retrieval_plan = planner.create_plan(
        tasks
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
        tasks,
        retrieval_results,
        raw_query=request.raw_query
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

    executor = Executor(max_workers=OLLAMA_MAX_WORKERS)

    def event_stream():

        # Each line is one JSON event: {"type": "executed", ...},
        # {"type": "verified", ...}, and finally {"type": "done", ...}
        # carrying the same "results" shape the old blocking endpoint
        # returned in one shot. NDJSON keeps this trivial to parse on
        # the frontend without pulling in an SSE client.
        for event in executor.execute_stream(request.execution_packages):
            yield json.dumps(event) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson"
    )