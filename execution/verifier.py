import re
import json

from ollama import Client


class Verifier:

    def __init__(
        self,
        host="http://10.241.250.48:11434",
        model="qwen3:8b"
    ):
        self.client = Client(host=host)
        self.model = model

    def verify(
        self,
        task,
        output,
        retrieved_context=None,
        dependency_outputs=None
    ):

        prompt = self._build_prompt(
            task=task,
            output=output,
            retrieved_context=retrieved_context,
            dependency_outputs=dependency_outputs
        )

        try:
            response = self.client.chat(
                model=self.model,
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
                options={
                    # Deterministic judging: we want consistent
                    # pass/fail verdicts, not creative variation.
                    "temperature": 0
                }
            )

        except Exception as exc:

            # Never let a transport/model error crash the pipeline.
            # A verifier that can't reach the model can't vouch for
            # the output, so we fail safe.
            return {
                "status": "failed",
                "reason": (
                    "Verifier call raised an exception: "
                    f"{exc}"
                )
            }

        return self._parse_response(
            response["message"]["content"]
        )

    # ==========================================================
    # PROMPT BUILDER
    # ==========================================================

    def _build_prompt(
        self,
        task,
        output,
        retrieved_context,
        dependency_outputs
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

        if retrieved_context:

            prompt += """

Retrieved context:
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
and dependency outputs (if any). Return ONLY the JSON
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

    # ------------------------------------------------------
    # Task 5
    # ------------------------------------------------------

    task = {
        "task_id": 5,
        "task": "Analyze the time and space complexity of the recursive solution.",
        "type": "analysis"
    }

    # Actual code generated by Task 2
    dependency_outputs = {
        2: """
def mysum(L):
    if not L:
        return 0
    else:
        return L[0] + mysum(L[1:])

numbers = [1, 2, 3, 4, 5]
result = mysum(numbers)
print(f"Sum of {numbers}: {result}")
"""
    }

    # Output generated by Task 5
    output = """
The recursive solution has O(100) time complexity
and O(1) space complexity.
"""

    result = verifier.verify(
        task=task,
        output=output,
        retrieved_context=None,
        dependency_outputs=dependency_outputs
    )

    print("\n")
    print("=" * 60)
    print("VERIFICATION RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2))