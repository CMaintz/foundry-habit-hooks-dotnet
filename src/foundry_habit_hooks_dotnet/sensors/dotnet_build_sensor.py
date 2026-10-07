"""Run ``dotnet build`` and print canonical habit-hooks smell findings.

The direct analog of the java plugin's pmd sensor: it wraps an external build,
reads the structural warnings SonarAnalyzer.CSharp emits, and shapes each one
into the canonical finding, mapping the Sonar rule id to a smell key.

``dotnet build`` operates on the project or solution in the working directory,
not on a file list, so (like the generic jscpd sensor) this does not splice
``${files}`` into the build command. It builds the whole project, then keeps
only the warnings whose file is in the run's scope, so a ``--file`` or
``--branch`` run reports scoped findings rather than the whole project's debt.

Warnings are left as warnings (TreatWarningsAsErrors off) so the build still
completes and this wrapper can read them. That is the whole point: a plain
``dotnet build -warnaserror`` can only fail the build on any warning, with no
way to grandfather the backlog and gate only new debt. Feeding the warnings
through habit-hooks' snooze index is what adds that ratchet.

The sensor is run as a loose script (``${python} ${dir}/dotnet_build_sensor.py``),
so its own directory is ``sys.path[0]``; the default ruleset it ships lives
next to it and is found by name, the same in the installed package and a
vendored copy.

Its argv spells ``${detector:dotnet} ${args} -- ${files}``: ``sys.argv[1]`` is
the dotnet executable, and ``sys.argv[2:]`` carries any ``[sensors.dotnet-build]
args`` on one side of a literal ``--`` and the scoped files on the other.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Sonar rule id -> habit-hooks smell key (habit_hooks.catalogue). A rule not
# named here is dropped: the catalogue is the record of what is worth failing a
# build over, and inventing a smell for every Sonar rule would bury the ones
# that were chosen.
RULE_SMELLS = {
    "S138": "oversized-function",
    "S1541": "high-complexity",
    "S3776": "high-complexity",
    "S107": "too-many-parameters",
    "S104": "oversized-file",
}

# One MSBuild warning line:
#   path\File.cs(12,34): warning S138: message text [path\Project.csproj]
WARNING = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),\d+\): "
    r"warning (?P<rule>S\d+): (?P<message>.*?)(?: \[(?P<project>.+?)\])?$"
)

# dotnet build exits non-zero on a compile error; only 0 is a clean read of its
# warnings. Anything else is a broken run, not a clean one.
BUILD_SUCCESS = 0


def build_env() -> dict[str, str]:
    """The environment the build runs in: English, quiet, no telemetry.

    The warning text is parsed, so a localised build would hand back messages
    this sensor's regex and the mapper never saw.
    """
    env = dict(os.environ)
    env["DOTNET_CLI_UI_LANGUAGE"] = "en"
    env["DOTNET_NOLOGO"] = "1"
    env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    return env


def default_ruleset() -> Path:
    """The ruleset this plugin ships, which enables the structural rules.

    SonarAnalyzer ships most structural rules off by default, so a bare package
    reference emits none of them. This is the answer to "the project configured
    none"; a project naming its own ``-p:CodeAnalysisRuleSet`` in the sensor's
    args passes it after this one, and MSBuild takes the last.
    """
    return Path(__file__).with_name("sonar.ruleset")


def build_command(dotnet: str, extra_args: list[str]) -> list[str]:
    """The ``dotnet build`` invocation, with this plugin's ruleset as the default."""
    return [
        dotnet,
        "build",
        "--no-incremental",
        "-nologo",
        "-p:TreatWarningsAsErrors=false",
        f"-p:CodeAnalysisRuleSet={default_ruleset()}",
        *extra_args,
    ]


def run_build(dotnet: str, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
    """What the build said, run in the working directory."""
    return subprocess.run(
        build_command(dotnet, extra_args),
        capture_output=True,
        encoding="utf-8",
        errors="replace",  # one invalid byte must not take the sensor down
    )


def split_argv(argv: list[str]) -> tuple[list[str], list[str]]:
    """``argv`` split on the last literal ``--``: build args before, files after."""
    if "--" not in argv:
        return argv, []
    index = len(argv) - 1 - argv[::-1].index("--")
    return argv[:index], argv[index + 1 :]


def parse_warnings(output: str) -> list[dict]:
    """Every structural warning the build printed, as ``{file, line, rule, message}``.

    Deduplicated on ``(file, line, rule)``: a multi-target or multi-project
    build compiles each source once per target and repeats every warning.
    """
    seen: set[tuple[str, str, str]] = set()
    warnings = []
    for line in output.splitlines():
        warning = _parsed_warning(line.strip())
        if warning is None:
            continue
        identity = (warning["file"], warning["line"], warning["rule"])
        if identity not in seen:
            seen.add(identity)
            warnings.append(warning)
    return warnings


def _parsed_warning(line: str) -> dict | None:
    match = WARNING.match(line)
    if match is None or match["rule"] not in RULE_SMELLS:
        return None
    return match.groupdict()


def in_scope(warnings: list[dict], files: list[str]) -> list[dict]:
    """The warnings whose file is one the run scoped this sensor to.

    MSBuild reports absolute paths and the scope arrives project-relative, so
    both sides are compared as absolute, case-folded paths. An empty scope keeps
    nothing: the run narrowed this sensor away and the build's own warnings are
    not the scope's answer.
    """
    scoped = {_normalised(path) for path in files}
    return [w for w in warnings if _normalised(w["file"]) in scoped]


def _normalised(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def issue(warning: dict) -> dict:
    """One warning as a canonical issue, keyed by its file like the pmd sensor."""
    return {
        "key": warning["file"],
        "details": {
            "file": warning["file"],
            "line": int(warning["line"]),
            "message": warning["message"],
            "source": "sonar:" + warning["rule"],
        },
    }


def findings(warnings: list[dict]) -> list[dict]:
    """The warnings grouped into one finding per smell."""
    by_smell: dict[str, list[dict]] = {}
    for warning in warnings:
        by_smell.setdefault(RULE_SMELLS[warning["rule"]], []).append(issue(warning))
    return [
        {"smell": smell, "details": {}, "issues": issues}
        for smell, issues in by_smell.items()
    ]


def main() -> int:
    dotnet, argv = sys.argv[1], sys.argv[2:]
    extra_args, files = split_argv(argv)
    result = subprocess.CompletedProcess([], BUILD_SUCCESS, "", "")
    try:
        result = run_build(dotnet, extra_args)
    except OSError as error:
        sys.stderr.write(f"dotnet build could not start: {error}\n")
        return 2
    if result.returncode != BUILD_SUCCESS:
        sys.stderr.write(result.stdout[-4000:] or result.stderr[-4000:])
        return 2
    scoped = in_scope(parse_warnings(result.stdout), files)
    print(json.dumps(findings(scoped)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
