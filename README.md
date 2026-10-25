# skill-drift

`skill-drift` 0.1.0 checks whether an agent skill package's stated paths and
basic metadata still match the disk. It is deterministic, offline, and uses
only the Python standard library at runtime: no daemon, LLM, network, or keys.
A finding means **check this claim**.

Requires Python 3.9+. Install with `pip install .`, or install a built wheel.

```sh
skill-drift audit [path] [--json] [--fail-on high|medium] [--ignore G]
skill-drift --version
skill-drift --help
python -m skill_drift audit .
```

Path defaults to the current directory. Repeat `--ignore` for multiple glob
patterns; patterns match the claim text, apply to all checks, and excluded
unique findings are counted as ignored.

## Discovery and parsing

A package is any directory containing a file named exactly `SKILL.md`.
Discovery recursively includes the supplied directory itself and hidden
folders such as `.claude/skills` and `.cursor/skills`. It skips `.git`,
`node_modules`, `dist`, `__pycache__`, `.venv`, and `venv`; directory symlinks
are not traversed. No packages gives PASS, exit 0, and `no skills found`.
Unreadable or invalid UTF-8 SKILL.md files produce parse errors.

The file must begin with an exact `---` line and close its frontmatter with
another `---` line. Supported YAML is a subset: `key: value`, quoted or
unquoted scalar values, and block lists under a key. Blank lines and full-line
comments are accepted. Nested maps, anchors, tags, flow collections, multiline
scalars, duplicate keys, and malformed blocks are parse errors. Name and
description must be scalars. Quoted values are treated literally, without
YAML escape processing; inline comments are not interpreted.

## Checks and severities

| Kind | Severity | Trigger |
| --- | --- | --- |
| missing-frontmatter | HIGH | No opening frontmatter delimiter |
| missing-name | HIGH | Missing or empty name |
| missing-description | HIGH | Missing or empty description |
| name-mismatch | MEDIUM | Name differs from package directory name |
| referenced-file | HIGH | Referenced path does not exist |
| script-not-executable | MEDIUM | Referenced scripts/ file has neither any executable bit nor a shebang |
| duplicate-skill-name | MEDIUM | Same nonempty name appears in multiple packages; each package is flagged |
| empty-body | MEDIUM | Stripped body has fewer than 50 characters |

Name and description are HIGH by design because they make a skill loadable
and discoverable. Name matching is a convention, not universal across hosts.

Path checks inspect the body after frontmatter, using backticked or bare
tokens containing `/` and ending in `.py`, `.js`, `.ts`, `.md`, `.json`,
`.yaml`, `.yml`, `.toml`, `.sh`, `.go`, `.rs`, or `.txt`, plus references
under `scripts/`, `references/`, `examples/`, `tests/`, `docs/`, and `bin/`.
URLs beginning http:// or https://, absolute paths, and tokens containing `*`
are skipped. Paths resolve against the skill directory first, then the audit
root. A trailing slash requires a directory. Shebang detection checks the
first two bytes for `#!`; permission checks inspect mode bits.

Findings include skill directory relative to the root, file, 1-based line,
kind, claim, severity, and detail. Metadata diagnostics use the opening lines;
body path diagnostics use their actual line. Findings deduplicate by
(skill, line, kind, claim). At most 500 are displayed, ordered by skill then
line (then kind and claim); truncation and omitted count are explicit.
Totals and verdict include all unignored findings, including omitted ones.
Human and JSON reports contain the same counts, per-kind and per-severity
totals, ignored count, parse-error count, and verdict.

## Exit codes

| Code | Verdict | Meaning |
| --- | --- | --- |
| 0 | PASS | No unignored findings or parse errors |
| 1 | WARN | Findings exist, all below the threshold |
| 2 | FAIL | Any finding reaches the threshold, or any parse error |

Default threshold is HIGH. With `--fail-on medium`, every finding fails.
An invalid audit path also produces exit 2. CLI argument errors use argparse's
exit 2. The warn-only case uses exit 1 even though no finding reaches the
threshold.

## Examples

All included examples are synthetic and need no credentials or services.

```sh
skill-drift audit examples/sample-skills/good-skill
# PASS: 1 skills found; no findings; exit 0
skill-drift audit examples/sample-skills/broken-skill
# FAIL: 1 skills found; exit 2
# HIGH missing-description: description
# MEDIUM name-mismatch: outdated-skill
# HIGH referenced-file: scripts/renamed.sh
# HIGH referenced-file: references/moved.md
skill-drift audit examples/sample-skills/broken-skill --json
# Valid JSON: HIGH=3, MEDIUM=1, verdict=FAIL, exit_code=2
```

The good package references an executable `scripts/check.sh`. The broken
package demonstrates a missing description, mismatched name, missing script,
and missing reference. The actual report also includes locations and details.

## Limitations

Checks are heuristic pattern matching, not semantic judgement. Paraphrased
claims are not checked. Commands are never executed; only their path tokens
are checked. Paths with spaces and unusual punctuation may be missed or
misidentified. Existence says nothing about correctness, safety, importability,
or successful execution. External targets and glob expansions are not checked.
The YAML subset rejects complex YAML instead of guessing. Filesystem changes
during a run can affect results; this is a snapshot-style audit, not a monitor.

## Differentiation

- **instruction-drift** audits instruction files (AGENTS.md, CLAUDE.md,
  MUSE.md, CONTRIBUTING.md) against a repository. This audits skill packages:
  SKILL.md, frontmatter, scripts, and references against the disk.
- **skill-tax** audits what a SKILL.md costs in tokens. This audits whether
  the skill still works through its checkable package claims.
- **skill-pin-verify** audits pinning/signatures. This audits the truth of
  package contents through offline heuristics.
- **frontmatter-guard** audits plugin.json manifests. This audits SKILL.md
  frontmatter.
- **Heavy runtimes** require more infrastructure. This is an offline stdlib
  CLI with no daemon, no LLM, and no network.

## Development

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python -m build
python -m venv /tmp/skill-drift-smoke
/tmp/skill-drift-smoke/bin/pip install dist/skill_drift-0.1.0-py3-none-any.whl
/tmp/skill-drift-smoke/bin/skill-drift audit examples/sample-skills/good-skill
```

Tests use unittest, temporary synthetic fixtures, and no network. Setuptools
and wheel are build-time dependencies; `build` is the development frontend.
Build artifacts are local only and should be removed before sharing a tree.

MIT licensed. See LICENSE.
