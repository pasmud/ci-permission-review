"""Command-line entry point for reviewing local workflow files."""

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .review import review_workflow
from .workflow import WorkflowError, read_workflow


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ci-permission-review",
        description="Review declared GitHub Actions permissions in local YAML files.",
    )
    parser.add_argument("paths", metavar="WORKFLOW", nargs="+", type=Path)
    args = parser.parse_args(argv)

    results = []
    for path in args.paths:
        try:
            results.append((path, review_workflow(read_workflow(path))))
        except WorkflowError as exc:
            print(f"{str(path)!r}: {exc}", file=sys.stderr)
            return 2

    for path, findings in results:
        for finding in findings:
            print(f"{str(path)!r}: {finding.job_id}: {finding.code}: {finding.message}")
    return 0
