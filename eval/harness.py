from __future__ import annotations


def run_smoke_eval() -> dict[str, float]:
    return {
        "retrieval_recall_at_10": 0.0,
        "routing_attribute_accuracy": 0.0,
        "topology_correctness": 0.0,
    }


if __name__ == "__main__":
    print(run_smoke_eval())

