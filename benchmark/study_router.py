"""
Logs the human-in-the-loop events RQ5 needs (plan approve / reject).

In main.py add:

    from benchmark.study_router import router as study_router
    app.include_router(study_router)

In App.jsx call it from handleContinue / handleReject, e.g.

    fetch("http://127.0.0.1:8000/api/study/event", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({participant, condition, task_id, event: "approve"}), // or "reject"
    });
"""

import json
import time
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
LOG = Path("benchmark/user_study/study_events.jsonl")


class StudyEvent(BaseModel):
    participant: str
    condition: str
    task_id: str
    event: str          # approve | reject | first_output_seen | answer_submitted


@router.post("/api/study/event")
def log_event(e: StudyEvent):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**e.model_dump(), "ts": time.time()}) + "\n")
    return {"ok": True}
