from collections import defaultdict


class RuleEngine:
    """
    Rule-based classifier for identifying the knowledge domain
    required by a task.
    """

    def __init__(self):

        self.domains = {

            "programming": [
                "python",
                "java",
                "c++",
                "javascript",
                "html",
                "css",
                "sql",
                "algorithm",
                "data structure",
                "linked list",
                "tree",
                "graph",
                "stack",
                "queue",
                "recursion",
                "sorting",
                "searching",
                "binary search",
                "dfs",
                "bfs",
                "dynamic programming",
                "api",
                "fastapi",
                "flask",
                "react",
                "node",
                "program",
                "code"
            ],

            "networking": [
                "tcp",
                "udp",
                "ip",
                "routing",
                "packet",
                "congestion",
                "ospf",
                "bgp",
                "dns"
            ],

            "database": [
                "mysql",
                "mongodb",
                "postgres",
                "database",
                "sql query",
                "normalization"
            ],

            "machine_learning": [
                "machine learning",
                "deep learning",
                "cnn",
                "rnn",
                "transformer",
                "llm",
                "rag",
                "neural network"
            ],

            "medical": [
                "disease",
                "symptom",
                "doctor",
                "blood",
                "infection",
                "medicine",
                "treatment",
                "diabetes",
                "fever"
            ],

            "finance": [
                "stock",
                "market",
                "investment",
                "share",
                "crypto",
                "trading"
            ],

            "law": [
                "constitution",
                "legal",
                "court",
                "judge",
                "law"
            ]
        }

    def classify(self, text: str):

        text = text.lower()

        scores = defaultdict(int)

        # Count keyword matches
        for domain, keywords in self.domains.items():

            for keyword in keywords:

                if keyword in text:
                    scores[domain] += 1

        # Nothing matched
        if len(scores) == 0:

            return {
                "knowledge_type": None,
                "confidence": 0.0,
                "scores": {}
            }

        # Highest scoring domain
        best_domain = max(scores, key=scores.get)

        total_score = sum(scores.values())

        confidence = scores[best_domain] / total_score

        return {
            "knowledge_type": best_domain,
            "confidence": round(confidence, 2),
            "scores": dict(scores)
        }
if __name__ == "__main__":

    engine = RuleEngine()

    tests = [

        "Generate a Python recursion program.",

        "Explain diabetes symptoms.",

        "Explain TCP congestion control.",

        "Build a MongoDB database.",

        "What is Retrieval Augmented Generation?",

        "Explain the Constitution of India.",

        "explaiin the concept of tcp and udp"
    ]

    for task in tests:

        print("=" * 50)

        print(task)

        print(engine.classify(task))