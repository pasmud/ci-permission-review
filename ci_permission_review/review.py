"""Review declared permissions without executing workflow content."""

from dataclasses import dataclass
from typing import Literal

from .permissions import Permissions, resolve_permissions

MIN_BROAD_WRITES = 3
Severity = Literal["medium", "high"]
SEVERITY_RANK = {"medium": 1, "high": 2}
FINDING_SEVERITY: dict[str, Severity] = {"BROAD_WRITE": "medium", "WRITE_ALL": "high"}


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


def _has_workflow_call(workflow: dict) -> bool:
    triggers = workflow.get("on")
    if isinstance(triggers, str):
        return triggers == "workflow_call"
    return isinstance(triggers, (list, dict)) and "workflow_call" in triggers


def _context_notes(
    job_id: str, job: dict, permissions: Permissions, *, accepts_calls: bool
) -> tuple[EvidenceNote, ...]:
    notes = []
    if permissions.mode == "default":
        notes.append(
            EvidenceNote(
                "PLATFORM_DEFAULT",
                "Neither the workflow nor the job declares permissions; the configured "
                "platform default is unknown to this local review.",
            )
        )
    if accepts_calls:
        notes.append(
            EvidenceNote(
                "CALLER_CONTEXT",
                "When invoked via workflow_call, the caller limits token permissions; "
                "the caller's permission ceiling is unknown to this local review.",
            )
        )
    reference = job.get("uses")
    if isinstance(reference, str) and reference.strip():
        notes.append(
            EvidenceNote(
                "REUSABLE_WORKFLOW",
                f"jobs.{job_id}.uses declares a reusable workflow call; only the caller's "
                "declaration was reviewed. The callee's permissions are unknown.",
            )
        )
    return tuple(notes)


def review_workflow(
    workflow: dict, *, include_notes: bool = False, min_severity: Severity | None = None
) -> tuple[JobReview, ...]:
    results = []
    accepts_calls = include_notes and _has_workflow_call(workflow)
    for job_id, permissions in resolve_permissions(workflow).items():
        notes = (
            _context_notes(
                job_id,
                workflow["jobs"][job_id],
                permissions,
                accepts_calls=accepts_calls,
            )
            if include_notes
            else ()
        )
        findings = _findings(permissions)
        if min_severity is not None:
            findings = tuple(
                finding
                for finding in findings
                if SEVERITY_RANK[FINDING_SEVERITY[finding.code]]
                >= SEVERITY_RANK[min_severity]
            )
        results.append(JobReview(job_id, permissions, findings, notes))
    return tuple(results)
