"""
Evaluation service.

Reads /data/input/calendar_entries_{de,en}.csv, translates each entry, and
writes /data/output/eval_{lang}_{timestamp}.{csv,json}.

Target format
-------------
Ground-truth columns (expected_summary, expected_location, expected_attendees)
hold a list of OR-groups. The prediction is correct if it contains at least
one pictogram ID from EACH group.

  ""                            → no ground truth (skipped in accuracy)
  "[12133,4321,2321]"           → 1 group, any of the three IDs counts
  "[12133,4321],[4239,5439]"    → 2 groups (a sequence): predictions must
                                   contain at least one ID from each bracket.

Order between groups is not required — only the presence of one match per
group. A prediction with extra IDs not listed in any group is still correct.

Input CSV schema:
    id, summary, location, attendees,
    expected_summary, expected_location, expected_attendees
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

from app.models.schemas import (EvaluationEntry, EvaluationMetrics,
                                EvaluationRun, Language, TranslationRequest)
from app.services import translation_service

logger = logging.getLogger(__name__)

DATA_ROOT = Path(os.getenv("DATA_DIR", "/data"))
INPUT_DIR = DATA_ROOT / "input"
OUTPUT_DIR = DATA_ROOT / "output"

_BRACKET_RE = re.compile(r"\[([^\]]*)\]")


def input_path(language: Language) -> Path:
    return INPUT_DIR / f"calendar_entries_{language.value}.csv"


def list_runs() -> list[dict]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    runs = []
    for json_file in sorted(OUTPUT_DIR.glob("eval_*.json"), reverse=True):
        try:
            with json_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            runs.append({
                "run_id": data.get("run_id"),
                "language": data.get("language"),
                "timestamp": data.get("timestamp"),
                "filename": json_file.name,
                "total_entries": data.get("metrics", {}).get("total_entries", 0),
            })
        except Exception as e:
            logger.warning("Could not parse %s: %s", json_file.name, e)
    return runs


def get_run(filename: str) -> dict | None:
    safe = Path(filename).name
    path = OUTPUT_DIR / safe
    if not path.exists() or path.suffix != ".json":
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_evaluation(language: Language) -> EvaluationRun:
    csv_path = input_path(language)
    if not csv_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {csv_path}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    entries: list[EvaluationEntry] = []
    started_at = time.time()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_id = f"{language.value}_{timestamp}"

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(_process_row(row, language))

    elapsed = time.time() - started_at
    metrics = _compute_metrics(entries)

    run = EvaluationRun(
        run_id=run_id,
        language=language,
        timestamp=datetime.utcnow().isoformat() + "Z",
        metrics=metrics,
        entries=entries,
    )

    json_path = OUTPUT_DIR / f"eval_{run_id}.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(run.model_dump(by_alias=True), f, ensure_ascii=False, indent=2)

    csv_out_path = OUTPUT_DIR / f"eval_{run_id}.csv"
    _write_csv(run, csv_out_path)

    logger.info("Evaluation '%s' complete: %d entries in %.1fs → %s",
                run_id, len(entries), elapsed, json_path.name)

    return run


def _process_row(row: dict, language: Language) -> EvaluationEntry:
    entry_id = row.get("id", "").strip() or f"row_{int(time.time() * 1000)}"
    summary = row.get("summary", "").strip()
    location = row.get("location", "").strip()
    attendees = row.get("attendees", "").strip()

    expected_summary = _parse_target_groups(row.get("expected_summary", ""))
    expected_location = _parse_target_groups(row.get("expected_location", ""))
    expected_attendees = _parse_target_groups(row.get("expected_attendees", ""))

    request = TranslationRequest(
        summary=summary, location=location,
        attendees=attendees, language=language,
    )
    response = translation_service.translate(request)

    pred_summary = [m.pictogram_id for m in response.summary.matches]
    pred_location = [m.pictogram_id for m in response.location.matches]
    pred_attendees = [m.pictogram_id for att in response.attendees for m in att.matches]

    return EvaluationEntry(
        id=entry_id,
        language=language,
        summary=summary,
        location=location,
        attendees=attendees,
        expected_summary=expected_summary,
        expected_location=expected_location,
        expected_attendees=expected_attendees,
        response=response,
        summary_correct=_check(pred_summary, expected_summary),
        location_correct=_check(pred_location, expected_location),
        attendees_correct=_check(pred_attendees, expected_attendees),
    )


def _parse_target_groups(raw: str) -> list[list[int]]:
    """
    Parse target specification into a list of OR-groups.

    Examples:
        ""                              → []
        "[12133,4321]"                  → [[12133, 4321]]
        "[12133,4321],[4239,5439]"      → [[12133, 4321], [4239, 5439]]
        "12133;4321"  (legacy)          → [[12133, 4321]]   (one group)
    """
    if not raw or not raw.strip():
        return []

    groups: list[list[int]] = []
    bracket_contents = _BRACKET_RE.findall(raw)

    if bracket_contents:
        for content in bracket_contents:
            ids = _parse_int_list(content)
            if ids:
                groups.append(ids)
    else:
        # Legacy fallback: treat the whole field as a single OR-group
        ids = _parse_int_list(raw)
        if ids:
            groups.append(ids)

    return groups


def _parse_int_list(raw: str) -> list[int]:
    """Split on commas and semicolons, return all valid integers."""
    out: list[int] = []
    for tok in re.split(r"[,;]", raw):
        tok = tok.strip()
        if tok and tok.lstrip("-").isdigit():
            out.append(int(tok))
    return out


def _check(predicted: list[int], target_groups: list[list[int]]) -> bool | None:
    """
    Return True if every target group has at least one ID present in `predicted`.
    Return None if there are no target groups (entry not evaluated).
    """
    if not target_groups:
        return None
    pred_set = set(predicted)
    for group in target_groups:
        if not (set(group) & pred_set):
            return False
    return True


def _accuracy(values: list[bool | None]) -> float:
    evaluated = [v for v in values if v is not None]
    if not evaluated:
        return 0.0
    return sum(1 for v in evaluated if v) / len(evaluated)


def _prf_for_field(predicted: list[int],
                   target_groups: list[list[int]]) -> tuple[float, float, float] | None:
    """
    Slot-based precision, recall, F1 for one prediction vs one target spec.

    - Recall    = covered slots / total slots
    - Precision = predictions hitting any slot / total predictions
    - F1        = 2PR / (P+R)

    Returns None if the field has no targets (skipped in aggregation).
    Returns (0,0,0) if there are targets but no predictions.
    """
    if not target_groups:
        return None

    pred_set = set(predicted)

    # Recall: how many target slots are covered by ≥1 prediction
    covered = sum(1 for g in target_groups if (set(g) & pred_set))
    recall = covered / len(target_groups)

    # Precision: how many predictions hit any target slot
    if not predicted:
        precision = 0.0
    else:
        all_target_ids: set[int] = set()
        for g in target_groups:
            all_target_ids.update(g)
        hits = sum(1 for pid in predicted if pid in all_target_ids)
        precision = hits / len(predicted)

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return precision, recall, f1


def _pp_prf_for_field(predicted: list[int],
                      target_groups: list[list[int]]) -> tuple[float, float, float] | None:
    """
    Per-prediction (set-based) precision, recall, F1.

    Targets are flattened to a single set: T = union of all slot IDs.
    Predictions are flattened to a single set: P.

    - Precision = |P ∩ T| / |P|
    - Recall    = |P ∩ T| / |T|        (every target ID must be predicted —
                                         alternatives within a slot do NOT
                                         grant credit to each other)
    - F1        = 2PR / (P+R)

    Returns None if there are no targets.
    Returns (0,0,0) if there are targets but no predictions.
    """
    if not target_groups:
        return None

    target_set: set[int] = set()
    for g in target_groups:
        target_set.update(g)

    if not target_set:
        return None

    pred_set = set(predicted)
    intersection = pred_set & target_set

    precision = len(intersection) / len(pred_set) if pred_set else 0.0
    recall = len(intersection) / len(target_set)
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)

    return precision, recall, f1


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _compute_metrics(entries: list[EvaluationEntry]) -> EvaluationMetrics:
    total = len(entries)
    if total == 0:
        return _empty_metrics()

    summary_covered = sum(1 for e in entries if e.response.summary.matches)
    location_covered = sum(1 for e in entries if e.response.location.matches)
    attendees_covered = sum(
        1 for e in entries if any(att.matches for att in e.response.attendees)
    )

    acc_summary = _accuracy([e.summary_correct for e in entries])
    acc_location = _accuracy([e.location_correct for e in entries])
    acc_attendees = _accuracy([e.attendees_correct for e in entries])

    fully_evaluated = [
        e for e in entries
        if e.summary_correct is not None
           and e.location_correct is not None
           and e.attendees_correct is not None
    ]
    if fully_evaluated:
        acc_overall = sum(
            1 for e in fully_evaluated
            if e.summary_correct and e.location_correct and e.attendees_correct
        ) / len(fully_evaluated)
    else:
        acc_overall = 0.0

    # --- Per-field P/R/F1 (slot-based and per-prediction) ---
    slot_lists: dict[str, tuple[list, list, list]] = {
        "summary": ([], [], []),
        "location": ([], [], []),
        "attendees": ([], [], []),
    }
    pp_lists: dict[str, tuple[list, list, list]] = {
        "summary": ([], [], []),
        "location": ([], [], []),
        "attendees": ([], [], []),
    }

    for e in entries:
        pred_summary = [m.pictogram_id for m in e.response.summary.matches]
        pred_location = [m.pictogram_id for m in e.response.location.matches]
        pred_attendees = [m.pictogram_id for att in e.response.attendees for m in att.matches]

        for field, predicted, targets in [
            ("summary", pred_summary, e.expected_summary),
            ("location", pred_location, e.expected_location),
            ("attendees", pred_attendees, e.expected_attendees),
        ]:
            slot_res = _prf_for_field(predicted, targets)
            if slot_res is not None:
                p, r, f = slot_res
                slot_lists[field][0].append(p)
                slot_lists[field][1].append(r)
                slot_lists[field][2].append(f)

            pp_res = _pp_prf_for_field(predicted, targets)
            if pp_res is not None:
                p, r, f = pp_res
                pp_lists[field][0].append(p)
                pp_lists[field][1].append(r)
                pp_lists[field][2].append(f)

    def field_means(buckets: dict[str, tuple[list, list, list]]) -> dict[str, tuple[float, float, float]]:
        return {
            field: (_mean(buckets[field][0]),
                    _mean(buckets[field][1]),
                    _mean(buckets[field][2]))
            for field in ("summary", "location", "attendees")
        }

    slot_means = field_means(slot_lists)
    pp_means = field_means(pp_lists)

    def macro(buckets: dict[str, tuple[list, list, list]],
              means: dict[str, tuple[float, float, float]]) -> tuple[float, float, float]:
        # Average only over fields that had at least one evaluable entry.
        present = [f for f in means if buckets[f][0]]
        if not present:
            return 0.0, 0.0, 0.0
        return (
            _mean([means[f][0] for f in present]),
            _mean([means[f][1] for f in present]),
            _mean([means[f][2] for f in present]),
        )

    slot_macro_p, slot_macro_r, slot_macro_f = macro(slot_lists, slot_means)
    pp_macro_p, pp_macro_r, pp_macro_f = macro(pp_lists, pp_means)

    # --- Match-type distribution and confidences ---
    match_type_counts: dict[str, int] = {}
    total_confidence = 0.0
    total_match_count = 0
    total_unmatched = 0
    for e in entries:
        all_matches = list(e.response.summary.matches) + list(e.response.location.matches)
        for att in e.response.attendees:
            all_matches.extend(att.matches)
        for m in all_matches:
            match_type_counts[m.match_type.value] = (
                    match_type_counts.get(m.match_type.value, 0) + 1
            )
            total_confidence += m.confidence
            total_match_count += 1
        total_unmatched += (
                len(e.response.summary.unmatched_tokens)
                + len(e.response.location.unmatched_tokens)
                + sum(len(att.unmatched_tokens) for att in e.response.attendees)
        )

    avg_confidence = total_confidence / total_match_count if total_match_count else 0.0
    avg_unmatched = total_unmatched / total

    return EvaluationMetrics(
        total_entries=total,
        coverage_summary=summary_covered / total,
        coverage_location=location_covered / total,
        coverage_attendees=attendees_covered / total,
        accuracy_summary=acc_summary,
        accuracy_location=acc_location,
        accuracy_attendees=acc_attendees,
        accuracy_overall=acc_overall,
        # Slot-based
        precision_summary=round(slot_means["summary"][0], 4),
        recall_summary=round(slot_means["summary"][1], 4),
        f1_summary=round(slot_means["summary"][2], 4),
        precision_location=round(slot_means["location"][0], 4),
        recall_location=round(slot_means["location"][1], 4),
        f1_location=round(slot_means["location"][2], 4),
        precision_attendees=round(slot_means["attendees"][0], 4),
        recall_attendees=round(slot_means["attendees"][1], 4),
        f1_attendees=round(slot_means["attendees"][2], 4),
        precision_macro=round(slot_macro_p, 4),
        recall_macro=round(slot_macro_r, 4),
        f1_macro=round(slot_macro_f, 4),
        # Per-prediction
        pp_precision_summary=round(pp_means["summary"][0], 4),
        pp_recall_summary=round(pp_means["summary"][1], 4),
        pp_f1_summary=round(pp_means["summary"][2], 4),
        pp_precision_location=round(pp_means["location"][0], 4),
        pp_recall_location=round(pp_means["location"][1], 4),
        pp_f1_location=round(pp_means["location"][2], 4),
        pp_precision_attendees=round(pp_means["attendees"][0], 4),
        pp_recall_attendees=round(pp_means["attendees"][1], 4),
        pp_f1_attendees=round(pp_means["attendees"][2], 4),
        pp_precision_macro=round(pp_macro_p, 4),
        pp_recall_macro=round(pp_macro_r, 4),
        pp_f1_macro=round(pp_macro_f, 4),
        avg_confidence=round(avg_confidence, 3),
        match_type_distribution=match_type_counts,
        avg_unmatched_tokens_per_entry=round(avg_unmatched, 2),
    )


def _empty_metrics() -> EvaluationMetrics:
    zero = 0.0
    return EvaluationMetrics(
        total_entries=0,
        coverage_summary=zero, coverage_location=zero, coverage_attendees=zero,
        accuracy_summary=zero, accuracy_location=zero, accuracy_attendees=zero,
        accuracy_overall=zero,
        precision_summary=zero, recall_summary=zero, f1_summary=zero,
        precision_location=zero, recall_location=zero, f1_location=zero,
        precision_attendees=zero, recall_attendees=zero, f1_attendees=zero,
        precision_macro=zero, recall_macro=zero, f1_macro=zero,
        pp_precision_summary=zero, pp_recall_summary=zero, pp_f1_summary=zero,
        pp_precision_location=zero, pp_recall_location=zero, pp_f1_location=zero,
        pp_precision_attendees=zero, pp_recall_attendees=zero, pp_f1_attendees=zero,
        pp_precision_macro=zero, pp_recall_macro=zero, pp_f1_macro=zero,
        avg_confidence=zero, match_type_distribution={},
        avg_unmatched_tokens_per_entry=zero,
    )


def _format_groups(groups: list[list[int]]) -> str:
    """Render groups back to the [a,b],[c,d] CSV format."""
    if not groups:
        return ""
    return ",".join("[" + ",".join(str(i) for i in g) + "]" for g in groups)


def _write_csv(run: EvaluationRun, path: Path) -> None:
    fieldnames = [
        "id", "language", "summary", "location", "attendees",
        "expected_summary", "expected_location", "expected_attendees",
        "summary_matches", "location_matches", "attendee_matches",
        "summary_correct", "location_correct", "attendees_correct",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for e in run.entries:
            writer.writerow({
                "id": e.id,
                "language": e.language.value,
                "summary": e.summary,
                "location": e.location,
                "attendees": e.attendees,
                "expected_summary": _format_groups(e.expected_summary),
                "expected_location": _format_groups(e.expected_location),
                "expected_attendees": _format_groups(e.expected_attendees),
                "summary_matches": json.dumps(
                    [_match_dict(m) for m in e.response.summary.matches],
                    ensure_ascii=False,
                ),
                "location_matches": json.dumps(
                    [_match_dict(m) for m in e.response.location.matches],
                    ensure_ascii=False,
                ),
                "attendee_matches": json.dumps(
                    [
                        {
                            "attendee": att.original_attendee,
                            "matches": [_match_dict(m) for m in att.matches],
                        }
                        for att in e.response.attendees
                    ],
                    ensure_ascii=False,
                ),
                "summary_correct": e.summary_correct,
                "location_correct": e.location_correct,
                "attendees_correct": e.attendees_correct,
            })


def _match_dict(m) -> dict:
    return {
        "id": m.pictogram_id,
        "term": m.matched_term,
        "type": m.match_type.value,
        "conf": m.confidence,
        "input": m.original_input,
    }
