"""
Evaluation service.

Reads /data/input/calendar_entries_{de,en}.csv, translates each entry,
and writes /data/output/eval_{lang}_{timestamp}.{csv,json} plus a metrics
summary. The frontend reads the output files via the /api/evaluation endpoints.

Input CSV schema:
    id,summary,location,attendees,expected_summary,expected_location,expected_attendees

The expected_* columns contain semicolon-separated lists of expected ARASAAC IDs.
Example row:
    1,Essen Frühstück,Schule,"Mami, Papa",6456;7890,5586,9876;9876
"""
from __future__ import annotations

import csv
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from app.models.schemas import (EvaluationEntry, EvaluationMetrics,
                                 EvaluationRun, Language, TranslationRequest,
                                 TranslationResponse)
from app.services import translation_service

logger = logging.getLogger(__name__)

DATA_ROOT = Path(os.getenv("DATA_DIR", "/data"))
INPUT_DIR = DATA_ROOT / "input"
OUTPUT_DIR = DATA_ROOT / "output"


def input_path(language: Language) -> Path:
    return INPUT_DIR / f"calendar_entries_{language.value}.csv"


def list_runs() -> list[dict]:
    """Return metadata for all stored evaluation runs."""
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
    """Load a stored run by filename."""
    safe = Path(filename).name  # avoid path traversal
    path = OUTPUT_DIR / safe
    if not path.exists() or not path.suffix == ".json":
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_evaluation(language: Language) -> EvaluationRun:
    """Run translation on every entry in the input CSV, write outputs, return result."""
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
            entry = _process_row(row, language)
            entries.append(entry)

    elapsed = time.time() - started_at
    metrics = _compute_metrics(entries)

    run = EvaluationRun(
        run_id=run_id,
        language=language,
        timestamp=datetime.utcnow().isoformat() + "Z",
        metrics=metrics,
        entries=entries,
    )

    # Write JSON output (consumed by frontend)
    json_path = OUTPUT_DIR / f"eval_{run_id}.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(run.model_dump(by_alias=True), f, ensure_ascii=False, indent=2)

    # Write CSV output (human-inspectable)
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

    expected_summary = _parse_id_list(row.get("expected_summary", ""))
    expected_location = _parse_id_list(row.get("expected_location", ""))
    expected_attendees = _parse_id_list(row.get("expected_attendees", ""))

    request = TranslationRequest(
        summary=summary,
        location=location,
        attendees=attendees,
        language=language,
    )
    response = translation_service.translate(request)

    summary_correct = _set_overlap(
        [m.pictogram_id for m in response.summary.matches], expected_summary
    ) if expected_summary else None
    location_correct = _set_overlap(
        [m.pictogram_id for m in response.location.matches], expected_location
    ) if expected_location else None
    attendee_picto_ids = [
        m.pictogram_id for att in response.attendees for m in att.matches
    ]
    attendees_correct = _set_overlap(
        attendee_picto_ids, expected_attendees
    ) if expected_attendees else None

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
        summary_correct=summary_correct,
        location_correct=location_correct,
        attendees_correct=attendees_correct,
    )


def _parse_id_list(raw: str) -> list[int]:
    if not raw or not raw.strip():
        return []
    out: list[int] = []
    for tok in raw.replace(",", ";").split(";"):
        tok = tok.strip()
        if tok and tok.lstrip("-").isdigit():
            out.append(int(tok))
    return out


def _set_overlap(predicted: list[int], expected: list[int]) -> bool:
    """Check if the predicted IDs cover all expected IDs (set equality on expected)."""
    if not expected:
        return True
    return set(expected).issubset(set(predicted))


def _compute_metrics(entries: list[EvaluationEntry]) -> EvaluationMetrics:
    total = len(entries)
    if total == 0:
        return EvaluationMetrics(
            total_entries=0,
            coverage_summary=0.0,
            coverage_location=0.0,
            coverage_attendees=0.0,
            accuracy_summary=0.0,
            accuracy_location=0.0,
            accuracy_attendees=0.0,
            accuracy_overall=0.0,
            avg_confidence=0.0,
            match_type_distribution={},
            avg_unmatched_tokens_per_entry=0.0,
        )

    summary_covered = sum(1 for e in entries if e.response.summary.matches)
    location_covered = sum(1 for e in entries if e.response.location.matches)
    attendees_covered = sum(
        1 for e in entries if any(att.matches for att in e.response.attendees)
    )

    summary_evaluated = [e for e in entries if e.summary_correct is not None]
    location_evaluated = [e for e in entries if e.location_correct is not None]
    attendees_evaluated = [e for e in entries if e.attendees_correct is not None]

    accuracy_summary = (
        sum(1 for e in summary_evaluated if e.summary_correct) / len(summary_evaluated)
        if summary_evaluated else 0.0
    )
    accuracy_location = (
        sum(1 for e in location_evaluated if e.location_correct) / len(location_evaluated)
        if location_evaluated else 0.0
    )
    accuracy_attendees = (
        sum(1 for e in attendees_evaluated if e.attendees_correct) / len(attendees_evaluated)
        if attendees_evaluated else 0.0
    )

    fully_evaluated = [
        e for e in entries
        if e.summary_correct is not None
        and e.location_correct is not None
        and e.attendees_correct is not None
    ]
    accuracy_overall = (
        sum(
            1 for e in fully_evaluated
            if e.summary_correct and e.location_correct and e.attendees_correct
        ) / len(fully_evaluated) if fully_evaluated else 0.0
    )

    # Aggregate match-type counts and confidences
    match_type_counts: dict[str, int] = {}
    total_confidence = 0.0
    total_match_count = 0
    total_unmatched = 0
    for e in entries:
        all_matches = list(e.response.summary.matches) + list(e.response.location.matches)
        for att in e.response.attendees:
            all_matches.extend(att.matches)
        for m in all_matches:
            match_type_counts[m.match_type.value] = match_type_counts.get(m.match_type.value, 0) + 1
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
        accuracy_summary=accuracy_summary,
        accuracy_location=accuracy_location,
        accuracy_attendees=accuracy_attendees,
        accuracy_overall=accuracy_overall,
        avg_confidence=round(avg_confidence, 3),
        match_type_distribution=match_type_counts,
        avg_unmatched_tokens_per_entry=round(avg_unmatched, 2),
    )


def _write_csv(run: EvaluationRun, path: Path) -> None:
    """Write a flat CSV. Match details serialized as JSON in their column."""
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
                "expected_summary": ";".join(map(str, e.expected_summary)),
                "expected_location": ";".join(map(str, e.expected_location)),
                "expected_attendees": ";".join(map(str, e.expected_attendees)),
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
