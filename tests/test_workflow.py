import subprocess
import sys

import pytest
import yaml

from ci_permission_review.workflow import WorkflowError, load_workflow


def test_preserves_on_and_limits_boolean_resolution_to_true_and_false():
    source = (
        "on: [push, pull_request]\njobs: {on: {name: yes, continue-on-error: false}}"
    )
    workflow = load_workflow(source)
    assert workflow["on"] == ["push", "pull_request"]
    assert workflow["jobs"]["on"] == {"name": "yes", "continue-on-error": False}
    assert yaml.safe_load("on: value") == {True: "value"}


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("jobs: {build: {}}\njobs: {review: {}}", "duplicate mapping key"),
        ("jobs: {build: !!python/name:builtins.object ''}", "unsupported YAML"),
        ("jobs: {build: {}}\n---\njobs: {other: {}}", "unsupported YAML"),
        ("jobs: {build: [}", "line 1"),
        ("[]", "workflow mapping"),
        ("jobs: {}", "non-empty 'jobs'"),
        ("jobs: {1job: [], 3: {}}", "invalid job ID"),
        ("jobs: {build: []}", "must be a mapping"),
    ],
)
def test_bad_input_is_rejected(source, message):
    with pytest.raises(WorkflowError, match=message):
        load_workflow(source)


def test_cli_reports_inherited_write_all_but_not_an_override(tmp_path):
    workflow = tmp_path / "fake.yml"
    workflow.write_text(
        "on: push\npermissions: write-all\njobs: {sample: {}, narrowed: {permissions: {}}}",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "ci_permission_review", str(workflow)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == [
        f"{str(workflow)!r}: narrowed: permissions (job): {{}} (unlisted scopes: none)",
        f"{str(workflow)!r}: sample: permissions (workflow): write-all",
        f"{str(workflow)!r}: sample: WRITE_ALL: Uses write-all.",
    ]
    assert not result.stderr
