"""Resolve permission declarations, independent of GitHub runtime policy."""

from dataclasses import dataclass
from typing import Literal

from .workflow import WorkflowError

Mode = Literal["default", "explicit", "read-all", "write-all"]
Source = Literal["platform-default", "workflow", "job"]

# These scopes accept both read and write. The exceptions are listed below.
READ_WRITE_SCOPES = frozenset(
    {
        "actions",
        "artifact-metadata",
        "attestations",
        "checks",
        "contents",
        "deployments",
        "discussions",
        "issues",
        "packages",
        "pages",
        "pull-requests",
        "security-events",
        "statuses",
    }
)
LEVELS = {
    **dict.fromkeys(READ_WRITE_SCOPES, ("read", "write", "none")),
    "id-token": ("write", "none"),
    "models": ("read", "none"),
}


@dataclass(frozen=True)
class Permissions:
    source: Source
    mode: Mode
    scopes: tuple[tuple[str, str], ...] = ()

    def describe(self) -> str:
        if self.mode == "default":
            return "unspecified platform default"
        if self.mode != "explicit":
            return self.mode
        pairs = ", ".join(f"{scope}: {level}" for scope, level in self.scopes)
        return "{" + pairs + "} (unlisted scopes: none)"


def _parse(value: object, source: Source, location: str) -> Permissions:
    if value == "read-all":
        return Permissions(source, "read-all")
    if value == "write-all":
        return Permissions(source, "write-all")
    if not isinstance(value, dict):
        raise WorkflowError(f"{location}: expected read-all, write-all, or a scope map")

    for scope, level in value.items():
        if not isinstance(scope, str) or scope not in LEVELS:
            raise WorkflowError(f"{location}: unknown permission scope {ascii(scope)}")
        allowed = LEVELS[scope]
        if not isinstance(level, str) or level not in allowed:
            raise WorkflowError(
                f"{location}: {scope!r} must be one of {', '.join(allowed)}"
            )
    return Permissions(source, "explicit", tuple(sorted(value.items())))


def resolve_permissions(workflow: dict) -> dict[str, Permissions]:
    inherited = Permissions("platform-default", "default")
    if "permissions" in workflow:
        inherited = _parse(workflow["permissions"], "workflow", "workflow permissions")

    return {
        job_id: (
            _parse(job["permissions"], "job", f"job {job_id!r} permissions")
            if "permissions" in job
            else inherited
        )
        for job_id, job in sorted(workflow["jobs"].items())
    }
