# ci-permission-review

An offline CLI for reviewing `GITHUB_TOKEN` permission declarations in local GitHub Actions workflows. It shows where each job gets its permissions and flags `write-all` or a broad set of explicit write scopes.

## Install and run

Requires Python 3.11 or newer. From the project directory, in a virtual environment:

```sh
python -m pip install .
ci-permission-review --notes examples/fake-review.yml
ci-permission-review --format json --fail-on-findings examples/fake-defaults.yml
```

`python -m ci_permission_review` is equivalent to the installed command. The two examples are synthetic files; they are read as data only. The first command that reviews a file reports findings on `sample_all` (`WRITE_ALL`) and `sample_report` (`BROAD_WRITE`). `sample_read` replaces the broad workflow map with `contents: read`, and `sample_call` declares no scopes and gets an informational note. The second report shows that `sample_default` has an unspecified platform default, while `sample_empty` explicitly grants no configurable scopes.

## How permissions are resolved

1. A job-level declaration replaces the workflow-level declaration. Maps are not merged across levels.
2. A job without its own declaration inherits the workflow declaration, if present.
3. If neither level declares permissions, the reviewer reports an **unspecified platform default**. It does not guess the repository or organization setting.

In an explicit map, unlisted configurable scopes are `none`; `{}` therefore grants none. `read-all` and `write-all` are reported as shorthands without expanding them into scope lists. An explicit `null` is invalid, not a missing declaration.

| Code | When it appears |
| --- | --- |
| `WRITE_ALL` | The resolved declaration for the job is `write-all`. |
| `BROAD_WRITE` | An explicit map declares `write` on at least three scopes. This is a review heuristic, not a verdict that the job is unsafe. |

With `--notes`, the report also explains permission context that the local file cannot establish:

| Note | When it appears |
| --- | --- |
| `PLATFORM_DEFAULT` | Neither the workflow nor the job declares permissions. The configured default is unknown. |
| `CALLER_CONTEXT` | The workflow declares `on: workflow_call`, alone or alongside other triggers. When the workflow is called, the caller limits the token permissions; its permission ceiling is unknown. |
| `REUSABLE_WORKFLOW` | A job has a non-empty job-level `uses`. The note points to the caller's YAML field; the callee's permissions are unknown. |

`read-all`, fewer than three explicit writes, and unspecified defaults produce no findings. Review these separately if your policy requires explicit permissions or prohibits individual scopes.

## Command line and reports

```text
ci-permission-review [--format {text,json}] [--notes] [--fail-on-findings] WORKFLOW [WORKFLOW ...]
```

- Pass one or more local UTF-8 YAML files, each at most 1 MiB. The CLI does not discover files, accept URLs or stdin, or follow local or remote `uses` references. It never runs jobs, invokes actions, evaluates expressions, or contacts GitHub.
- The default text report includes a permission summary per job followed by its findings and any requested notes. Workflows are reported in argument order; job IDs and permission scopes are sorted.
- JSON is one object with `schema_version: 1` and a `workflows` array. Each workflow has `path` and `jobs`. Each job has `job_id`, `permissions`, `findings`, and `notes`. Permissions contain `source` (`platform-default`, `workflow`, or `job`), `mode` (`default`, `explicit`, `read-all`, or `write-all`), and `scopes` (named entries from an explicit map; otherwise `{}`). Check `mode` to tell whether an empty `scopes` object means no permissions. Findings contain `code`, `message`, and a sorted `scopes` array (empty for `WRITE_ALL`); notes contain `code` and `message`.

| Exit code | Meaning |
| --- | --- |
| `0` | Review completed. Findings are advisory unless `--fail-on-findings` is set. |
| `1` | Review completed and `--fail-on-findings` was set with at least one finding. The report is still printed. Notes do not count. |
| `2` | Usage or input error. The first invalid input is reported to stderr, with no partial report on stdout. |

The YAML reader preserves the `on` key and rejects duplicate keys, merge keys, and explicit tags. Permissions must use recognized scope names and valid levels; typos or newer scopes outside the built-in list are input errors. The tool validates the YAML and the fields it reviews, not the full workflow schema. It does not account for runtime restrictions such as fork policy or determine whether a step actually needs a permission.

## Development

```sh
python -m pip install '.[dev]'
python -m pytest
ruff check .
ruff format --check .
```

See [LICENSE](LICENSE) for the MIT license.
