from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.intake_router import resolve_requirements
from graph.state import ATTRIBUTES, AdvisorState, RequirementValue
from retrieval.index import SearchResult
from retrieval.service import retrieve
from synth.topology import select_topology


DEFAULT_GOLD_PATH = Path(__file__).resolve().parent / "gold" / "v0_1_seed.json"


@dataclass
class EvalReport:
    version: str
    metrics: dict[str, float]
    counts: dict[str, int]
    failures: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "metrics": self.metrics,
            "counts": self.counts,
            "failures": self.failures,
        }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _load_gold(path: str | Path = DEFAULT_GOLD_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _section_text(result: SearchResult) -> str:
    return " > ".join(result.chunk.metadata.get("section_path") or [])


def _source_path(result: SearchResult) -> str:
    return str(result.chunk.metadata.get("source_path") or result.chunk.source_path)


def _matches_evidence(result: SearchResult, evidence: dict[str, Any]) -> bool:
    expected_path = evidence.get("path")
    if expected_path and _source_path(result) != expected_path:
        return False

    section = _section_text(result).lower()
    for needle in evidence.get("section_contains") or []:
        if str(needle).lower() not in section:
            return False

    text = f"{result.chunk.text_original}\n{result.chunk.text_for_embedding}".lower()
    for needle in evidence.get("text_contains") or []:
        if str(needle).lower() not in text:
            return False

    return True


def _rank_of_first_match(results: list[SearchResult], evidence: dict[str, Any]) -> int | None:
    for rank, result in enumerate(results, start=1):
        if _matches_evidence(result, evidence):
            return rank
    return None


def _evidence_key(evidence: dict[str, Any]) -> str:
    return json.dumps(evidence, sort_keys=True)


def _ranked_gains(results: list[SearchResult], item: dict[str, Any]) -> list[int]:
    required = item.get("required", [])
    helpful = item.get("helpful", [])
    seen_required: set[str] = set()
    seen_helpful: set[str] = set()
    gains = []

    for result in results:
        gain = 0
        for evidence in required:
            key = _evidence_key(evidence)
            if key not in seen_required and _matches_evidence(result, evidence):
                seen_required.add(key)
                gain = 2
                break
        if gain == 0:
            for evidence in helpful:
                key = _evidence_key(evidence)
                if key not in seen_helpful and _matches_evidence(result, evidence):
                    seen_helpful.add(key)
                    gain = 1
                    break
        gains.append(gain)

    return gains


def _dcg(gains: list[int]) -> float:
    return sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))


def _score_retrieval_item(item: dict[str, Any]) -> tuple[dict[str, float], dict[str, Any] | None]:
    top_k = int(item.get("top_k", 10))
    results = retrieve(
        item["query"],
        namespace=item.get("namespace", "knowledge"),
        top_k=top_k,
        filters=item.get("filters"),
    )
    required = item.get("required", [])
    required_ranks = [_rank_of_first_match(results, evidence) for evidence in required]
    hits = [rank for rank in required_ranks if rank is not None]

    recall = len(hits) / len(required) if required else 1.0
    mrr = 1.0 / min(hits) if hits else 0.0

    gains = _ranked_gains(results, item)
    ideal_gains = sorted(([2] * len(required)) + ([1] * len(item.get("helpful", []))), reverse=True)[:top_k]
    ndcg = _dcg(gains) / _dcg(ideal_gains) if ideal_gains else 1.0

    failure = None
    if recall < 1.0:
        failure = {
            "axis": "retrieval",
            "id": item["id"],
            "recall": recall,
            "top_sections": [_section_text(result) for result in results[:5]],
            "top_sources": [_source_path(result) for result in results[:5]],
        }

    return {"recall": recall, "mrr": mrr, "ndcg": ndcg}, failure


def _score_retrieval(items: list[dict[str, Any]]) -> tuple[dict[str, float], list[dict[str, Any]]]:
    scores = []
    failures = []
    for item in items:
        item_scores, failure = _score_retrieval_item(item)
        scores.append(item_scores)
        if failure:
            failures.append(failure)

    return (
        {
            "retrieval_recall_at_10": _mean([score["recall"] for score in scores]),
            "retrieval_mrr_at_10": _mean([score["mrr"] for score in scores]),
            "retrieval_ndcg_at_10": _mean([score["ndcg"] for score in scores]),
        },
        failures,
    )


def _score_routing_item(item: dict[str, Any]) -> tuple[dict[str, float], dict[str, int], dict[str, Any] | None]:
    state = resolve_requirements(AdvisorState(user_brief=item["scenario"]))
    domain_correct = state.domain_prior == item.get("expected_domain")

    expected_attributes = item.get("expected_attributes") or {}
    attr_total = len(expected_attributes)
    attr_correct = 0
    wrong_attrs = {}
    for attr, expected_value in expected_attributes.items():
        actual_value = state.requirement_vector[attr].value
        if actual_value == expected_value:
            attr_correct += 1
        else:
            wrong_attrs[attr] = {"expected": expected_value, "actual": actual_value}

    pending_total = 0
    pending_correct = 0
    if "expected_pending" in item:
        pending_total = 1
        pending_correct = int(set(state.pending_elicitation) == set(item["expected_pending"]))

    failure = None
    if not domain_correct or wrong_attrs or (pending_total and not pending_correct):
        failure = {
            "axis": "routing",
            "id": item["id"],
            "expected_domain": item.get("expected_domain"),
            "actual_domain": state.domain_prior,
            "wrong_attributes": wrong_attrs,
            "expected_pending": item.get("expected_pending"),
            "actual_pending": state.pending_elicitation,
        }

    return (
        {
            "domain_accuracy": float(domain_correct),
            "attribute_accuracy": attr_correct / attr_total if attr_total else 1.0,
            "pending_accuracy": pending_correct / pending_total if pending_total else 1.0,
        },
        {
            "routing_attribute_total": attr_total,
            "routing_attribute_correct": attr_correct,
            "routing_pending_total": pending_total,
            "routing_pending_correct": pending_correct,
        },
        failure,
    )


def _score_routing(items: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, int], list[dict[str, Any]]]:
    scores = []
    counts = {
        "routing_attribute_total": 0,
        "routing_attribute_correct": 0,
        "routing_pending_total": 0,
        "routing_pending_correct": 0,
    }
    failures = []
    for item in items:
        item_scores, item_counts, failure = _score_routing_item(item)
        scores.append(item_scores)
        for key, value in item_counts.items():
            counts[key] += value
        if failure:
            failures.append(failure)

    metrics = {
        "routing_domain_accuracy": _mean([score["domain_accuracy"] for score in scores]),
        "routing_attribute_accuracy": (
            counts["routing_attribute_correct"] / counts["routing_attribute_total"]
            if counts["routing_attribute_total"]
            else 1.0
        ),
        "routing_pending_accuracy": (
            counts["routing_pending_correct"] / counts["routing_pending_total"]
            if counts["routing_pending_total"]
            else 1.0
        ),
    }
    return metrics, counts, failures


def _gold_requirement_vector(values: dict[str, str | None]) -> dict[str, RequirementValue]:
    vector = {attr: RequirementValue() for attr in ATTRIBUTES}
    for attr, value in values.items():
        vector[attr] = RequirementValue(value=value, source="gold", confidence=1.0)
    return vector


def _score_topology_item(item: dict[str, Any]) -> tuple[float, dict[str, Any] | None]:
    selected = select_topology(_gold_requirement_vector(item["requirement_vector"]))
    expected = item["expected_topology"]
    correct = selected["key"] == expected
    failure = None
    if not correct:
        failure = {
            "axis": "topology",
            "id": item["id"],
            "expected_topology": expected,
            "actual_topology": selected["key"],
        }
    return float(correct), failure


def _score_topology(items: list[dict[str, Any]]) -> tuple[dict[str, float], list[dict[str, Any]]]:
    scores = []
    failures = []
    for item in items:
        score, failure = _score_topology_item(item)
        scores.append(score)
        if failure:
            failures.append(failure)
    accuracy = _mean(scores)
    return {"topology_accuracy": accuracy, "topology_correctness": accuracy}, failures


def run_eval(gold_path: str | Path = DEFAULT_GOLD_PATH) -> EvalReport:
    gold = _load_gold(gold_path)
    retrieval_metrics, retrieval_failures = _score_retrieval(gold.get("retrieval", []))
    routing_metrics, routing_counts, routing_failures = _score_routing(gold.get("routing", []))
    topology_metrics, topology_failures = _score_topology(gold.get("topology", []))

    metrics = {
        **retrieval_metrics,
        **routing_metrics,
        **topology_metrics,
    }
    counts = {
        "retrieval_items": len(gold.get("retrieval", [])),
        "routing_items": len(gold.get("routing", [])),
        "topology_items": len(gold.get("topology", [])),
        **routing_counts,
    }
    failures = retrieval_failures + routing_failures + topology_failures
    return EvalReport(version=gold["version"], metrics=metrics, counts=counts, failures=failures)


def run_smoke_eval() -> dict[str, float]:
    """Backward-compatible entrypoint used by early smoke checks."""

    return run_eval().metrics


def _threshold_failures(report: EvalReport, thresholds: dict[str, float]) -> list[str]:
    failed = []
    for metric, threshold in thresholds.items():
        actual = report.metrics.get(metric)
        if actual is None:
            failed.append(f"{metric}: missing metric, threshold={threshold}")
        elif actual < threshold:
            failed.append(f"{metric}: actual={actual:.3f}, threshold={threshold:.3f}")
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic advisor gold-set evals.")
    parser.add_argument("--gold", default=str(DEFAULT_GOLD_PATH), help="Path to a gold JSON file.")
    parser.add_argument("--gate", action="store_true", help="Exit non-zero when configured thresholds fail.")
    args = parser.parse_args()

    gold = _load_gold(args.gold)
    report = run_eval(args.gold)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))

    if args.gate:
        failures = _threshold_failures(report, gold.get("thresholds", {}))
        if failures:
            raise SystemExit("Eval gate failed:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
