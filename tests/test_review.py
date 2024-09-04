import pytest

from ci_permission_review.review import review_workflow
from ci_permission_review.workflow import load_workflow


def test_flags_broad_writes_only_where_they_apply():
    workflow = load_workflow("""
        permissions: {statuses: write, checks: write, actions: write, contents: read}
        jobs:
          reports: {}
          all_permissions: {permissions: write-all}
          write_two: {permissions: {id-token: write, contents: write, packages: none}}
          use_read_all: {permissions: read-all}
          no_permissions: {permissions: {}}
    """)
    results = review_workflow(workflow)
    assert [job.job_id for job in results] == [
        "all_permissions",
        "no_permissions",
        "reports",
        "use_read_all",
        "write_two",
    ]
    assert {
        job.job_id: [(finding.code, finding.scopes) for finding in job.findings]
        for job in results
        if job.findings
    } == {
        "all_permissions": [("WRITE_ALL", ())],
        "reports": [("BROAD_WRITE", ("actions", "checks", "statuses"))],
    }


def test_reusable_notes_do_not_follow_or_echo_references_or_flag_step_actions():
    workflow = load_workflow("""
        jobs:
          sample_call:
            uses: ./.github/workflows/fake-missing.yml
            permissions: {}
          other_call:
            uses: fake-org/fake-repo/.github/workflows/fake-example.yml@fake-ref
          sample_step:
            permissions: {}
            steps:
              - uses: fake-org/fake-action@fake-ref
    """)
    assert all(not job.notes for job in review_workflow(workflow))
    results = review_workflow(workflow, include_notes=True)
    assert all(not job.findings for job in results)
    assert [note.code for note in results[0].notes] == [
        "PLATFORM_DEFAULT",
        "REUSABLE_WORKFLOW",
    ]
    assert "unknown" in results[0].notes[0].message
    assert [note.code for note in results[1].notes] == ["REUSABLE_WORKFLOW"]
    for job in results[:2]:
        note = job.notes[-1]
        assert f"jobs.{job.job_id}.uses" in note.message
        assert "caller" in note.message
        assert "callee's permissions are unknown" in note.message
        assert "fake-" not in note.message
    assert not results[2].notes


@pytest.mark.parametrize(
    "triggers", ["workflow_call", "[workflow_call, push]", "{workflow_call: null}"]
)
def test_callable_workflow_explains_caller_ceiling_for_explicit_permissions(triggers):
    workflow = load_workflow(
        f"on: {triggers}\npermissions: {{contents: read}}\njobs: {{sample: {{}}}}"
    )
    (job,) = review_workflow(workflow, include_notes=True)
    assert job.permissions.scopes == (("contents", "read"),)
    assert not job.findings
    (note,) = job.notes
    assert note.code == "CALLER_CONTEXT"
    assert "When invoked via workflow_call" in note.message
    assert "ceiling is unknown" in note.message
