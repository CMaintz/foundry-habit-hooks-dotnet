# foundry-habit-hooks-dotnet

The C#/.NET Habit Hooks plugin: wraps `dotnet build` with
[SonarAnalyzer.CSharp](https://www.nuget.org/packages/SonarAnalyzer.CSharp)
active, and maps its structural warnings to habit-hooks smell kinds.

It is the direct analog of the Java plugin's pmd sensor. Where a plain
`dotnet build -warnaserror` can only fail the build on any warning, this feeds
the warnings through habit-hooks' snooze index, so an existing backlog is
grandfathered and only new structural debt gates.

## Install

```sh
pip install habit-hooks foundry-habit-hooks-dotnet
```

Installing a plugin does not switch it on. Name it in `plugins`:

```toml
# .habit-hooks/config.toml
plugins = ["dotnet", "generic"]
```

## Requirements

- The .NET SDK (`dotnet` on PATH). `winget install Microsoft.DotNet.SDK.9`
- The target project references `SonarAnalyzer.CSharp` as an analyzer package.

The plugin ships a default ruleset that enables the structural rules
(SonarAnalyzer ships them off by default) and passes it with
`-p:CodeAnalysisRuleSet`. A project that wants its own thresholds or rule set
overrides it:

```toml
[sensors.dotnet-build]
args = ["-p:CodeAnalysisRuleSet=path/to/your.ruleset"]
```

## Rule mapping

| Sonar rule | Smell |
| --- | --- |
| S138 (method length) | oversized-function |
| S1541 (cyclomatic complexity) | high-complexity |
| S3776 (cognitive complexity) | high-complexity |
| S107 (too many parameters) | too-many-parameters |
| S104 (file length) | oversized-file |

Thresholds are SonarAnalyzer's own defaults. A Sonar rule not in the table is
not reported.

## Versioning

Released in lockstep with habit-hooks core: the plugin version tracks the
core's major.minor so the sensor protocol it builds against never drifts. The
mise `HABIT_HOOKS_VERSION` variable pins both together.
