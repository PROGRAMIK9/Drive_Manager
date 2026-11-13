"""Conservative course eligibility checks independent of any language model."""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class EligibilityResult:
    status: str
    reason: str


def assess_mca_eligibility(
    courses: Iterable[str] | None,
    *,
    excluded_courses: Iterable[str] | None = None,
    branches: Iterable[str] | None = None,
    excluded_branches: Iterable[str] | None = None,
    eligible_batches: Iterable[int] | None = None,
    target_batch: int | None = None,
) -> EligibilityResult:
    """Provide a review hint; never use this result to remove an opportunity."""
    normalize = lambda values: {value.strip().casefold() for value in (values or []) if value.strip()}
    included = normalize(courses)
    excluded = normalize(excluded_courses)
    branch_set = normalize(branches)
    excluded_branch_set = normalize(excluded_branches)
    batches = set(eligible_batches or [])

    mca_terms = {"mca", "master of computer applications", "master's in computer applications"}
    explicit_mca = bool(included & mca_terms)
    if excluded & mca_terms:
        return EligibilityResult("NOT_ELIGIBLE", "MCA is explicitly excluded")
    if included and not explicit_mca:
        general_pg = any("postgraduate" in value or value in {"pg", "masters", "master's"} for value in included)
        if not general_pg:
            return EligibilityResult("NOT_ELIGIBLE", "MCA is not included in the eligible courses")
        return EligibilityResult("UNCLEAR", "General postgraduate eligibility does not explicitly include MCA")
    if not included:
        return EligibilityResult("UNCLEAR", "Eligible courses are not specified")
    if branch_set and not any("computer" in branch or "mca" in branch for branch in branch_set):
        return EligibilityResult("UNCLEAR", "Branch restrictions do not clearly include MCA")
    if excluded_branch_set and any("computer applications" in branch or branch == "mca" for branch in excluded_branch_set):
        return EligibilityResult("NOT_ELIGIBLE", "MCA is excluded by the branch restrictions")
    if batches and target_batch is not None and target_batch not in batches:
        return EligibilityResult("NOT_ELIGIBLE", f"Graduation batch {target_batch} is not eligible")
    return EligibilityResult("ELIGIBLE", "MCA is explicitly included and no known restriction excludes it")
