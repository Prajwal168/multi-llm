from retrieval.planner import RetrievalPlanner
import json


planner = RetrievalPlanner()

mediated_tasks = [

    {
        "task_id": 1,
        "task": "Explain the concept of recursion.",
        "type": "concept",
        "priority": "high",
        "retrieval": {
            "required": True
        }
    },

    {
        "task_id": 2,
        "task": "Generate the Python program.",
        "type": "code_generation",
        "priority": "high",
        "retrieval": {
            "required": True
        }
    },

    {
        "task_id": 3,
        "task": "Explain the generated program.",
        "type": "explanation",
        "priority": "medium",
        "retrieval": {
            "required": False
        }
    },

    {
        "task_id": 4,
        "task": "Analyze the time complexity.",
        "type": "analysis",
        "priority": "medium",
        "retrieval": {
            "required": True
        }
    }

]

plan = planner.create_plan(mediated_tasks)

print(json.dumps(plan, indent=4))