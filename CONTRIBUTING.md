# Contributing

Contributions are welcome — bug reports, documentation fixes, and pull requests alike. This project
follows the
[Django Commons Code of Conduct](https://github.com/django-commons/membership/blob/main/CODE_OF_CONDUCT.md).

## Before you open an issue or a pull request

This project is maintained in spare time. Response and review times depend on the available
capacity and the scope of the work; a quick response to one submission does not set a timeline
for others.

- **Keep submissions focused.** Use one topic per issue and one change per pull request. Submit
  unrelated changes separately so each can be reviewed on its own.
- **Make reports actionable.** Describe what you did, what you expected, and what happened instead.
  Include reproduction steps and relevant diagnostics so the problem can be investigated.
- **Review and understand your contribution.** You are responsible for what you submit, including
  work produced with assistance. Check it before submitting and be prepared to explain each change.
- **Use a specific subject line.** Name the affected command or feature and describe the problem
  or proposed change.

For questions about scope or direction, open a
[discussion](https://github.com/django-commons/django-tailwind-cli/discussions) or mail
<oliver@andrich.me> before starting substantial work.

## Reporting a bug

Run the diagnostics and paste their output — they cover most of what would otherwise be a round of
questions:

```bash
python manage.py tailwind config        # resolved paths and settings
python manage.py tailwind troubleshoot  # common misconfigurations
python manage.py tailwind build --verbose
```

Add your OS, your Python and Django versions, the steps to reproduce, and the full traceback if
there is one.

## Development setup

The only prerequisite is [mise](https://mise.jdx.dev/); it provisions Python 3.10–3.15, `uv`, and
`pre-commit` from `mise.toml`.

```bash
git clone git@github.com:django-commons/django-tailwind-cli.git
cd django-tailwind-cli

mise install
mise run bootstrap
```

## Tests and checks

```bash
mise run test        # pytest with coverage on the default interpreter
mise run test-all    # the full Python/Django matrix via tox
mise run lint        # pre-commit: ruff, basedpyright, uv-secure, upgrade hooks
```

`mise run test` and `mise run lint` both have to pass before a pull request is ready. `test-all`
takes a while; CI runs the matrix on every pull request, so running it locally is optional unless
you are touching something version-specific.

One of the lint hooks, `uv-secure`, checks the lock file against published security advisories. If
it fails on a dependency your change never touched, a new advisory appeared and the lock needs a
bump — mention it in the pull request instead of working around it.

## An optional dev session

`mise run dev` opens a three-pane tmux session — `claude --continue` on the left, `pytest-watcher`
running the suite on every save top right, a shell bottom right — on a tmux server of its own named
after the project, so stopping it can never disturb another project's session.

```bash
mise run dev            # start, or attach if it is already running
mise run dev stop       # shut it down
mise run dev restart    # from outside the session
mise run dev status
```

Entirely optional — nothing in the project depends on it. The watcher is also available on its own
as `mise run test-watch`; it runs without coverage so the feedback stays fast, and `mise run test`
remains the command that enforces it.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/) in English, with a scope:

```
feat(management): add purge command for cleaning CSS
fix(config): handle prefixed staticfile directories
chore(deps): bump django-click to 2.5.0
```

Use the scope that names the area you touched. `config`, `management`, `build`, `watch`,
`runserver`, `download`, `http`, `docs`, `tests`, `ci`, and `deps` are the common ones; `git log`
shows the rest.

Keep the message short — a title plus one or two sentences on the _why_. The diff already shows
what changed, and test counts or coverage numbers belong in the pull request, not in the history.

Commit under your own name and without bot co-author trailers. Whatever tools you used, the change
is yours.

## Changelog

User-facing changes get an entry in `CHANGELOG.md` under `## Unreleased`, in one of the categories
the file already uses (Breaking Changes, New Features, Bug Fixes, Developer Experience, and so on).
One or two bullets, focused on what the change means for users rather than on how it was
implemented. Internal refactorings that nobody notices from the outside do not need one.

## Releases

**The major version tracks Tailwind CSS, not this package's own compatibility.** `4.x` supports
Tailwind 4.x, and the major only moves when Tailwind's does. A change that would be a major
elsewhere under semver — a dropped dependency, a different exit code — goes into a minor here and
is called out in the changelog instead.

Releasing is a tag. `[tool.hatch.version]` reads the version from git, so `v4.8.0` _is_ the
version. Pushing the tag starts the release rather than finishing it: the workflow builds, uploads
to TestPyPI, and then waits — the `pypi` environment requires a reviewer, so PyPI publishing needs
an admin to approve it in the GitHub UI. Do not push a tag and walk away.

Rename `## Unreleased` to `## 4.8.0 (YYYY-MM-DD)` before tagging. The release workflow extracts
that section for the GitHub release notes and fails if it cannot find one, which blocks the whole
release rather than shipping empty notes.

## Pull requests

Fork the repository and work on a feature branch. Add tests for new behaviour and update the
documentation when the change is user-facing — `docs/` is published to
[Read the Docs](https://django-tailwind-cli.rtfd.io/), and the README is its landing page. New code
carries type hints; `basedpyright` runs in strict mode. CI runs the same pre-commit hooks that
`mise run lint` runs, so checking locally first saves you a red pipeline.

## License

By contributing you agree that your contribution is licensed under the
[MIT license](https://github.com/django-commons/django-tailwind-cli/blob/main/LICENSE) of this
project.
