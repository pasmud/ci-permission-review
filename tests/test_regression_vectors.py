import json
from pathlib import Path

import pytest

from ci_permission_review.cli import main

VECTORS = sorted(Path(__file__).with_name("regression_vectors").glob("*.json"))


@pytest.mark.parametrize("vector_path", VECTORS, ids=lambda path: path.stem)
def test_permission_review_vector(vector_path, tmp_path, capsys):
    vector = json.loads(vector_path.read_text(encoding="utf-8"))
    title = vector["title"]
    assert 0 < len(title) < 72 and title.isprintable()

    workflow = tmp_path / vector_path.with_suffix(".yml").name
    workflow.write_text("\n".join(vector["workflow"]) + "\n", encoding="utf-8")
    options = vector.get("options", ["--notes", "--fail-on-findings"])
    exit_code = main(["--format", "json", *options, str(workflow)])
    stdout, stderr = capsys.readouterr()
    assert not stderr
    assert exit_code == vector["exit_code"], title

    report = json.loads(stdout)
    assert report["schema_version"] == 1
    (review,) = report["workflows"]
    assert review["path"] == str(workflow)
    expected = vector["expected"]
    assert [job["job_id"] for job in review["jobs"]] == sorted(expected)
    note_contains = vector.get("note_contains", {})
    for job in review["jobs"]:
        job_id = job["job_id"]
        notes = {note["code"]: note["message"] for note in job["notes"]}
        actual = {
            "permissions": job["permissions"],
            "findings": [
                {"code": item["code"], "scopes": item["scopes"]}
                for item in job["findings"]
            ],
            "notes": [note["code"] for note in job["notes"]],
        }
        assert actual == expected[job_id], f"{title}: jobs.{job_id}"
        for code, fragments in note_contains.get(job_id, {}).items():
            for fragment in fragments:
                assert fragment in notes[code]
