from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Callable

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.intake_router import resolve_requirements
from graph.build import build_graph
from graph.state import ATTRIBUTES, AdvisorState, RequirementValue
from retrieval.index import SearchResult
from retrieval.service import retrieve
from synth.topology import select_topology


DEFAULT_GOLD_PATH = Path(__file__).resolve().parent / "gold" / "v0_2_expanded.json"
RetrieveFn = Callable[[str, str, int, dict[str, str] | None], list[SearchResult]]
AnswerFn = Callable[[str], AdvisorState]


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


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil((percentile / 100.0) * len(ordered)) - 1)
    return ordered[min(rank, len(ordered) - 1)]


def _latency_metrics(prefix: str, values: list[float]) -> dict[str, float]:
    return {
        f"{prefix}_latency_ms_mean": _mean(values),
        f"{prefix}_latency_ms_p50": _percentile(values, 50),
        f"{prefix}_latency_ms_p90": _percentile(values, 90),
        f"{prefix}_latency_ms_p95": _percentile(values, 95),
        f"{prefix}_latency_ms_p99": _percentile(values, 99),
        f"{prefix}_latency_ms_max": max(values) if values else 0.0,
    }


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


def _default_retrieve(
    query: str,
    namespace: str,
    top_k: int,
    filters: dict[str, str] | None,
) -> list[SearchResult]:
    return retrieve(query, namespace=namespace, top_k=top_k, filters=filters)


def _score_retrieval_item(
    item: dict[str, Any],
    retrieve_fn: RetrieveFn,
) -> tuple[dict[str, float], dict[str, Any] | None]:
    top_k = int(item.get("top_k", 10))
    started = time.perf_counter()
    results = retrieve_fn(
        item["query"],
        namespace=item.get("namespace", "knowledge"),
        top_k=top_k,
        filters=item.get("filters"),
    )
    latency_ms = (time.perf_counter() - started) * 1000.0
    required = item.get("required", [])
    required_ranks = [_rank_of_first_match(results, evidence) for evidence in required]
    hits = [rank for rank in required_ranks if rank is not None]

    recall = len(hits) / len(required) if required else 1.0
    mrr = 1.0 / min(hits) if hits else 0.0

    gains = _ranked_gains(results, item)
    ideal_gains = sorted(
        ([2] * len(required)) + ([1] * len(item.get("helpful", []))), reverse=True
    )[:top_k]
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

    return {"recall": recall, "mrr": mrr, "ndcg": ndcg, "latency_ms": latency_ms}, failure


def _score_retrieval(
    items: list[dict[str, Any]],
    retrieve_fn: RetrieveFn,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    scores = []
    failures = []
    for item in items:
        item_scores, failure = _score_retrieval_item(item, retrieve_fn)
        scores.append(item_scores)
        if failure:
            failures.append(failure)

    metrics = {
        "retrieval_recall_at_10": _mean([score["recall"] for score in scores]),
        "retrieval_mrr_at_10": _mean([score["mrr"] for score in scores]),
        "retrieval_ndcg_at_10": _mean([score["ndcg"] for score in scores]),
        **_latency_metrics("retrieval", [score["latency_ms"] for score in scores]),
    }
    return metrics, failures


def _score_routing_item(
    item: dict[str, Any],
) -> tuple[dict[str, float], dict[str, int], dict[str, Any] | None]:
    started = time.perf_counter()
    state = resolve_requirements(AdvisorState(user_brief=item["scenario"]))
    latency_ms = (time.perf_counter() - started) * 1000.0
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
            "latency_ms": latency_ms,
        },
        {
            "routing_attribute_total": attr_total,
            "routing_attribute_correct": attr_correct,
            "routing_pending_total": pending_total,
            "routing_pending_correct": pending_correct,
        },
        failure,
    )


def _score_routing(
    items: list[dict[str, Any]],
) -> tuple[dict[str, float], dict[str, int], list[dict[str, Any]]]:
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
        **_latency_metrics("routing", [score["latency_ms"] for score in scores]),
    }
    return metrics, counts, failures


def _gold_requirement_vector(values: dict[str, str | None]) -> dict[str, RequirementValue]:
    vector = {attr: RequirementValue() for attr in ATTRIBUTES}
    for attr, value in values.items():
        vector[attr] = RequirementValue(value=value, source="gold", confidence=1.0)
    return vector


def _score_topology_item(item: dict[str, Any]) -> tuple[float, float, dict[str, Any] | None]:
    started = time.perf_counter()
    selected = select_topology(_gold_requirement_vector(item["requirement_vector"]))
    latency_ms = (time.perf_counter() - started) * 1000.0
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
    return float(correct), latency_ms, failure


def _score_topology(items: list[dict[str, Any]]) -> tuple[dict[str, float], list[dict[str, Any]]]:
    scores = []
    latencies = []
    failures = []
    for item in items:
        score, latency_ms, failure = _score_topology_item(item)
        scores.append(score)
        latencies.append(latency_ms)
        if failure:
            failures.append(failure)
    accuracy = _mean(scores)
    return {
        "topology_accuracy": accuracy,
        "topology_correctness": accuracy,
        **_latency_metrics("topology", latencies),
    }, failures


def _default_answer(scenario: str) -> AdvisorState:
    return build_graph().invoke({"user_brief": scenario})


def _decision_by_area(output: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(decision.get("area")): decision
        for decision in output.get("architecture_decisions", [])
        if decision.get("area")
    }


def _source_matches(source: dict[str, Any], expected: dict[str, Any]) -> bool:
    path = str(source.get("source_path") or "").lower()
    section = str(source.get("section") or "").lower()
    used_by = {str(agent).lower() for agent in source.get("used_by") or []}

    if expected.get("used_by") and str(expected["used_by"]).lower() not in used_by:
        return False
    if expected.get("path_contains") and str(expected["path_contains"]).lower() not in path:
        return False
    for needle in expected.get("section_contains") or []:
        if str(needle).lower() not in section:
            return False
    return True


def _score_answer_item(
    item: dict[str, Any],
    answer_fn: AnswerFn,
) -> tuple[dict[str, float], dict[str, int], dict[str, Any] | None]:
    started = time.perf_counter()
    state = answer_fn(item["scenario"])
    latency_ms = (time.perf_counter() - started) * 1000.0
    output = state.draft_output or {}
    decisions = output.get("architecture_decisions", [])
    decisions_by_area = _decision_by_area(output)
    sources = output.get("sources", [])

    expected_topology = item.get("expected_topology")
    actual_topology = (output.get("topology") or {}).get("key")
    topology_score = float(not expected_topology or actual_topology == expected_topology)

    required_areas = item.get("required_decision_areas") or []
    area_hits = [area for area in required_areas if area in decisions_by_area]
    area_recall = len(area_hits) / len(required_areas) if required_areas else 1.0

    phrase_checks = item.get("required_decision_phrases") or []
    phrase_hits = []
    missing_phrases = []
    for check in phrase_checks:
        area = check["area"]
        decision = decisions_by_area.get(area, {})
        text = f"{decision.get('choice', '')} {decision.get('rationale', '')}".lower()
        missing = [
            phrase for phrase in check.get("contains", []) if str(phrase).lower() not in text
        ]
        if missing:
            missing_phrases.append({"area": area, "missing": missing})
        else:
            phrase_hits.append(area)
    phrase_recall = len(phrase_hits) / len(phrase_checks) if phrase_checks else 1.0

    required_sources = item.get("required_sources") or []
    source_hits = [
        expected
        for expected in required_sources
        if any(_source_matches(source, expected) for source in sources)
    ]
    source_recall = len(source_hits) / len(required_sources) if required_sources else 1.0

    cited_decisions = [decision for decision in decisions if decision.get("source_ids")]
    citation_coverage = len(cited_decisions) / len(decisions) if decisions else 0.0
    min_citation_coverage = float(item.get("min_citation_coverage", 1.0))

    failure = None
    if (
        topology_score < 1.0
        or area_recall < 1.0
        or phrase_recall < 1.0
        or source_recall < 1.0
        or citation_coverage < min_citation_coverage
    ):
        failure = {
            "axis": "answer",
            "id": item["id"],
            "expected_topology": expected_topology,
            "actual_topology": actual_topology,
            "missing_decision_areas": sorted(set(required_areas) - set(area_hits)),
            "missing_decision_phrases": missing_phrases,
            "source_recall": source_recall,
            "citation_coverage": citation_coverage,
        }

    return (
        {
            "topology": topology_score,
            "decision_area_recall": area_recall,
            "decision_phrase_recall": phrase_recall,
            "source_recall": source_recall,
            "citation_coverage": citation_coverage,
            "latency_ms": latency_ms,
        },
        {
            "answer_decisions_total": len(decisions),
            "answer_decisions_cited": len(cited_decisions),
        },
        failure,
    )


def _score_answers(
    items: list[dict[str, Any]],
    answer_fn: AnswerFn | None = None,
) -> tuple[dict[str, float], dict[str, int], list[dict[str, Any]]]:
    scores = []
    counts = {"answer_decisions_total": 0, "answer_decisions_cited": 0}
    failures = []
    scorer = answer_fn or _default_answer
    for item in items:
        item_scores, item_counts, failure = _score_answer_item(item, scorer)
        scores.append(item_scores)
        for key, value in item_counts.items():
            counts[key] += value
        if failure:
            failures.append(failure)

    metrics = {
        "answer_topology_accuracy": _mean([score["topology"] for score in scores]),
        "answer_decision_area_recall": _mean(
            [score["decision_area_recall"] for score in scores]
        ),
        "answer_decision_phrase_recall": _mean(
            [score["decision_phrase_recall"] for score in scores]
        ),
        "answer_source_recall": _mean([score["source_recall"] for score in scores]),
        "answer_citation_coverage": _mean([score["citation_coverage"] for score in scores]),
        **_latency_metrics("answer", [score["latency_ms"] for score in scores]),
    }
    return metrics, counts, failures


def run_eval(
    gold_path: str | Path = DEFAULT_GOLD_PATH,
    retrieve_fn: RetrieveFn | None = None,
    answer_fn: AnswerFn | None = None,
) -> EvalReport:
    gold = _load_gold(gold_path)
    answer_items = gold.get("answer", [])
    retrieval_metrics, retrieval_failures = _score_retrieval(
        gold.get("retrieval", []), retrieve_fn or _default_retrieve
    )
    routing_metrics, routing_counts, routing_failures = _score_routing(gold.get("routing", []))
    topology_metrics, topology_failures = _score_topology(gold.get("topology", []))
    answer_metrics, answer_counts, answer_failures = _score_answers(answer_items, answer_fn)

    metrics = {
        **retrieval_metrics,
        **routing_metrics,
        **topology_metrics,
    }
    if answer_items:
        metrics.update(answer_metrics)
    counts = {
        "retrieval_items": len(gold.get("retrieval", [])),
        "routing_items": len(gold.get("routing", [])),
        "topology_items": len(gold.get("topology", [])),
        "answer_items": len(answer_items),
        **routing_counts,
        **answer_counts,
    }
    failures = retrieval_failures + routing_failures + topology_failures + answer_failures
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
    parser.add_argument(
        "--gate", action="store_true", help="Exit non-zero when configured thresholds fail."
    )
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
