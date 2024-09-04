import json
import subprocess
import sys
from pathlib import Path

import pytest


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "ci_permission_review", *map(str, args)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_json_preserves_path_order_and_distinguishes_modes(tmp_path):
    first = tmp_path / "fake-z.yml"
    first.write_text(
        "jobs:\n  platform: {}\n  no_access: {permissions: {}}\n",
        encoding="utf-8",
    )
    second = tmp_path / "fake-a.yml"
    second.write_text(
        "permissions: {issues: write, contents: write, checks: write}\n"
        "jobs:\n  caller: {uses: ./.github/workflows/fake-callee.yml}\n",
        encoding="utf-8",
    )
    args = ["--format", "json", "--notes", first, second]
    result = run_cli(*args)
    assert result.returncode == 0
    assert not result.stderr
    assert result.stdout == run_cli(*args).stdout
    assert "fake-callee" not in result.stdout

    report = json.loads(result.stdout)
    assert report["schema_version"] == 1
    assert [workflow["path"] for workflow in report["workflows"]] == [
        str(first),
        str(second),
    ]
    no_access, platform = report["workflows"][0]["jobs"]
    assert no_access == {
        "job_id": "no_access",
        "permissions": {"source": "job", "mode": "explicit", "scopes": {}},
        "findings": [],
        "notes": [],
    }
    assert platform["job_id"] == "platform"
    assert platform["permissions"] == {
        "source": "platform-default",
        "mode": "default",
        "scopes": {},
    }
    assert not platform["findings"]
    assert [note["code"] for note in platform["notes"]] == ["PLATFORM_DEFAULT"]
    (caller,) = report["workflows"][1]["jobs"]
    assert caller["job_id"] == "caller"
    assert caller["permissions"]["scopes"] == dict.fromkeys(
        ["checks", "contents", "issues"], "write"
    )
    (finding,) = caller["findings"]
    assert finding["code"] == "BROAD_WRITE"
    assert finding["scopes"] == ["checks", "contents", "issues"]
    (note,) = caller["notes"]
    assert note["code"] == "REUSABLE_WORKFLOW"


@pytest.mark.parametrize(
    ("permissions", "exit_code"), [("write-all", 1), ("read-all", 0)]
)
def test_policy_exit_counts_findings_not_notes(tmp_path, permissions, exit_code):
    path = tmp_path / "fake.yml"
    path.write_text(
        f"permissions: {permissions}\njobs: {{caller: {{uses: ./fake.yml}}}}",
        encoding="utf-8",
    )
    result = run_cli("--fail-on-findings", "--notes", path)
    assert result.returncode == exit_code
    assert "note REUSABLE_WORKFLOW" in result.stdout
    assert not result.stderr


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (None, "expected a local regular file"),
        (b"\xff", "workflow must be UTF-8"),
        (b" " * (1024 * 1024 + 1), "1 MiB input limit"),
        (b"jobs: {sample: {permissions: null}}", "job 'sample' permissions:"),
        (b"jobs:\n  sample: [fake-value", "invalid or unsupported YAML"),
    ],
    ids=["missing", "encoding", "size", "permissions", "yaml"],
)
def test_input_error_has_priority_and_keeps_stdout_empty(tmp_path, content, message):
    valid = tmp_path / "fake-valid.yml"
    valid.write_text("jobs: {sample: {permissions: write-all}}", encoding="utf-8")
    invalid = tmp_path / "fake-invalid.yml"
    if content is not None:
        invalid.write_bytes(content)
    result = run_cli("--format", "json", "--fail-on-findings", valid, invalid)
    assert result.returncode == 2
    assert not result.stdout
    assert str(invalid) in result.stderr
    assert message in result.stderr
    assert "Traceback" not in result.stderr
    assert "fake-value" not in result.stderr


def test_missing_arguments_are_a_usage_error():
    result = run_cli()
    assert result.returncode == 2
    assert not result.stdout
    assert "usage: ci-permission-review" in result.stderr


def test_documented_fixtures_have_expected_policy_results():
    examples = Path(__file__).resolve().parents[1] / "examples"
    defaults = run_cli("--fail-on-findings", examples / "fake-defaults.yml")
    assert defaults.returncode == 0
    assert "sample_default: permissions (platform-default):" in defaults.stdout
    assert "sample_empty: permissions (job): {}" in defaults.stdout
    assert "note PLATFORM_DEFAULT" not in defaults.stdout

    with_notes = run_cli(
        "--fail-on-findings", "--notes", examples / "fake-defaults.yml"
    )
    assert with_notes.returncode == 0
    assert "sample_default: note PLATFORM_DEFAULT:" in with_notes.stdout
    assert "sample_empty: note" not in with_notes.stdout

    flags = run_cli(
        "--format",
        "json",
        "--notes",
        "--fail-on-findings",
        examples / "fake-review.yml",
    )
    assert flags.returncode == 1
    assert not flags.stderr
    (report,) = json.loads(flags.stdout)["workflows"]
    assert {
        job["job_id"]: [finding["code"] for finding in job["findings"]]
        for job in report["jobs"]
    } == {
        "sample_all": ["WRITE_ALL"],
        "sample_call": [],
        "sample_read": [],
        "sample_report": ["BROAD_WRITE"],
    }
