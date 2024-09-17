"""Load the local YAML portion needed for a permission review."""

import re
from pathlib import Path

import yaml
from yaml.composer import ComposerError
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, Node, ScalarNode

MAX_WORKFLOW_BYTES = 1024 * 1024
BOOL_TAG = "tag:yaml.org,2002:bool"
MERGE_TAG = "tag:yaml.org,2002:merge"
JOB_ID = re.compile(r"[a-zA-Z_][a-zA-Z0-9_-]*\Z")
EXPLICIT_TAG_ERROR = "explicit YAML tags are not supported"


class WorkflowError(ValueError):
    """An input cannot be reviewed."""


class WorkflowLoader(yaml.SafeLoader):
    # PyYAML's default YAML 1.1 resolver makes workflow keys like `on` booleans.
    yaml_implicit_resolvers = {
        initial: [entry for entry in resolvers if entry[0] != BOOL_TAG]
        for initial, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def compose_node(self, parent: Node | None, index: Node | int | None) -> Node:
        event = self.peek_event()
        if getattr(event, "tag", None) is not None:
            raise ComposerError(None, None, EXPLICIT_TAG_ERROR, event.start_mark)
        return super().compose_node(parent, index)

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict:
        if not isinstance(node, MappingNode):
            return super().construct_mapping(node, deep=deep)
        seen: set[object] = set()
        for key_node, _ in node.value:
            if key_node.tag == MERGE_TAG:
                raise ConstructorError(
                    None, None, "YAML merge keys are not supported", key_node.start_mark
                )
            if not isinstance(key_node, ScalarNode):
                raise ConstructorError(
                    None, None, "mapping keys must be scalars", key_node.start_mark
                )
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise ConstructorError(
                    None, None, "duplicate mapping key", key_node.start_mark
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


WorkflowLoader.add_implicit_resolver(
    BOOL_TAG, re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)


def load_workflow(source: str) -> dict:
    try:
        workflow = yaml.load(source, Loader=WorkflowLoader)
    except (
        yaml.YAMLError,
        RecursionError,
        ValueError,
        TypeError,
        OverflowError,
    ) as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        safe_problems = {
            EXPLICIT_TAG_ERROR,
            "duplicate mapping key",
            "mapping keys must be scalars",
            "YAML merge keys are not supported",
        }
        problem = getattr(exc, "problem", None)
        detail = f" ({problem})" if problem in safe_problems else ""
        raise WorkflowError(f"invalid or unsupported YAML{location}{detail}") from exc

    if not isinstance(workflow, dict):
        raise WorkflowError("expected a workflow mapping")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        raise WorkflowError("expected a non-empty 'jobs' mapping")
    for job_id, job in jobs.items():
        if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
            raise WorkflowError(
                "invalid job ID; expected letters, digits, '_' or '-', "
                "starting with a letter or '_'"
            )
        if not isinstance(job, dict):
            raise WorkflowError(f"job {job_id!r} must be a mapping")
    return workflow


def read_workflow(path: Path) -> dict:
    try:
        if not path.is_file():
            raise WorkflowError("expected a local regular file")
        with path.open("rb") as stream:
            data = stream.read(MAX_WORKFLOW_BYTES + 1)
    except OSError as exc:
        raise WorkflowError(f"cannot read file ({exc.strerror})") from exc
    if len(data) > MAX_WORKFLOW_BYTES:
        raise WorkflowError("workflow exceeds the 1 MiB input limit")
    try:
        source = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise WorkflowError("workflow must be UTF-8") from exc
    return load_workflow(source)
