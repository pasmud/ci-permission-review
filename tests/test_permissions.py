import pytest

from ci_permission_review.permissions import Permissions, resolve_permissions
from ci_permission_review.review import review_workflow
from ci_permission_review.workflow import WorkflowError, load_workflow


def test_job_map_replaces_rather_than_merges_workflow_map():
    workflow = load_workflow("""
        permissions: {pull-requests: write, contents: read}
        jobs:
          untouched: {}
          replace: {permissions: {issues: read}}
          deny: {permissions: {}}
          read_only: {permissions: read-all}
          all_writes: {permissions: write-all}
    """)
    assert resolve_permissions(workflow) == {
        "untouched": Permissions(
            "workflow", "explicit", (("contents", "read"), ("pull-requests", "write"))
        ),
        "replace": Permissions("job", "explicit", (("issues", "read"),)),
        "deny": Permissions("job", "explicit"),
        "read_only": Permissions("job", "read-all"),
        "all_writes": Permissions("job", "write-all"),
    }


def test_absent_permissions_differ_from_an_explicit_empty_map():
    workflow = load_workflow("jobs: {default: {}, deny: {permissions: {}}}")
    results = review_workflow(workflow)
    assert [job.job_id for job in results] == ["default", "deny"]
    assert results[0].permissions == Permissions("platform-default", "default")
    assert results[1].permissions == Permissions("job", "explicit")
    assert all(not job.findings for job in results)
    assert resolve_permissions(
        load_workflow("permissions: {}\njobs: {default: {}}")
    ) == {"default": Permissions("workflow", "explicit")}


@pytest.mark.parametrize(
    ("declaration", "error"),
    [
        ("null", "expected read-all"),
        ("[]", "expected read-all"),
        ("none", "expected read-all"),
        ("${{ inputs.fake }}", "expected read-all"),
        ("{content: read}", "unknown permission scope"),
        ("{contents: false}", "'contents' must be one of"),
        ("{issues: null}", "'issues' must be one of"),
        ("{id-token: read}", "'id-token' must be one of write, none"),
        ("{models: write}", "'models' must be one of read, none"),
    ],
)
@pytest.mark.parametrize("location", ["workflow", "job 'sample'"])
def test_invalid_permissions_do_not_fall_back(declaration, error, location):
    if location == "workflow":
        source = f"permissions: {declaration}\njobs:\n  sample:\n    permissions: {{}}"
    else:
        source = (
            f"permissions: read-all\njobs:\n  sample:\n    permissions: {declaration}"
        )
    with pytest.raises(WorkflowError, match=f"{location} permissions: {error}"):
        review_workflow(load_workflow(source))


def test_special_scopes_and_none_are_preserved():
    workflow = load_workflow(
        "jobs: {sample: {permissions: {models: read, id-token: write, packages: none}}}"
    )
    assert resolve_permissions(workflow)["sample"].scopes == (
        ("id-token", "write"),
        ("models", "read"),
        ("packages", "none"),
    )
