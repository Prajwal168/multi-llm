"""Generates tasks.json (seed set). Edit/extend here, then re-run."""
import json

def g(i, text, deps=None):
    return {"id": i, "text": text, "depends_on": deps or []}

T = []

def add(id, stratum, query, gold, tags=None, content=None, evidence="", fmt="", fault_query=None, faulted_gold_id=None):
    t = {
        "id": id, "stratum": stratum, "query": query, "gold_subtasks": gold,
        "tags": {"needs_web": False, "near_synonym": False, "user_submission": False, **(tags or {})},
        "success_criteria": {
            "content": content or [],
            "evidence": evidence or "Claims must be supported by the retrieved evidence or the user's submission; no unsupported claims.",
            "format": fmt or "Addresses every requested part; readable Markdown.",
        },
    }
    if fault_query:
        t["fault_query"] = fault_query
        t["faulted_gold_id"] = faulted_gold_id
    T.append(t)

# ---------------- S1: simple single-step (paper predicts small/negative gain)
add("S1-01", "S1",
    "What is the difference between a list and a tuple in Python?",
    [g("g1", "Explain the differences between Python lists and tuples")],
    content=["States that lists are mutable and tuples are immutable"])

add("S1-02", "S1",
    "Explain the concept of method overloading in Python.",
    [g("g1", "Explain method overloading in Python, including that Python does not support it natively")],
    tags={"near_synonym": True},
    content=["Addresses method overloading specifically, not operator overloading",
             "States that a later def with the same name replaces the earlier one"])

add("S1-03", "S1",
    "Explain the error in this code and give the corrected version:\n\n"
    "def average(nums):\n    total = 0\n    for n in nums:\n        total += n\n    return total / len(nums)\n\n"
    "print(average([]))",
    [g("g1", "Explain the error in the provided average function (ZeroDivisionError on an empty list)"),
     g("g2", "Provide a corrected version of the average function", ["g1"])],
    tags={"user_submission": True},
    content=["Identifies ZeroDivisionError caused by len(nums) == 0", "Corrected code handles the empty list"])

# ---------------- S2: multiple evidence types
add("S2-01", "S2",
    "Explain how TCP congestion control works, compare it with UDP's lack of congestion control, and summarize recent alternatives such as BBR.",
    [g("g1", "Explain how TCP congestion control works"),
     g("g2", "Compare TCP congestion control with UDP's lack of congestion control", ["g1"]),
     g("g3", "Summarize recent congestion-control alternatives such as BBR")],
    tags={"needs_web": True})

add("S2-02", "S2",
    "Explain how B-tree and hash indexes work in a relational database, compare them, and give guidance on when to use each.",
    [g("g1", "Explain how B-tree indexes work"),
     g("g2", "Explain how hash indexes work"),
     g("g3", "Compare B-tree and hash indexes and give guidance on when to use each", ["g1", "g2"])])

add("S2-03", "S2",
    "Define retrieval-augmented generation, describe how chunking affects retrieval quality, and summarize current approaches to evaluating RAG systems.",
    [g("g1", "Define retrieval-augmented generation"),
     g("g2", "Describe how chunking affects retrieval quality"),
     g("g3", "Summarize current approaches to evaluating RAG systems")],
    tags={"needs_web": True})

# ---------------- S3: dependent multi-step, >=2 independent branches
add("S3-01", "S3",
    "Write a Python function that computes Fibonacci numbers using plain recursion and a second version using memoization, explain each version, and compare their time complexity.",
    [g("g1", "Write a plain recursive Python Fibonacci function"),
     g("g2", "Write a memoized Python Fibonacci function"),
     g("g3", "Explain the plain recursive version", ["g1"]),
     g("g4", "Explain the memoized version", ["g2"]),
     g("g5", "Compare the time complexity of the two versions", ["g1", "g2"])],
    fault_query="Write a Python function that computes Fibonacci numbers using plain recursion and a second version using zq@@## ~~[corrupted instruction]~~ ??, explain each version, and compare their time complexity.",
    faulted_gold_id="g2")

add("S3-02", "S3",
    "Design a SQLite schema for student attendance, design FastAPI endpoints for marking and viewing attendance, then write the attendance-marking module in Python 3.11 and pytest tests for it.",
    [g("g1", "Design a SQLite schema for student attendance"),
     g("g2", "Design FastAPI endpoints for marking and viewing attendance"),
     g("g3", "Write the attendance-marking module in Python 3.11", ["g1", "g2"]),
     g("g4", "Write pytest tests for the attendance-marking module", ["g3"])],
    fault_query="Design a SQLite schema for student attendance, design FastAPI endpoints ##@@ ~~ [corrupted instruction] ?? zzq, then write the attendance-marking module in Python 3.11 and pytest tests for it.",
    faulted_gold_id="g2")

add("S3-03", "S3",
    "Explain merge sort and quicksort separately, implement each in Python, then compare their average and worst-case time complexity.",
    [g("g1", "Explain merge sort"),
     g("g2", "Explain quicksort"),
     g("g3", "Implement merge sort in Python", ["g1"]),
     g("g4", "Implement quicksort in Python", ["g2"]),
     g("g5", "Compare average and worst-case time complexity of merge sort and quicksort", ["g1", "g2"])],
    fault_query="Explain merge sort and quicksort separately, implement each in Python, then compare their average and worst-case time complexity. Also handle: zq@@## ~~[corrupted instruction for quicksort]~~ ??.",
    faulted_gold_id="g2")

# ---------------- S4: explicit traceability
add("S4-01", "S4",
    "Explain the different types of SQL joins and state, for each type, which source in the retrieved material supports your explanation.",
    [g("g1", "Explain the types of SQL joins (inner, left, right, full, cross)"),
     g("g2", "State which retrieved source supports the explanation of each join type", ["g1"])])

add("S4-02", "S4",
    "Describe how recursion works in Python, including base and recursive cases and the recursion depth limit, and cite where each claim comes from.",
    [g("g1", "Describe how recursion works in Python, including base and recursive cases"),
     g("g2", "Describe Python's recursion depth limit"),
     g("g3", "Cite the source of each claim", ["g1", "g2"])])

add("S4-03", "S4",
    "Trace this code and explain its output, citing the material that supports your explanation:\n\n"
    "def f(a):\n    for i in range(len(a) + 1):\n        print(a[i])\n\nf([1, 2, 3])",
    [g("g1", "Trace the provided code and explain its output (prints 1, 2, 3 then raises IndexError)"),
     g("g2", "Cite the material supporting the explanation", ["g1"])],
    tags={"user_submission": True},
    content=["States the output is 1, 2, 3 followed by an IndexError", "Attributes the IndexError to range(len(a) + 1)"])

# ---------------- S5: open-ended generation / reports
add("S5-01", "S5",
    "Write a short report on the trade-offs between a monolithic and a microservices architecture for a university attendance system, suitable for a project review.",
    [g("g1", "Describe monolithic architecture for a university attendance system"),
     g("g2", "Describe microservices architecture for a university attendance system"),
     g("g3", "Compare the trade-offs of the two architectures", ["g1", "g2"]),
     g("g4", "Give a recommendation suitable for a project review", ["g3"])])

add("S5-02", "S5",
    "Write a report explaining how retrieval-augmented generation reduces hallucination in LLMs and where it still fails.",
    [g("g1", "Explain how RAG reduces hallucination"),
     g("g2", "Explain where RAG still fails", ["g1"])],
    tags={"needs_web": True})

add("S5-03", "S5",
    "Write an explanatory article for beginners on how the Transformer architecture works, covering attention, positional encoding, and the encoder-decoder structure.",
    [g("g1", "Explain attention for beginners"),
     g("g2", "Explain positional encoding for beginners"),
     g("g3", "Explain the encoder-decoder structure for beginners")],
    fmt="Beginner-friendly article in Markdown covering all three topics.")

json.dump(T, open("tasks.json", "w"), indent=2, ensure_ascii=False)
print(len(T), "tasks written")
