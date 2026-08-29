from ollama import Client


class Synthesizer:

    def __init__(
        self,
        host="http://192.19.4.170:11434",
        model="qwen3:8b"
    ):
        self.client = Client(host=host)
        self.model = model

    def synthesize(self, query, results):

        prompt = self._build_prompt(
            query=query,
            results=results
        )

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """
You are the final response specialist.

You are given the user's original request and the outputs
produced by a set of tasks that were executed and verified
in order to fulfill that request.

Your job is to combine these task outputs into a single,
well-organized, natural response that directly answers the
user's original request.

Rules:

1. Do not mention tasks, task IDs, verification, attempts,
   or any part of the internal pipeline. The user should
   only see a normal, direct answer.
2. Do not fabricate information that isn't supported by the
   task outputs.
3. If a task output is marked as "unverified_failed" or
   "failed", you may still use it if nothing better is
   available, but do not present it with full confidence -
   soften the language or note the uncertainty naturally.
4. Preserve important specifics (code, numbers, steps,
   worked examples, edge cases) from the task outputs
   rather than vaguely summarizing them. Carry over code
   blocks verbatim.
5. Be thorough, not brief. The task outputs were generated
   deliberately - the user should get the substance of all
   of them, not just a minimal answer to the literal query.
   Merge them into sections (using natural headings suited
   to the content, not "Task 1" style labels) rather than
   compressing everything into a short paragraph.
6. Write directly to the user as one cohesive answer, not as
   a list of separate task summaries.

Return ONLY the final response text. No preamble, no JSON,
no explanations about what you did.
"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                options={
                    # Give the model enough room to actually include
                    # every task's content instead of truncating a
                    # multi-section answer early.
                    "num_predict": -1
                }
            )

        except Exception as exc:

            # Never let a transport/model error crash the pipeline.
            # The user still deserves *something* back, even if it's
            # just an honest note that synthesis failed.
            return (
                "The underlying tasks completed, but I ran into an "
                f"error while composing the final response: {exc}"
            )

        return response["message"]["content"].strip()

    # ==========================================================
    # PROMPT BUILDER
    # ==========================================================

    def _build_prompt(self, query, results):

        prompt = f"""
Original user request:
{query}

Task outputs:
"""

        for result in results:

            prompt += (
                f"\n--- Task {result.get('task_id')} "
                f"({result.get('type')}) ---\n"
                f"Task: {result.get('task')}\n"
                f"Verification status: {result.get('status')}\n"
                f"Output:\n{result.get('output')}\n"
            )

        prompt += """

Combine the task outputs above into a single final response
that directly and completely answers the original user
request. Follow the rules given in your instructions.
"""

        return prompt


if __name__ == "__main__":

    synthesizer = Synthesizer()

    query = "write a python code on recursion"

    results = [
      {
      "task_id": 1,
      "task": "Explain the concept of recursion in Python.",
      "type": "concept",
      "depends_on": [],
      "output": "Recursion in Python is a programming technique where a function calls itself directly or indirectly to solve a problem. It is particularly useful for tasks that can be broken down into smaller, similar subproblems, such as traversing nested data structures or performing calculations on lists. Here's a structured explanation:\n\n### **Core Concepts**\n1. **Base Case and Recursive Case**  \n   Every recursive function must have a **base case** to terminate the recursion and a **recursive case** that reduces the problem size. For example, the `mysum` function (from Context 2) sums a list of numbers:  \n   ```python\n   def mysum(L):\n       if not L:          # Base case: empty list\n           return 0\n       else:              # Recursive case\n           return L[0] + mysum(L[1:])  # Sum first element + sum of the rest\n   ```  \n   The base case (`if not L`) stops the recursion when the list is empty, while the recursive step processes smaller sublists until the base case is met.\n\n2. **Breaking Down Problems**  \n   Recursion excels at handling structures with unpredictable shapes (e.g., trees, linked lists). For instance, `mysum` splits the list into the first element and the remaining elements (`L[1:]`), recursively summing the latter until the entire list is processed.\n\n3. **Direct vs. Indirect Recursion**  \n   - **Direct recursion**: A function calls itself (e.g., `mysum` calling `mysum`).  \n   - **Indirect recursion**: A function calls another function, which eventually calls the original function (e.g., `mysum` calling `nonempty`, which calls `mysum` again, as shown in Context 4).\n\n4. **Comparison with Loops**  \n   While recursion is a valid alternative to loops, Python often favors iterative approaches (e.g., `while` or `for` loops) for their simplicity and efficiency. For example, summing a list with a `while` loop (Context 4):  \n   ```python\n   L = [1, 2, 3, 4, 5]\n   sum = 0\n   while L:\n       sum += L[0]\n       L = L[1:]\n   ```  \n   Loops typically use less memory and execute faster than recursive functions, which incur overhead from repeated function calls.\n\n### **Key Considerations**\n- **Infinite Recursion**: Forgetting the base case leads to infinite recursion, causing a `RecursionError`.  \n- **Scope Rules**: Recursive functions must manage variable scoping carefully. Names inside a function are local unless declared `global` or `nonlocal` (Context 1).  \n- **Efficiency**: Recursion can be less efficient in Python due to stack overhead, though it is elegant for certain problems (e.g., tree traversals).\n\n### **When to Use Recursion**\nRecursion is ideal for tasks where the problem size decreases predictably (e.g., factorial computation, Fibonacci sequence) or when the structure is hierarchical (e.g., parsing nested JSON). However, for simple iterations, loops are generally preferred in Python.",
      "status": "passed",
      "reason": "The output accurately explains recursion in Python, referencing context examples like mysum and nonempty, covers base cases, scope rules, and compares recursion with loops. All concepts align with the provided contexts.",
      "attempts": 1
    },
    {
      "task_id": 2,
      "task": "Generate a Python program demonstrating recursion.",
      "type": "code_generation",
      "depends_on": [],
      "output": "Here's a Python program demonstrating recursion using a custom summation function:\n\n```python\ndef mysum(L):\n    \"\"\"Recursively sum elements of a list.\"\"\"\n    if not L:  # Base case: empty list\n        return 0\n    else:  # Recursive case: add first element to sum of remaining list\n        return L[0] + mysum(L[1:])\n\n# Test the recursive function\nnumbers = [1, 2, 3, 4, 5]\nresult = mysum(numbers)\nprint(f\"Sum of {numbers} is: {result}\")\n```\n\n**Output:**\n```\nSum of [1, 2, 3, 4, 5] is: 15\n```\n\n**Explanation:**\n1. The `mysum` function uses recursion to calculate the sum of a list.\n2. **Base case:** When the list is empty (`if not L`), it returns 0 to terminate the recursion.\n3. **Recursive case:** It adds the first element (`L[0]`) to the result of calling `mysum` on the rest of the list (`L[1:]`).\n4. This continues until the entire list is processed, demonstrating how recursion breaks down problems into smaller subproblems.",
      "status": "passed",
      "reason": "The generated code correctly demonstrates recursion with a summation function matching the context examples. It includes proper base case and recursive case, and the test output aligns with expected behavior.",
      "attempts": 1
    },
    {
      "task_id": 3,
      "task": "Explain the generated recursive code.",
      "type": "explanation",
      "depends_on": [
        2
      ],
      "output": "The recursive code in Task 2 implements a function `mysum` to calculate the sum of a list of numbers. Here's a step-by-step explanation:\n\n---\n\n### **1. Function Definition**\n```python\ndef mysum(L):\n    \"\"\"Recursively sum elements of a list.\"\"\"\n```\n- **Purpose**: The function `mysum` takes a list `L` as input and returns the sum of its elements using recursion.\n\n---\n\n### **2. Base Case**\n```python\nif not L:  # Base case: empty list\n    return 0\n```\n- **What it does**: Checks if the list is empty (`not L`). \n- **Why it's important**: This is the **termination condition** for recursion. Without it, the function would call itself infinitely.\n- **Result**: Returns `0` because the sum of an empty list is defined as `0`.\n\n---\n\n### **3. Recursive Case**\n```python\nelse:  # Recursive case: add first element to sum of remaining list\n    return L[0] + mysum(L[1:])\n```\n- **What it does**: \n  - Takes the **first element** of the list (`L[0]`).\n  - Adds it to the result of `mysum(L[1:])`, which is the sum of the **remaining elements** in the list.\n- **How it works**: \n  - The problem is broken into smaller subproblems. For example, to sum `[1, 2, 3, 4, 5]`, it computes `1 + mysum([2, 3, 4, 5])`.\n  - This continues until the base case is reached (empty list), and the results are combined as the recursion \"unwinds.\"\n\n---\n\n### **4. Example Execution**\nFor the input `[1, 2, 3, 4, 5]`, the recursion unfolds as:\n```\nmysum([1,2,3,4,5]) \n= 1 + mysum([2,3,4,5]) \n= 1 + (2 + mysum([3,4,5])) \n= 1 + (2 + (3 + mysum([4,5]))) \n= 1 + (2 + (3 + (4 + mysum([5])))) \n= 1 + (2 + (3 + (4 + (5 + mysum([])))))) \n= 1 + (2 + (3 + (4 + (5 + 0)))) \n= 1 + (2 + (3 + (4 + 5))) \n= 1 + (2 + (3 + 9)) \n= 1 + (2 + 12) \n= 1 + 14 \n= 15\n```\n\n---\n\n### **5. Key Concepts Demonstrated**\n- **Divide and Conquer**: The list is split into smaller sublists until the base case is reached.\n- **Stack Unwinding**: Each recursive call waits for the result of the next call, eventually combining results to compute the final sum.\n- **Simplicity**: Recursion simplifies the logic by avoiding explicit loops.\n\n---\n\n### **6. Test Case Output**\n```python\nnumbers = [1, 2, 3, 4, 5]\nresult = mysum(numbers)\nprint(f\"Sum of {numbers} is: {result}\")\n```\n- **Output**: `Sum of [1, 2, 3, 4, 5] is: 15`\n- **Verification**: The sum of the list is correctly computed as `15`.\n\n---\n\n### **Summary**\nThe `mysum` function uses recursion to sum a list by:\n1. **Base case**: Returning `0` for an empty list.\n2. **Recursive step**: Adding the first element to the sum of the remaining list.\nThis approach elegantly breaks down the problem into smaller, manageable subproblems, demonstrating the power of recursion for iterative tasks.",
      "status": "passed",
      "reason": "The explanation accurately describes the recursive mysum function, matches the code implementation, and correctly demonstrates how recursion works with clear examples and key concepts.",
      "attempts": 1
    },
    {
      "task_id": 4,
      "task": "Test the recursive function with sample input and output.",
      "type": "testing",
      "depends_on": [
        2
      ],
      "output": "The recursive function `mysum` has been successfully tested with various sample inputs, confirming its correctness. Below are the test cases and their expected outputs:\n\n---\n\n### **Test Case 1: Standard Input**\n**Input:**  \n```python\nnumbers = [1, 2, 3, 4, 5]\n```  \n**Expected Output:**  \n```\nSum of [1, 2, 3, 4, 5] is: 15\n```  \n**Result:** ✅ Correct. The function computes the sum as `1+2+3+4+5 = 15`.\n\n---\n\n### **Test Case 2: Empty List**\n**Input:**  \n```python\nresult = mysum([])\n```  \n**Expected Output:**  \n```\n0\n```  \n**Result:** ✅ Correct. The base case returns `0` for an empty list.\n\n---\n\n### **Test Case 3: Single Element**\n**Input:**  \n```python\nresult = mysum([7])\n```  \n**Expected Output:**  \n```\n7\n```  \n**Result:** ✅ Correct. The function returns the single element directly.\n\n---\n\n### **Test Case 4: Mixed Numbers**\n**Input:**  \n```python\nresult = mysum([10, -3, 2])\n```  \n**Expected Output:**  \n```\n9\n```  \n**Result:** ✅ Correct. The sum is `10 + (-3) + 2 = 9`.\n\n---\n\n### **Test Case 5: Larger List**\n**Input:**  \n```python\nresult = mysum([2, 4, 6, 8])\n```  \n**Expected Output:**  \n```\n20\n```  \n**Result:** ✅ Correct. The sum is `2+4+6+8 = 20`.\n\n---\n\n### **Conclusion**  \nThe `mysum` function works as intended for all tested cases, demonstrating proper recursion with base case termination and correct subproblem decomposition.",
      "status": "passed",
      "reason": "The generated output matches the expected behavior of the recursive mysum function from the dependency task. All test cases align with the function's implementation and correctly verify its functionality.",
      "attempts": 1
    },
    {
      "task_id": 5,
      "task": "Analyze the time and space complexity of the recursive solution.",
      "type": "analysis",
      "depends_on": [
        2
      ],
      "output": "The recursive solution provided in the `mysum` function has the following time and space complexity:\n\n---\n\n### **Time Complexity: O(n)**  \n- **Analysis**:  \n  The function processes each element of the list exactly once. For a list of size `n`, the recurrence relation is:  \n  $$\n  T(n) = T(n-1) + O(1)\n  $$  \n  Solving this recurrence yields $ T(n) = O(n) $, as each recursive call reduces the problem size by 1 and the non-recursive work is constant.  \n\n---\n\n### **Space Complexity: O(n)**  \n- **Analysis**:  \n  The recursion depth equals the length of the list (`n`), as each call processes a sublist of size `n-1`, `n-2`, ..., `0`. This results in a call stack depth of `O(n)`.  \n  Additionally, no auxiliary data structures are used, so the space complexity is dominated by the call stack.  \n\n---\n\n### **Summary**  \n- **Time Complexity**: Linear ($ O(n) $)  \n- **Space Complexity**: Linear ($ O(n) $)  \n\nThis is due to the single recursive call per step and the linear reduction in problem size.",
      "status": "passed",
      "reason": "The analysis correctly identifies O(n) time and space complexity for the mysum function. The recurrence relation T(n) = T(n-1) + O(1) accurately models the linear time complexity, and the recursion depth of n matches the O(n) space complexity. This aligns with the dependency task's code and context about recursive algorithm analysis.",
      "attempts": 1
    }
  ]

    final_response = synthesizer.synthesize(
        query=query,
        results=results
    )

    print("\n")
    print("=" * 60)
    print("FINAL RESPONSE")
    print("=" * 60)
    print(final_response)