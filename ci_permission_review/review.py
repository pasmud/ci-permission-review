"""Review declared permissions without executing workflow content."""

from dataclasses import dataclass

from .permissions import Permissions, resolve_permissions

MIN_BROAD_WRITES = 3


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceNote:
    code: str
    message: str


@dataclass(frozen=True)
class JobReview:
    job_id: str
    permissions: Permissions
    findings: tuple[Finding, ...]
    notes: tuple[EvidenceNote, ...]


def _findings(permissions: Permissions) -> tuple[Finding, ...]:
    if permissions.mode == "write-all":
        return (Finding("WRITE_ALL", "Uses write-all."),)

    scopes = tuple(scope for scope, level in permissions.scopes if level == "write")
    if len(scopes) >= MIN_BROAD_WRITES:
        return (
            Finding(
                "BROAD_WRITE",
                f"Declares write on {len(scopes)} scopes: {', '.join(scopes)}.",
                scopes,
            ),
        )
    return ()


def _reusable_notes(job_id: str, job: dict) -> tuple[EvidenceNote, ...]:
    reference = job.get("uses")
    if not isinstance(reference, str) or not reference.strip():
        return ()
    return (
        EvidenceNote(
            "REUSABLE_WORKFLOW",
            f"jobs.{job_id}.uses declares a reusable workflow call; this review covers "
            "the caller's permission declaration only. Review the referenced workflow separately.",
        ),
    )


def review_workflow(
    workflow: dict, *, include_notes: bool = False
) -> tuple[JobReview, ...]:
    results = []
    for job_id, permissions in resolve_permissions(workflow).items():
        notes = (
            _reusable_notes(job_id, workflow["jobs"][job_id]) if include_notes else ()
        )
        results.append(JobReview(job_id, permissions, _findings(permissions), notes))
    return tuple(results)
