import queue
import time
from concurrent.futures import ThreadPoolExecutor

from ollama import Client

from .verifier import Verifier


class Executor:

    def __init__(
        self,
        host="http://10.99.39.48:11434",
        model="qwen3:8b",
        verifier=None,
        verifier_host=None,
        max_retries=1,
        max_workers=4
    ):
        self.client = Client(host=host)
        self.model = model

        # Reuse a Verifier instance if one is passed in (e.g. to
        # share a connection or point it at a different model).
        # Otherwise build a fresh one. Important: do NOT default
        # verifier_host to the executor's own `host` here — that
        # was the bug. If the caller doesn't explicitly give us a
        # verifier_host, let Verifier fall back to its own default
        # host, since the executor and verifier are meant to live
        # on separate machines.
        self.verifier = verifier or Verifier(
            **({"host": verifier_host} if verifier_host else {})
        )

        # Keep a plain string of whichever host the verifier actually
        # ended up on, purely for the startup log below. We track this
        # ourselves rather than introspecting self.verifier.client
        # internals, since those are private to the ollama library and
        # not guaranteed stable across versions.
        self._verifier_host_display = (
            verifier_host
            if verifier_host
            else ("(Verifier instance passed in)" if verifier else "default (Verifier's own)")
        )

        # How many times to retry a task in the executor after a
        # failed verification, before giving up and moving on.
        self.max_retries = max_retries

        # Cap on how many tasks run concurrently within a single
        # dependency "level" (see _topological_levels). Independent
        # tasks are dispatched together; this just guards against an
        # unusually wide task graph swamping the Ollama host.
        self.max_workers = max_workers

        # Internal lookup of task_id -> output string, used only to
        # feed dependency content into later prompts. This always
        # holds the *final* attempt's output, whether or not it
        # verified.
        self._outputs = {}

        # Public results: a list of structured records, one per
        # task, in execution order. Mirrors the shape of the input
        # execution_packages so callers don't have to cross-reference
        # two separate dicts to see a task's output/status/reason.
        self.results = []

        # Sanity-check log: print exactly which host each role is
        # pointed at on startup. This is here specifically because
        # the executor's Verifier construction previously (silently)
        # defaulted to the executor's own host instead of the
        # verifier's, so both roles were hitting the same machine
        # without any visible signal that anything was wrong.
        print(
            "\n[Executor init] "
            f"executor -> {host} (model={model}) | "
            f"verifier -> {self._verifier_host_display} "
            f"(model={self.verifier.model})"
        )

    def execute(self, execution_packages):

        self.results = []
        self._outputs = {}

        for package in execution_packages:

            task_id = package["task_id"]
            dependencies = package.get(
                "depends_on",
                []
            )

            # --------------------------------------------------
            # Collect outputs from dependent tasks
            # --------------------------------------------------

            previous_outputs = {}

            for dependency_id in dependencies:

                if dependency_id not in self._outputs:
                    raise ValueError(
                        f"Task {task_id} depends on "
                        f"Task {dependency_id}, "
                        f"but Task {dependency_id} "
                        f"has not been executed."
                    )

                previous_outputs[dependency_id] = (
                    self._outputs[dependency_id]
                )

            # --------------------------------------------------
            # Execute current task, verifying and retrying
            # --------------------------------------------------

            output, verification, attempts = (
                self._execute_with_verification(
                    package,
                    previous_outputs
                )
            )

            # --------------------------------------------------
            # Store result
            # --------------------------------------------------

            self._outputs[task_id] = output

            self.results.append({
                "task_id": task_id,
                "task": package["task"],
                "type": package["type"],
                "depends_on": dependencies,
                "output": output,
                "status": verification["status"],
                "reason": verification["reason"],
                "attempts": attempts
            })

        return self.results

    # ==========================================================
    # STREAMING EXECUTION (dependency-parallel + live progress)
    # ==========================================================
    #
    # Same inputs/outputs as execute(), but:
    #   - tasks with no unmet dependencies on each other run
    #     concurrently instead of strictly one-at-a-time
    #   - yields a progress event the moment each thing happens,
    #     instead of blocking until every task is done
    #
    # Event shapes yielded:
    #   {"type": "executed", "task_id": N}
    #   {"type": "verified", "task_id": N, "task", "type",
    #    "depends_on", "output", "status", "reason", "attempts"}
    #   {"type": "done", "results": [...]}   <- always last

    def execute_stream(self, execution_packages):

        self.results = []
        self._outputs = {}

        packages_by_id = {
            package["task_id"]: package
            for package in execution_packages
        }

        levels = self._topological_levels(execution_packages)

        for level in levels:

            events = queue.Queue()

            with ThreadPoolExecutor(
                max_workers=min(self.max_workers, len(level))
            ) as pool:

                for task_id in level:
                    pool.submit(
                        self._run_task_stream,
                        packages_by_id[task_id],
                        events
                    )

                # Drain events as they arrive from whichever task
                # finishes first, until every task in this level has
                # reported completion. The `with` block above won't
                # return until all submitted work is done, but we
                # don't want to wait for that silently — we want to
                # surface each event the moment it lands.
                finished = 0

                while finished < len(level):

                    event = events.get()

                    if event["type"] == "task_done":
                        finished += 1
                        continue

                    if event["type"] == "verified":

                        self._outputs[event["task_id"]] = (
                            event["output"]
                        )

                        self.results.append({
                            "task_id": event["task_id"],
                            "task": event["task"],
                            "type": event["task_type"],
                            "depends_on": event["depends_on"],
                            "output": event["output"],
                            "status": event["status"],
                            "reason": event["reason"],
                            "attempts": event["attempts"],
                        })

                    yield event

        self.results.sort(key=lambda result: result["task_id"])

        yield {
            "type": "done",
            "results": self.results
        }

    def _run_task_stream(self, package, events):

        task_id = package["task_id"]

        try:

            dependencies = package.get("depends_on", [])

            previous_outputs = {
                dependency_id: self._outputs[dependency_id]
                for dependency_id in dependencies
            }

            output, verification, attempts = (
                self._execute_with_verification(
                    package,
                    previous_outputs,
                    on_event=events.put
                )
            )

            events.put({
                "type": "verified",
                "task_id": task_id,
                "task": package["task"],
                "task_type": package["type"],
                "depends_on": dependencies,
                "output": output,
                "status": verification["status"],
                "reason": verification["reason"],
                "attempts": attempts,
            })

        except Exception as exc:

            # A thread dying silently would leave the level's event
            # loop waiting forever for a "task_done" that never comes.
            # Fail this task clearly instead of hanging the pipeline.
            events.put({
                "type": "verified",
                "task_id": task_id,
                "task": package.get("task", ""),
                "task_type": package.get("type", ""),
                "depends_on": package.get("depends_on", []),
                "output": f"EXECUTION ERROR: {exc}",
                "status": "failed",
                "reason": f"Unhandled exception during execution: {exc}",
                "attempts": 0,
            })

        finally:
            events.put({
                "type": "task_done",
                "task_id": task_id
            })

    def _topological_levels(self, execution_packages):
        """
        Groups tasks into ordered "levels" based on depends_on: every
        task in a level has all of its dependencies satisfied by
        earlier levels, so tasks within the same level are mutually
        independent and safe to run concurrently.
        """

        remaining = {
            package["task_id"]: set(package.get("depends_on", []))
            for package in execution_packages
        }

        # Preserve original task order as a tie-breaker within a level.
        order = [package["task_id"] for package in execution_packages]

        levels = []

        while remaining:

            ready = [
                task_id
                for task_id in order
                if task_id in remaining and not remaining[task_id]
            ]

            if not ready:
                raise ValueError(
                    "Circular or unresolved dependency in execution "
                    f"packages involving tasks: {list(remaining.keys())}"
                )

            levels.append(ready)

            for task_id in ready:
                del remaining[task_id]

            for dependency_ids in remaining.values():
                dependency_ids.difference_update(ready)

        return levels

    # ==========================================================
    # EXECUTE + VERIFY (WITH RETRY)
    # ==========================================================

    def _execute_with_verification(
        self,
        package,
        previous_outputs,
        on_event=None
    ):

        task_id = package["task_id"]
        task = package["task"]
        task_type = package["type"]
        retrieved_context = package.get(
            "retrieved_context",
            []
        )
        raw_query = package.get("raw_query")

        feedback = None
        output = None
        verification = None

        # attempt 0 is the normal run; attempts 1..max_retries are
        # retries that include the verifier's feedback in the prompt.
        for attempt in range(self.max_retries + 1):

            output = self._execute_task(
                package,
                previous_outputs,
                feedback=feedback,
                attempt=attempt
            )

            # Signal "executed" once, after the first attempt produces
            # output. Retries are an internal recovery detail — the
            # caller only needs to know the task has *something* and
            # is now moving into verification.
            if attempt == 0 and on_event:
                on_event({
                    "type": "executed",
                    "task_id": task_id
                })

            verification = self._verify_with_retry(
                task={"task": task, "type": task_type},
                output=output,
                retrieved_context=retrieved_context,
                dependency_outputs=previous_outputs,
                raw_query=raw_query
            )

            print(
                f"\nVerification for Task {task_id} "
                f"(attempt {attempt}): "
                f"{verification['status'].upper()} "
                f"- {verification['reason']}"
            )

            if verification["status"] == "passed":
                return output, verification, attempt + 1

            # Only carry genuine content feedback into the next
            # executor attempt. A transport "error" means the
            # verifier never actually judged this output — re-running
            # the model with a network exception as "reviewer
            # feedback" wouldn't fix anything and just burns a retry.
            if verification["status"] == "failed":
                feedback = verification["reason"]

        # Exhausted all retries and still failing verification.
        # Don't crash the pipeline (downstream tasks may still
        # need *something* to work with) - just flag it clearly.
        print(
            f"\nTask {task_id} did not pass verification after "
            f"{self.max_retries} retr"
            f"{'y' if self.max_retries == 1 else 'ies'}. "
            "Proceeding with the last attempt's output, flagged "
            "as unverified."
        )

        verification = {
            "status": "unverified_failed",
            "reason": verification["reason"]
        }

        return output, verification, self.max_retries + 1

    def _verify_with_retry(
        self,
        task,
        output,
        retrieved_context,
        dependency_outputs,
        raw_query=None,
        transport_retries=2,
        backoff_seconds=3
    ):
        """
        Retries only the verifier call itself on a transport failure
        (dropped connection, timeout, server briefly unreachable) —
        the model's output already exists and doesn't need
        regenerating just because the verifier couldn't be reached.
        """

        verification = None

        for transport_attempt in range(transport_retries + 1):

            verification = self.verifier.verify(
                task=task,
                output=output,
                retrieved_context=retrieved_context,
                dependency_outputs=dependency_outputs,
                raw_query=raw_query
            )

            if verification["status"] != "error":
                return verification

            if transport_attempt < transport_retries:

                print(
                    f"\nVerifier unreachable "
                    f"(attempt {transport_attempt + 1}/"
                    f"{transport_retries + 1}): "
                    f"{verification['reason']}. "
                    f"Retrying in {backoff_seconds}s..."
                )

                time.sleep(backoff_seconds)

        # Verifier stayed unreachable after retries. Surface this
        # distinctly from a content failure so callers (and the UI)
        # can tell "the model rejected this" apart from "we couldn't
        # even ask the model."
        return verification

    # ==========================================================
    # TASK EXECUTION
    # ==========================================================

    def _execute_task(
        self,
        package,
        previous_outputs,
        feedback=None,
        attempt=0
    ):

        task_id = package["task_id"]
        task = package["task"]
        task_type = package["type"]

        retrieved_context = package.get(
            "retrieved_context",
            []
        )

        raw_query = package.get("raw_query")

        # ------------------------------------------------------
        # Build prompt
        # ------------------------------------------------------

        prompt = self._build_prompt(
            task=task,
            task_type=task_type,
            retrieved_context=retrieved_context,
            previous_outputs=previous_outputs,
            feedback=feedback,
            raw_query=raw_query
        )

        print("\n" + "=" * 60)
        label = "EXECUTING" if attempt == 0 else f"RETRYING (attempt {attempt})"
        print(f"{label} TASK {task_id}")
        print("=" * 60)

        print(f"\nTask: {task}")
        print(f"Type: {task_type}")
        print(
            f"Dependencies: "
            f"{package.get('depends_on', [])}"
        )

        if feedback:
            print(f"Feedback from prior verification: {feedback}")

        # ------------------------------------------------------
        # Call Ollama
        # ------------------------------------------------------

        try:
            content = self._stream_chat(
                task_id=task_id,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are the execution specialist. "
                            "Complete the assigned task exactly as "
                            "described. The task description alone "
                            "defines the subject matter and scope — "
                            "never substitute or adopt a different "
                            "subject, even if one appears in the "
                            "retrieved knowledge below.\n\n"
                            "Retrieved knowledge may include worked "
                            "examples, guides, or sample content that "
                            "illustrate a method, structure, or "
                            "format using their own unrelated topic "
                            "(e.g. a 'how to write a research paper' "
                            "guide that demonstrates its advice using "
                            "a sample paper about some other subject). "
                            "In that case, use the guidance and "
                            "structure it demonstrates, but do NOT "
                            "write about that example's topic. Apply "
                            "the technique to the task's actual "
                            "subject instead.\n\n"
                            "Use outputs from dependent tasks as "
                            "given context for continuity."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                # Thinking mode was burning 2000-3000 tokens per call
                # on an invisible <think> block that competed with the
                # actual answer for the same num_predict budget, same
                # issue as the mediator/verifier had. Off for every
                # task type now.
                think=False,
                options={
                    # Generous cap — this is real deliverable content
                    # (code, explanations, analysis), not a small
                    # fixed-shape verdict, so it needs far more room
                    # than the mediator/verifier calls. Just guards
                    # against a runaway generation, not meant to bind
                    # in normal operation.
                    "num_predict": 3000,
                }
            )

        except Exception as exc:

            # Surface a clear, non-crashing output so verification
            # can catch and (if retries remain) retry the failure
            # rather than the whole pipeline dying.
            return (
                "EXECUTION ERROR: the model call failed with "
                f"the following exception: {exc}"
            )

        return content

    # ==========================================================
    # STREAMING CHAT HELPER
    # ==========================================================

    def _stream_chat(self, task_id, messages, think, options):
        """
        Runs an Ollama chat call with stream=True instead of blocking
        until the full response is generated. Content is identical
        either way — this doesn't make generation faster — but it
        lets us print real token/sec numbers per call and see live
        whether a task is stalling out or filling its num_predict
        budget, instead of only finding out after the fact.
        """

        start = time.monotonic()
        chunks = []
        eval_count = None
        eval_duration_ns = None

        for chunk in self.client.chat(
            model=self.model,
            messages=messages,
            think=think,
            options=options,
            stream=True,
        ):
            piece = chunk.get("message", {}).get("content", "")

            if piece:
                chunks.append(piece)

            if chunk.get("done"):
                eval_count = chunk.get("eval_count")
                eval_duration_ns = chunk.get("eval_duration")

        elapsed = time.monotonic() - start
        content = "".join(chunks)

        if eval_count and eval_duration_ns:
            tokens_per_sec = eval_count / (eval_duration_ns / 1e9)
            print(
                f"\n[Task {task_id}] generated {eval_count} tokens "
                f"in {elapsed:.1f}s ({tokens_per_sec:.1f} tok/s)"
            )
        else:
            print(
                f"\n[Task {task_id}] streamed response in "
                f"{elapsed:.1f}s (token count unavailable)"
            )

        return content

    # ==========================================================
    # PROMPT BUILDER
    # ==========================================================

    def _build_prompt(
        self,
        task,
        task_type,
        retrieved_context,
        previous_outputs,
        feedback=None,
        raw_query=None
    ):

        prompt = f"""
Task:
{task}

Task type:
{task_type}
"""

        # ------------------------------------------------------
        # User's original submission (verbatim)
        #
        # The mediator only ever produces short task labels like
        # "Explain the provided code snippet" — it never carries the
        # actual code/document/text the task refers to. This is that
        # original content, forwarded unmodified from the initial
        # query so a task like the one above has something concrete
        # to act on instead of nothing.
        # ------------------------------------------------------

        if raw_query:

            prompt += f"""

User's original submission (verbatim — this may contain the actual
code, document, or content the Task above refers to; treat it as
the primary source of truth over any paraphrase in the Task text):

{raw_query}
"""

        # ------------------------------------------------------
        # Retrieved knowledge
        # ------------------------------------------------------

        if retrieved_context:

            prompt += """

Reference material (background/structure/method only —
NOT the subject to write about; the Task above is the
only source of the actual subject matter):
"""

            for index, context in enumerate(
                retrieved_context,
                start=1
            ):

                prompt += (
                    f"\n--- Reference {index} "
                    f"(source: {context.get('source', 'unknown')}) ---\n"
                    f"{context.get('content', '')}\n"
                )

        # ------------------------------------------------------
        # Previous task outputs
        # ------------------------------------------------------

        if previous_outputs:

            prompt += """

Outputs from dependent tasks:
"""

            for dep_task_id, dep_output in (
                previous_outputs.items()
            ):

                prompt += (
                    f"\n--- Task {dep_task_id} Output ---\n"
                    f"{dep_output}\n"
                )

        # ------------------------------------------------------
        # Verifier feedback from a prior failed attempt
        # ------------------------------------------------------

        if feedback:

            prompt += f"""

A previous attempt at this task was reviewed and REJECTED
by a verifier for the following reason:

"{feedback}"

Correct this issue and produce a new output that fully
satisfies the task.
"""

        prompt += """

Complete the task using the information above.
"""

        return prompt


# ==========================================================
# Standalone Testing
# ==========================================================

if __name__ == "__main__":

    executor = Executor(max_retries=1)