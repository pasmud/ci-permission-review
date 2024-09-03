"""Review declared permissions without executing workflow content."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    job_id: str
    code: str
    message: str


def review_workflow(workflow: dict) -> tuple[Finding, ...]:
    findings = []
    for job_id, job in sorted(workflow["jobs"].items()):
        permissions = job.get("permissions", workflow.get("permissions"))
        if permissions == "write-all":
            findings.append(Finding(job_id, "WRITE_ALL", "Declares write-all."))
    return tuple(findings)
