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
            steps:
              - uses: fake-org/fake-action@fake-ref
    """)
    assert all(not job.notes for job in review_workflow(workflow))
    results = review_workflow(workflow, include_notes=True)
    assert all(not job.findings for job in results)
    for job in results[:2]:
        (note,) = job.notes
        assert note.code == "REUSABLE_WORKFLOW"
        assert f"jobs.{job.job_id}.uses" in note.message
        assert "caller" in note.message
        assert "fake-" not in note.message
    assert not results[2].notes
