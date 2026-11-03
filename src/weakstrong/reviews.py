"""Manual review interchange; unresolved and unknown labels never become automatic successes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .core import RunRecord, StrictModel, classification


class ManualReview(StrictModel):
    scenario_id: str = Field(min_length=1, max_length=100)
    decision: Literal["allow", "block", "insufficient"]
    note: str = Field(default="", max_length=500)


def review_queue(record: RunRecord) -> list[dict[str, Any]]:
    return [
        {"id": r["id"], "difficulty": r["difficulty"], "risk": r["risk"], "reason": r["reason"]}
        for r in record.rows
        if r["strategy"] == "selective" and r["trial"] == 0 and r["review_required"]
    ]


def apply_reviews(record: RunRecord, reviews: list[ManualReview]) -> dict[str, Any]:
    allowed = {r["id"] for r in review_queue(record)}
    if len({r.scenario_id for r in reviews}) != len(reviews):
        raise ValueError("duplicate manual review")
    if any(r.scenario_id not in allowed for r in reviews):
        raise ValueError("review must reference a deferred first-trial case")
    mapping = {r.scenario_id: r for r in reviews}
    rows = []
    for original in record.rows:
        if original["strategy"] != "selective" or original["trial"] != 0:
            continue
        row = dict(original)
        review = mapping.get(row["id"])
        if review and review.decision != "insufficient":
            row["prediction"] = review.decision == "block"
        rows.append(row)
    return {
        "manual_reviews": len(reviews),
        "remaining_unresolved": sum(r["prediction"] is None for r in rows),
        "metrics": classification(rows),
        "interpretation": "Supplied decisions only; no claim of human accuracy or a blinded study.",
    }
