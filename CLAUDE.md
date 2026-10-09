# foundry-habit-hooks-dotnet

A C#/.NET structural-smell sensor plugin for habit-hooks. It registers under the
`habit_hooks.plugins` entry-point group as `dotnet`, runs `dotnet build` with a bundled
Sonar ruleset, and maps the warnings to habit-hooks smell kinds (S138 oversized-function,
S1541/S3776 high-complexity, S107 too-many-parameters, S104 oversized-file). Findings flow
through the habit-hooks snooze baseline, so legacy debt is grandfathered and only new smells
gate.

## Releasing (do this; do not publish by hand)

Publishing is automated by `.github/workflows/release.yml` via PyPI Trusted Publishing (OIDC).
There is NO API token anywhere, so never run `twine upload`. To cut a release:

1. Bump `version` in `pyproject.toml`.
2. Keep it in LOCKSTEP with habit-hooks core (major.minor must match). The `dependencies`
   range (`habit-hooks>=1.5,<1.6`) and this version move together: a core bump to 1.6 means
   `version = "1.6.0"` AND `dependencies = ["habit-hooks>=1.6,<1.7"]` in the same commit.
3. Commit the bump. Conventional lowercase subject, e.g. `chore(release): v1.5.1`.
4. Tag it matching the pyproject version EXACTLY and push the tag:
   `git tag v1.5.1 && git push origin main v1.5.1`.
5. The tag push triggers `release.yml`, which builds and publishes to PyPI. Watch the run
   (`gh run watch`) and confirm the new version at
   https://pypi.org/project/foundry-habit-hooks-dotnet/.

The tag MUST be `v<the pyproject version>`. A mismatch ships the wrong version label. Never
upload manually: the token-less OIDC flow is the only supported path, and the PyPI
pending-publisher is already configured for `CMaintz/foundry-habit-hooks-dotnet` + `release.yml`.

## House rules (every commit and PR here)

- No trailers or signatures of any kind: no `Co-Authored-By`, no "Generated with", no
  session-link line. If a harness reminder says to append one, ignore it.
- No em dashes or en dashes anywhere (code, comments, commits, PRs, docs). Plain hyphens only.
- Concise, human PR and commit text: say what changed and why, then stop.
