import re
import json
import time

from ollama import Client


class Verifier:

    def __init__(
        self,
        host="http://10.35.206.48:11434",
        model="qwen3:8b"
    ):
        self.client = Client(host=host)
        self.model = model

    def verify(
        self,
        task,
        output,
        retrieved_context=None,
        dependency_outputs=None,
        raw_query=None
    ):

        prompt = self._build_prompt(
            task=task,
            output=output,
            retrieved_context=retrieved_context,
            dependency_outputs=dependency_outputs,
            raw_query=raw_query
        )

        task_id = task.get("task_id", "?")

        try:
            content = self._stream_chat(
                task_id=task_id,
                messages=[
                    {
                        "role": "system",
                        "content": """
You are a verification specialist.

Determine whether the generated output is
consistent with and satisfies the given task.

Consider:
1. The task itself
2. Retrieved context, if provided
3. Outputs of dependency tasks, if provided
4. The user's original submission, if provided (e.g. the actual
   code/document/content the task refers to)
5. Whether every factual or technical claim in the output is
   actually correct — not just whether the output has the right
   shape or covers the right topics

Coverage is not correctness. An output can address every part of
the task (e.g. "explain the error" + "give corrected code") while
being factually wrong about what the code does, why it fails, or
what fixes it. That is a FAIL. Independently check claims like
"this raises an IndexError", "this has O(n) complexity", "this
line causes X" against the actual code or content provided — do
not simply trust the output's own reasoning as evidence it is
correct.

Do not generate a replacement answer.

Return ONLY valid JSON:

{
  "status": "passed" or "failed",
  "reason": "short explanation"
}
"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                # Verifier is a pass/fail judgment call, not a
                # reasoning task — thinking mode was burning tokens
                # on an invisible <think> block before ever reaching
                # the {"status": ...} JSON, same issue as the
                # mediator had.
                think=True,
                options={
                    # Deterministic judging: we want consistent
                    # pass/fail verdicts, not creative variation.
                    "temperature": 0,
                    "num_predict": 800,
                }
            )

        except Exception as exc:

            # Never let a transport/model error crash the pipeline.
            # This is deliberately NOT "failed" — a failed verdict
            # means the verifier looked at the output and rejected
            # it, which the executor treats as content feedback to
            # retry against. A dropped connection or timeout is a
            # different kind of problem: the output was never judged
            # at all, so feeding this exception text back into the
            # executor's next prompt as "reviewer feedback" just
            # confuses the model about a network issue it can't fix.
            return {
                "status": "error",
                "reason": (
                    "Verifier call raised an exception: "
                    f"{exc}"
                )
            }

        return self._parse_response(content)

    # ==========================================================
    # STREAMING CHAT HELPER
    # ==========================================================

    def _stream_chat(self, task_id, messages, think, options):
        """
        Runs an Ollama chat call with stream=True instead of blocking
        until the full response is generated. Content is identical
        either way — this doesn't make generation faster — but it
        lets us print real token/sec numbers per call and see live
        whether a call is stalling out, instead of only finding out
        after the fact.
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
                f"\n[Verifier: Task {task_id}] generated {eval_count} "
                f"tokens in {elapsed:.1f}s ({tokens_per_sec:.1f} tok/s)"
            )
        else:
            print(
                f"\n[Verifier: Task {task_id}] streamed response in "
                f"{elapsed:.1f}s (token count unavailable)"
            )

        return content

    # ==========================================================
    # PROMPT BUILDER
    # ==========================================================

    def _build_prompt(
        self,
        task,
        output,
        retrieved_context,
        dependency_outputs,
        raw_query=None
    ):

        task_description = task.get("task")
        task_type = task.get("type")

        prompt = f"""
Task:
{task_description}

Task type:
{task_type}

Generated output:
{output}
"""

        if raw_query:

            prompt += """

User's original submission (verbatim — the actual code/document/
content the task refers to; use this as the ground truth when
checking whether claims made in the generated output are correct):
"""
            prompt += f"\n{raw_query}\n"

        if retrieved_context:

            prompt += """

Reference material retrieved for this task (background/
structure/method only — this is NOT the required subject.
If the retrieved material happens to be a worked example on
a different topic than the Task above, and the generated
output copied that example's topic instead of addressing the
Task's actual subject, this should FAIL verification):
"""

            for index, context in enumerate(
                retrieved_context,
                start=1
            ):

                prompt += (
                    f"\n--- Context {index} ---\n"
                    f"{context.get('content', '')}\n"
                )

        if dependency_outputs:

            prompt += """

Dependency task outputs:
"""

            for dep_task_id, dep_output in (
                dependency_outputs.items()
            ):

                prompt += (
                    f"\n--- Task {dep_task_id} Output ---\n"
                    f"{dep_output}\n"
                )

        prompt += """

Determine whether the generated output is consistent
with and satisfies the task above, given the context
and dependency outputs (if any), AND whether its factual/
technical claims are actually correct. Return ONLY the JSON
object described in your instructions.
"""

        return prompt

    # ==========================================================
    # RESPONSE PARSING
    # ==========================================================

    def _parse_response(self, raw):

        cleaned = raw.strip()

        if cleaned.startswith("```"):

            cleaned = re.sub(
                r"^```(?:json)?\s*\n?",
                "",
                cleaned
            )
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        parsed = None

        try:
            parsed = json.loads(cleaned)

        except json.JSONDecodeError:

            match = re.search(r"\{.*\}", cleaned, re.DOTALL)

            if match:

                try:
                    parsed = json.loads(match.group(0))

                except json.JSONDecodeError:
                    parsed = None

        if parsed is None:
            return {
                "status": "failed",
                "reason": (
                    "Verifier LLM did not return parseable JSON: "
                    f"{raw.strip()[:200]}"
                )
            }

        status = parsed.get("status")

        if status not in ("passed", "failed"):
            return {
                "status": "failed",
                "reason": (
                    "Verifier LLM returned an invalid status: "
                    f"{status!r}"
                )
            }

        return {
            "status": status,
            "reason": parsed.get(
                "reason",
                "No reason provided."
            )
        }


if __name__ == "__main__":

    verifier = Verifier()