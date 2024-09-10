"""Review declared permissions without executing workflow content."""

from dataclasses import dataclass

from .permissions import Permissions, resolve_permissions


@dataclass(frozen=True)
class Finding:
    job_id: str
    code: str
    message: str


@dataclass(frozen=True)
class JobReview:
    job_id: str
    permissions: Permissions
    findings: tuple[Finding, ...]


def review_workflow(workflow: dict) -> tuple[JobReview, ...]:
    results = []
    for job_id, permissions in resolve_permissions(workflow).items():
        findings = ()
        if permissions.mode == "write-all":
            findings = (Finding(job_id, "WRITE_ALL", "Uses write-all."),)
        results.append(JobReview(job_id, permissions, findings))
    return tuple(results)
