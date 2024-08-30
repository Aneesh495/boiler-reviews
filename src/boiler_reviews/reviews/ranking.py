from __future__ import annotations

from dataclasses import dataclass
from math import log1p


@dataclass(frozen=True, slots=True)
class RankingPreferences:
    workload_tolerance_hours: float = 10.0
    evidence_weight: float = 0.25
    workload_weight: float = 0.25
    degree_progress_weight: float = 0.25
    preference_weight: float = 0.25


@dataclass(frozen=True, slots=True)
class CourseCandidate:
    course_id: str
    code: str
    title: str
    feasible: bool
    rating_mean: float | None
    review_count: int
    workload_mean_hours: float | None
    degree_progress: float
    preference_match: float


@dataclass(frozen=True, slots=True)
class RankedCourse:
    candidate: CourseCandidate
    score: float | None
    factors: dict[str, float]
    explanation: tuple[str, ...]


def rank_courses(candidates: list[CourseCandidate], preferences: RankingPreferences) -> list[RankedCourse]:
    ranked: list[RankedCourse] = []
    for candidate in candidates:
        if not candidate.feasible:
            ranked.append(RankedCourse(candidate, None, {}, ("Academically infeasible under the selected assumptions",)))
            continue
        evidence = min(log1p(candidate.review_count) / log1p(32), 1.0)
        rating = ((candidate.rating_mean or 3.0) - 1.0) / 4.0 if candidate.rating_mean is not None else 0.0
        evidence_factor = evidence * rating
        workload = candidate.workload_mean_hours
        workload_factor = 1.0 if workload is None else max(0.0, min(1.0, 1.0 - abs(workload - preferences.workload_tolerance_hours) / max(preferences.workload_tolerance_hours, 1.0)))
        degree_factor = max(0.0, min(1.0, candidate.degree_progress))
        preference_factor = max(0.0, min(1.0, candidate.preference_match))
        factors = {
            "evidence_quality_and_rating": evidence_factor,
            "workload_fit": workload_factor,
            "degree_progress": degree_factor,
            "preference_match": preference_factor,
        }
        score = (
            preferences.evidence_weight * evidence_factor
            + preferences.workload_weight * workload_factor
            + preferences.degree_progress_weight * degree_factor
            + preferences.preference_weight * preference_factor
        )
        explanation = (
            f"{candidate.review_count} eligible published reviews" if candidate.review_count else "No published review evidence",
            "Prerequisites and availability are satisfied" if candidate.feasible else "Prerequisites are not satisfied",
            f"Workload evidence is {workload:.1f} hours/week" if workload is not None else "Workload evidence is unavailable",
        )
        ranked.append(RankedCourse(candidate, score, factors, explanation))
    return sorted(ranked, key=lambda value: (value.score is not None, value.score or -1.0, value.candidate.code), reverse=True)
