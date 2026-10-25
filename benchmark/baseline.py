"""
Arm A: single-LLM baseline (paper Section IV-B).

One qwen3:8b call receives the user request plus an UNFILTERED set of
retrieved context from the same Chroma corpus (plain top-k: no distance
threshold, no dedup, no relevance gate, no web) and must plan, answer
and self-validate in that one response. No task graph, no independent
verifier, no larger model.
"""

import json
import re
import time

from ollama import Client

SYSTEM = """You are a single assistant. In ONE response you must:
1. PLAN: list the subtasks needed to fully satisfy the request.
2. ANSWER: complete every subtask, using the provided context where it is useful.
3. VALIDATE: check your own answer against the request and context.

Return ONLY valid JSON:
{
  "plan": ["<subtask 1>", "<subtask 2>"],
  "answer": "<the complete answer, in Markdown>",
  "self_validation": {"status": "passed" or "failed", "reason": "<short reason>"}
}"""


class Baseline:

    def __init__(self, host, model, top_k=5, num_predict=6000):
        from retrieval.static_retriever import StaticRetriever
        self.client = Client(host=host)
        self.model = model
        self.num_predict = num_predict
        # Unfiltered retrieval: infinite threshold, dedup effectively off.
        self.retriever = StaticRetriever(
            top_k=top_k, distance_threshold=float("inf"),
            over_fetch_factor=1, dedup_similarity_threshold=1.01)

    def run(self, query):
        t_all = time.monotonic()
        rec = {"plan": [], "timings": {}}

        t = time.monotonic()
        out = self.retriever.retrieve([{"query": query}])[0]
        ctx = out.get("retrieved_context", [])
        rec["timings"]["retrieval"] = round(time.monotonic() - t, 3)
        rec["contexts"] = [{
            "source": c.get("source"),
            "source_type": "local",
            "content": c.get("content"),
            "score": c.get("score"),
        } for c in ctx]

        user = f"REQUEST:\n{query}\n"
        if ctx:
            user += "\nCONTEXT:\n" + "\n".join(
                f"--- Context {i} ---\n{c['content']}"
                for i, c in enumerate(ctx, 1))

        t = time.monotonic()
        resp = self.client.chat(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": user}],
            think=False,
            format="json",
            options={"temperature": 0, "num_predict": self.num_predict},
        )
        raw = resp["message"]["content"].strip()
        rec["timings"]["generation"] = round(time.monotonic() - t, 3)

        parsed = None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except json.JSONDecodeError:
                    parsed = None

        if isinstance(parsed, dict):
            plan = parsed.get("plan", [])
            rec["plan"] = [str(p) for p in plan] if isinstance(plan, list) else []
            rec["answer"] = str(parsed.get("answer", ""))
            sv = parsed.get("self_validation")
            rec["self_validation"] = sv if isinstance(sv, dict) else None
            rec["parse_error"] = False
        else:
            rec["answer"] = raw
            rec["self_validation"] = None
            rec["parse_error"] = True

        rec["timings"]["total"] = round(time.monotonic() - t_all, 3)
        return rec
