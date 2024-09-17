"""Command-line entry point for reviewing local workflow files."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .review import JobReview, review_workflow
from .workflow import WorkflowError, read_workflow

Reports = list[tuple[str, tuple[JobReview, ...]]]


def _print_text(reports: Reports) -> None:
    for path, jobs in reports:
        for job in jobs:
            prefix = f"{path!r}: {job.job_id}:"
            print(
                f"{prefix} permissions ({job.permissions.source}): {job.permissions.describe()}"
            )
            for finding in job.findings:
                print(f"{prefix} {finding.code}: {finding.message}")
            for note in job.notes:
                print(f"{prefix} note {note.code}: {note.message}")


def _print_json(reports: Reports) -> None:
    workflows = []
    for path, jobs in reports:
        entries = []
        for job in jobs:
            entry = asdict(job)
            entry["permissions"]["scopes"] = dict(job.permissions.scopes)
            entries.append(entry)
        workflows.append({"path": path, "jobs": entries})
    print(json.dumps({"schema_version": 1, "workflows": workflows}, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ci-permission-review",
        description="Review declared GitHub Actions permissions in local YAML files.",
        allow_abbrev=False,
    )
    parser.add_argument("paths", metavar="WORKFLOW", nargs="+")
    parser.add_argument(
        "--notes", action="store_true", help="include reusable-job evidence"
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="return 1 if any job has a finding",
    )
    args = parser.parse_args(argv)

    reports: Reports = []
    for path in args.paths:
        try:
            jobs = review_workflow(read_workflow(Path(path)), include_notes=args.notes)
            reports.append((path, jobs))
        except WorkflowError as exc:
            print(f"{path!r}: {exc}", file=sys.stderr)
            return 2

    if args.format == "json":
        _print_json(reports)
    else:
        _print_text(reports)
    if args.fail_on_findings and any(
        job.findings for _, jobs in reports for job in jobs
    ):
        return 1
    return 0
