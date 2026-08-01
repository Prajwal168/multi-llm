from retrieval.planner import RetrievalPlanner
import json

planner = RetrievalPlanner()

mediated_tasks = [

    # =====================================================
    # Rule Engine (Known Domains)
    # =====================================================
    {
        "task_id": 1,
        "task": "Explain the TCP three-way handshake.",
        "type": "concept",
        "priority": "high",
        "retrieval": {
            "required": True
        }
    },

    {
        "task_id": 2,
        "task": "Write a SQL query to find the second highest salary.",
        "type": "code_generation",
        "priority": "high",
        "retrieval": {
            "required": True
        }
    },

    # =====================================================
    # No Retrieval
    # =====================================================
    {
        "task_id": 3,
        "task": "Combine all specialist responses into a final answer.",
        "type": "response_generation",
        "priority": "medium",
        "retrieval": {
            "required": False
        }
    },

    {
        "task_id": 4,
        "task": "Rewrite the answer in simple English.",
        "type": "rewriting",
        "priority": "medium",
        "retrieval": {
            "required": False
        }
    },

    # =====================================================
    # Planner LLM (Unknown Domains)
    # =====================================================
    {
        "task_id": 5,
        "task": "Explain how black holes are formed.",
        "type": "analysis",
        "priority": "medium",
        "retrieval": {
            "required": True
        }
    },

    {
        "task_id": 6,
        "task": "Describe the process of photosynthesis.",
        "type": "analysis",
        "priority": "medium",
        "retrieval": {
            "required": True
        }
    }

]

plan = planner.create_plan(mediated_tasks)

print(json.dumps(plan, indent=4))