from ollama import Client

from .verifier import Verifier


class Executor:

    def __init__(
        self,
        host="http://10.241.250.48:11434",
        model="qwen3:8b",
        verifier=None,
        max_retries=1
    ):
        self.client = Client(host=host)
        self.model = model

        # Reuse a Verifier instance if one is passed in (e.g. to
        # share a connection or point it at a different model),
        # otherwise spin up a default one against the same host.
        self.verifier = verifier or Verifier(host=host)

        # How many times to retry a task in the executor after a
        # failed verification, before giving up and moving on.
        self.max_retries = max_retries

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
    # EXECUTE + VERIFY (WITH RETRY)
    # ==========================================================

    def _execute_with_verification(
        self,
        package,
        previous_outputs
    ):

        task_id = package["task_id"]
        task = package["task"]
        task_type = package["type"]
        retrieved_context = package.get(
            "retrieved_context",
            []
        )

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

            verification = self.verifier.verify(
                task={"task": task, "type": task_type},
                output=output,
                retrieved_context=retrieved_context,
                dependency_outputs=previous_outputs
            )

            print(
                f"\nVerification for Task {task_id} "
                f"(attempt {attempt}): "
                f"{verification['status'].upper()} "
                f"- {verification['reason']}"
            )

            if verification["status"] == "passed":
                return output, verification, attempt + 1

            # Failed. If we still have retries left, carry the
            # verifier's reason into the next attempt as feedback.
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

        # ------------------------------------------------------
        # Build prompt
        # ------------------------------------------------------

        prompt = self._build_prompt(
            task=task,
            task_type=task_type,
            retrieved_context=retrieved_context,
            previous_outputs=previous_outputs,
            feedback=feedback
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
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are the execution specialist. "
                            "Complete the assigned task using "
                            "the provided knowledge and outputs "
                            "from dependent tasks."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

        except Exception as exc:

            # Surface a clear, non-crashing output so verification
            # can catch and (if retries remain) retry the failure
            # rather than the whole pipeline dying.
            return (
                "EXECUTION ERROR: the model call failed with "
                f"the following exception: {exc}"
            )

        return response["message"]["content"]

    # ==========================================================
    # PROMPT BUILDER
    # ==========================================================

    def _build_prompt(
        self,
        task,
        task_type,
        retrieved_context,
        previous_outputs,
        feedback=None
    ):

        prompt = f"""
Task:
{task}

Task type:
{task_type}
"""

        # ------------------------------------------------------
        # Retrieved knowledge
        # ------------------------------------------------------

        if retrieved_context:

            prompt += """

Retrieved knowledge:
"""

            for index, context in enumerate(
                retrieved_context,
                start=1
            ):

                prompt += (
                    f"\n--- Context {index} ---\n"
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

    execution_packages = [

        {
        "task_id": 1,
        "task": "Explain the concept of recursion in Python.",
        "type": "concept",
        "priority": "high",
        "depends_on": [],
        "knowledge_type": "programming",
        "query": "Explain the concept of recursion in Python.",
        "retrieved_context": [
            {
                "content": "Recursion is useful when processing structures whose shapes can\u2019t be predicted ahead of time. \u2022 Assigned names are local unless declared global or nonlocal . By default, all the names assigned inside a function definition are put in the local scope (the namespace associated with the function call). If you need to assign a name that lives at the top level of the module enclosing the function, you can do so by declaring it in a global statement inside the function. If you need to assign a name that lives in an enclosing def, as of Python 3.0 you can do so by declaring it in a nonlocal statement. \u2022 All other names are enclosing function locals, globals, or built-ins . Names not assigned a value in the function definition are assumed to be enclosing scope locals (in an enclosing def), globals (in the enclosing module\u2019s namespace), or builtins (in the predefined __builtin__ module Python provides). There are a few subtleties to note here.",
                "domain": "programming",
                "source": "documents\\programming\\Learning_Python.pdf",
                "score": 0.3259459137916565
            },
            {
                "content": "Recursive Functions While discussing scope rules near the start of Chapter 17, we briefly noted that Python supports recursive functions\u2014functions that call themselves either directly or indirectly in order to loop. Recursion is a somewhat advanced topic, and it\u2019s relatively rare to see in Python. Still, it\u2019s a useful technique to know about, as it allows programs to traverse structures that have arbitrary and unpredictable shapes. Recursion is even an alternative for simple loops and iterations, though not necessarily the simplest or most efficient one. Summation with Recursion Let\u2019s look at some examples. To sum a list (or other sequence) of numbers, we can either use the built-in sum function or write a more custom version of our own. Here\u2019s what a custom summing function might look like when coded with recursion:\n>>> def mysum(L):\n... if not L:\n... return 0\n... else:\n... return L[0] + mysum(L[1:]) # Call myself",
                "domain": "programming",
                "source": "documents\\programming\\Learning_Python.pdf",
                "score": 0.33909910917282104
            },
            {
                "content": ">>> def mysum(L):\n... if not L:\n... return 0\n... else:\n... return L[0] + mysum(L[1:]) # Call myself\n>>> mysum([1, 2, 3, 4, 5])\nAt each level, this function calls itself recursively to compute the sum of the rest of the list, which is later added to the item at the front. The recursive loop ends and zero is returned when the list becomes empty. When using recursion like this, each open level Figure 19-1. Function execution environment. Functions may obtain input and produce output in a variety of ways, though functions are usually easier to understand and maintain if you use arguments for input and return statements and anticipated mutable argument changes for output. In Python 3, outputs may also take the form of declared nonlocal names that exist in an enclosing function scope. Recursive Functions | 465",
                "domain": "programming",
                "source": "documents\\programming\\Learning_Python.pdf",
                "score": 0.3599058985710144
            },
            {
                "content": ">>> def mysum(L):\n... if not L: return 0\n... return nonempty(L) # Call a function that calls me\n...\n>>> def nonempty(L):\n... return L[0] + mysum(L[1:]) # Indirectly recursive\n...\n>>> mysum([1.1, 2.2, 3.3, 4.4])\n11.0 Loop Statements Versus Recursion Though recursion works for summing in the prior sections\u2019 examples, it\u2019s probably overkill in this context. In fact, recursion is not used nearly as often in Python as in more esoteric languages like Prolog or Lisp, because Python emphasizes simpler procedural statements like loops, which are usually more natural. The while, for example, often makes things a bit more concrete, and it doesn\u2019t require that a function be defined to allow recursive calls:\n>>> L = [1, 2, 3, 4, 5]\n>>> sum = 0\n>>> while L:\n... sum += L[0]\n... L = L[1:]\n...\n>>> sum\nBetter yet, for loops iterate for us automatically, making recursion largely extraneous in most cases (and, in all likelihood, less efficient in terms of memory space and execution time):",
                "domain": "programming",
                "source": "documents\\programming\\Learning_Python.pdf",
                "score": 0.3714852035045624
            },
            {
                "content": "expressions, are passed values, and return results. But writing new functions requires the application of a few additional ideas that haven\u2019t yet been introduced. Moreover, functions behave very differently in Python than they do in compiled languages like C. Here is a brief introduction to the main concepts behind Python functions, all of which we will study in this part of the book: \u2022 def is executable code. Python functions are written with a new statement, the def. Unlike functions in compiled languages such as C, def is an executable statement\u2014your function does not exist until Python reaches and runs the def. In fact, it\u2019s legal (and even occasionally useful) to nest def statements inside if statements, while loops, and even other defs. In typical operation, def statements are coded in module files and are naturally run to generate functions when a module file is first imported. \u2022 def creates an object and assigns it to a name.",
                "domain": "programming",
                "source": "documents\\programming\\Learning_Python.pdf",
                "score": 0.37339818477630615
            },
            {
                "content": "expressions, are passed values, and return results. But writing new functions requires the application of a few additional ideas that haven\u2019t yet been introduced. Moreover, functions behave very differently in Python than they do in compiled languages like C. Here is a brief introduction to the main concepts behind Python functions, all of which we will study in this part of the book: \u2022 def is executable code. Python functions are written with a new statement, the def. Unlike functions in compiled languages such as C, def is an executable statement\u2014your function does not exist until Python reaches and runs the def. In fact, it\u2019s legal (and even occasionally useful) to nest def statements inside if statements, while loops, and even other defs. In typical operation, def statements are coded in module files and are naturally run to generate functions when a module file is first imported. \u2022 def creates an object and assigns it to a name.",
                "domain": "programming",
                "source": "documents\\programming\\Learning_Python.pdf",
                "score": 0.37718647718429565
            }
        ]
    },
    {
        "task_id": 2,
        "task": "Generate a Python program demonstrating recursion.",
        "type": "code_generation",
        "priority": "high",
        "depends_on": [],
        "knowledge_type": "programming",
        "query": "Generate a Python program demonstrating recursion.",
        "retrieved_context": [
            {
                "content": "Recursive Functions While discussing scope rules near the start of Chapter 17, we briefly noted that Python supports recursive functions\u2014functions that call themselves either directly or indirectly in order to loop. Recursion is a somewhat advanced topic, and it\u2019s relatively rare to see in Python. Still, it\u2019s a useful technique to know about, as it allows programs to traverse structures that have arbitrary and unpredictable shapes. Recursion is even an alternative for simple loops and iterations, though not necessarily the simplest or most efficient one. Summation with Recursion Let\u2019s look at some examples. To sum a list (or other sequence) of numbers, we can either use the built-in sum function or write a more custom version of our own. Here\u2019s what a custom summing function might look like when coded with recursion:\n>>> def mysum(L):\n... if not L:\n... return 0\n... else:\n... return L[0] + mysum(L[1:]) # Call myself",
                "domain": "programming",
                "source": "documents\\programming\\Learning_Python.pdf",
                "score": 0.3880983591079712
            },
            {
                "content": ">>> def mysum(L):\n... if not L:\n... return 0\n... else:\n... return L[0] + mysum(L[1:]) # Call myself\n>>> mysum([1, 2, 3, 4, 5])\nAt each level, this function calls itself recursively to compute the sum of the rest of the list, which is later added to the item at the front. The recursive loop ends and zero is returned when the list becomes empty. When using recursion like this, each open level Figure 19-1. Function execution environment. Functions may obtain input and produce output in a variety of ways, though functions are usually easier to understand and maintain if you use arguments for input and return statements and anticipated mutable argument changes for output. In Python 3, outputs may also take the form of declared nonlocal names that exist in an enclosing function scope. Recursive Functions | 465",
                "domain": "programming",
                "source": "documents\\programming\\Learning_Python.pdf",
                "score": 0.4316267967224121
            },
            {
                "content": ">>> def mysum(L):\n... if not L: return 0\n... return nonempty(L) # Call a function that calls me\n...\n>>> def nonempty(L):\n... return L[0] + mysum(L[1:]) # Indirectly recursive\n...\n>>> mysum([1.1, 2.2, 3.3, 4.4])\n11.0 Loop Statements Versus Recursion Though recursion works for summing in the prior sections\u2019 examples, it\u2019s probably overkill in this context. In fact, recursion is not used nearly as often in Python as in more esoteric languages like Prolog or Lisp, because Python emphasizes simpler procedural statements like loops, which are usually more natural. The while, for example, often makes things a bit more concrete, and it doesn\u2019t require that a function be defined to allow recursive calls:\n>>> L = [1, 2, 3, 4, 5]\n>>> sum = 0\n>>> while L:\n... sum += L[0]\n... L = L[1:]\n...\n>>> sum\nBetter yet, for loops iterate for us automatically, making recursion largely extraneous in most cases (and, in all likelihood, less efficient in terms of memory space and execution time):",
                "domain": "programming",
                "source": "documents\\programming\\Learning_Python.pdf",
                "score": 0.4471689462661743
            },
            {
                "content": ">>> def gensquares(N):\n... for i in range(N):\n... yield i ** 2 # Resume here later\n...\nThis function yields a value, and so returns to its caller, each time through the loop; when it is resumed, its prior state is restored and control picks up again immediately after the yield statement. For example, when it\u2019s used in the body of a for loop, control returns to the function after its yield statement each time through the loop:\n>>> for i in gensquares(5): # Resume the function\n... print(i, end=' : ') # Print last yielded value\n...\n>>>\nTo end the generation of values, functions either use a return statement with no value or simply allow control to fall off the end of the function body. If you want to see what is going on inside the for, call the generator function directly:\n>>> x = gensquares(4)",
                "domain": "programming",
                "source": "documents\\programming\\Learning_Python.pdf",
                "score": 0.4569298028945923
            },
            {
                "content": "19. Advanced Function Topics . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 463 Function Design Concepts 463 Recursive Functions 465 Summation with Recursion 465 Coding Alternatives 466 Loop Statements Versus Recursion 467 Handling Arbitrary Structures 468 Function Objects: Attributes and Annotations 469 Indirect Function Calls 469 Function Introspection 470 Function Attributes 471 Function Annotations in 3.0 472 Anonymous Functions: lambda 474 lambda Basics 474 Why Use lambda? 475 How (Not) to Obfuscate Your Python Code 477 Nested lambdas and Scopes 478 Mapping Functions over Sequences: map 479 Functional Programming Tools: filter and reduce 481 20. Iterations and Comprehensions, Part 2 . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .",
                "domain": "programming",
                "source": "documents\\programming\\Learning_Python.pdf",
                "score": 0.4644320607185364
            }
        ]
    },
    {
        "task_id": 3,
        "task": "Explain the generated recursive code.",
        "type": "explanation",
        "priority": "medium",
        "depends_on": [
            2
        ],
        "knowledge_type": None,
        "query": None,
        "retrieved_context": []
    },
    {
        "task_id": 4,
        "task": "Test the recursive code with sample input and output.",
        "type": "testing",
        "priority": "medium",
        "depends_on": [
            2
        ],
        "knowledge_type": None,
        "query": None,
        "retrieved_context": []
    },
    {
        "task_id": 5,
        "task": "Analyze the time and space complexity of the recursive solution.",
        "type": "analysis",
        "priority": "medium",
        "depends_on": [
            2
        ],
        "knowledge_type": "programming",
        "query": "Analyze the time and space complexity of the recursive solution.",
        "retrieved_context": [
            {
                "content": "# Analysis of Time and Space Complexity in Recursive Algorithms\n\n--\n\nListen\n\nShare\n\nIn this article, we\u2019ll delve deeper into the analysis of time and space complexity in recursive algorithms by examining two classic examples: calculating the Fibonacci sequence and binary search. By understanding these examples, you\u2019ll gain fresh insights into the intricacies of recursive algorithms.\n\nPerformance of Recursively Calculating the Fibonacci Sequence\n\nLet\u2019s start by looking at a recursive approach to calculate the Fibonacci sequence.",
                "source": "https://medium.com/@yingpeng0221/analysis-of-time-and-space-complexity-in-recursive-algorithms-5a82ea278046",
                "domain": "programming",
                "score": 0.7892124652862549
            },
            {
                "content": "Let\u2019s analyze the time complexity of this recursive Fibonacci algorithm.\n\nWhen discussing the time complexity of recursive algorithms, we mentioned that the time complexity of a recursive algorithm fundamentally depends on the number of recursive calls * the time complexity of each recursive call .",
                "source": "https://medium.com/@yingpeng0221/analysis-of-time-and-space-complexity-in-recursive-algorithms-5a82ea278046",
                "domain": "programming",
                "score": 0.7243631482124329
            },
            {
                "content": "Consider the following code for example.\n\nThe time complexity of this function is written as T(n) = 2T(n/2) + O(n ). Now to find the time complexity, we need to solve this recurrence. There are mainly three common methods used to solve recurrence relations that arise in the analysis of recursive algorithms.",
                "source": "https://www.geeksforgeeks.org/dsa/how-to-analyse-complexity-of-recurrence-relation/",
                "domain": "programming",
                "score": 0.7129022479057312
            },
            {
                "content": "Analyzing time/space complexity for recursive algorithms\u00e2\u0080\u0094this is the main focus, and I'll use dynamic programming and backtracking as examples.\n\nBefore diving into the concepts and calculations, let me share some practical tips and common pitfalls.",
                "source": "https://labuladong.online/en/algo/essential-technique/complexity-analysis/",
                "domain": "programming",
                "score": 0.7061986923217773
            },
            {
                "content": "## PROBLEM STATEMENT\n\nAnalyzing the complexity of recursive algorithms requires a systematic approach, especially when dealing with non-trivial structures. The core challenges typically revolve around:\n\nDetermining Recurrence Relations: Formulating a mathematical expression that describes the runtime or space usage of a recursive function in terms of its input size and the cost of its recursive calls.",
                "source": "https://www.technetexperts.com/recursive-algorithm-complexity-analysis/",
                "domain": "programming",
                "score": 0.701823353767395
            }
        ]
    }

    ]

    executor = Executor(max_retries=1)

    results = executor.execute(
        execution_packages
    )

    print("\n\n")
    print("=" * 60)
    print("FINAL EXECUTION RESULTS")
    print("=" * 60)

    for result in results:

        print(
            f"\nTASK {result['task_id']} "
            f"[{result['status'].upper()}] "
            f"(attempts: {result['attempts']})"
        )
        print(f"Task: {result['task']}")
        print(f"Reason: {result['reason']}")
        print("-" * 60)
        print(result["output"])

    # Optional: dump the full structured results as JSON, useful if
    # this pipeline feeds into another system downstream.
    import json
    print("\n\n" + "=" * 60)
    print("JSON RESULTS")
    print("=" * 60)
    print(json.dumps(results, indent=2))