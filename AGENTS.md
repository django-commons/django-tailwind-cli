# AGENTS.md

Guidance for coding agents working in this repository. Read
[CONTRIBUTING.md](CONTRIBUTING.md) first — development setup, tests, commit conventions, and the
changelog rule live there and are not repeated here. This file covers what the code looks like and
which mistakes are easy to make in it.

## What this project is

`django-tailwind-cli` integrates Tailwind CSS 4.x into Django through the precompiled standalone
Tailwind CLI. There is no Node.js anywhere in the picture: the package downloads a platform-specific
binary and drives it from Django management commands.

## Package layout

```
src/django_tailwind_cli/
├── apps.py                     # Django app configuration
├── config.py                   # Central configuration (Config class)
├── management/commands/
│   ├── _group.py               # the django-click group, and the four behaviours it restores
│   ├── tailwind.py             # the click group object and the nine command functions
│   ├── _build.py               # running the CLI, watch, and the build/watch bootstrap
│   ├── _download.py            # getting the binary onto disk, and the managed directory
│   ├── _errors.py              # handle_command_errors and the hints it prints
│   ├── _guides.py              # what troubleshoot, optimize and config print
│   ├── _process.py             # spawning and shutting down the watcher processes
│   └── _source_css.py          # writing the managed source.css and protecting hand edits
├── templates/tailwind_cli/     # base.html and the tailwind_css.html partial
├── templatetags/               # {% tailwind_css %}
└── utils/http.py               # urllib download helpers
```

- **`config.py`** — `Config` reads the Django settings and derives every path from them, and
  `get_platform_info()` picks the binary for the current OS and architecture. New settings belong
  here, with a default, not in the commands. A handful of direct `settings.BASE_DIR` reads in
  `tailwind.py` predate that rule, so grep for `settings.` before assuming `Config` is the only
  reader.
- **`management/commands/tailwind.py`** — one django-click group holding all nine subcommands, with the bulky parts in `_`-prefixed siblings. The group class lives in `_group.py`, because django-click leaves out four things Django's own `BaseCommand` does: it never runs the system checks, it swallows `CommandError` instead of letting a `call_command` caller catch it, it does not route `call_command` keyword options to a subcommand, and it drops several of Django's standard options (`--skip-checks`, `--force-color`, `stdout`/`stderr`). All four are restored there, and all four are django-click defects rather than anything specific to this package. The checks run per subcommand rather than in the group callback, so that `tailwind COMMAND --help` still works on a project whose checks fail. The underscore is load-bearing: Django's `find_commands` would otherwise register them as broken management commands. The subcommands are:
  `build`, `watch`, `runserver`, `setup`, `config`, `troubleshoot`, `optimize`, `download_cli`, and
  `remove_cli`. `runserver` is a transparent passthrough — every argument except
  `--force-default-runserver` is forwarded verbatim to Django's `runserver` or `runserver_plus`.
- **`utils/http.py`** — every network call in the package, on `urllib` rather than `requests` so the
  package stays dependency-light.

## Things that are easy to get wrong

- **Tailwind CSS 4.x only.** There is no config-file-based v3 path left; template discovery happens
  exclusively through `@source` directives in the source CSS.
- **`mise run build-docs` fails on any Sphinx warning**, which is how a dead cross-reference or a moved `literalinclude` target gets caught — a plain build reports both as warnings and publishes regardless. `docs/conf.py` suppresses only `misc.highlighting_failure`, the class Pygments raises on Tailwind 4 at-rules.
- **`mise run lint` only sees git-tracked files.** It is `pre-commit run --all-files`, and
  pre-commit's idea of "all files" is what git knows about — a new module that has never been
  `git add`ed is skipped silently, basedpyright included, and the run still reports green. `git add`
  a new file before believing a lint result about it.
- **The README is a docs page.** `docs/index.md` includes it verbatim, so a README edit is a
  documentation edit and has to hold up in both places.
- **Supported versions are asserted in three places** — `pyproject.toml` classifiers, `tox.ini`, and
  the CI matrix in `.github/workflows/test.yml`. A version bump that touches only one of them
  passes CI and is still wrong.
- **`mise.toml` pins the toolchain.** Prereleases need an entry under `[tool_alias.python.versions]`
  because bare version strings do not resolve for unreleased Pythons.

## Working agreement

- **Do not commit unless you were asked to.** Leave the work in the tree and offer.
- **English for everything that lands in the repository** — code, comments, documentation, commit
  messages — regardless of the language the conversation is held in.
- **No AI attribution anywhere.** No `Co-Authored-By` trailers, no references to the tool that
  helped write a change, in commits, code, or docs. The person opening the pull request is the
  author.
- **`mise run test` and `mise run lint` pass** before anything is offered as finished.

## Tests

Test first, always. Write the failing test, then the code that makes it pass. A test written
afterwards pins whatever the implementation happens to do, bugs included, and it passes for reasons
nobody checked.

- **Prove the test can fail.** Break the thing it guards, watch it go red, put it back. A test that
  still passes against a sabotaged implementation is not evidence of anything, and running it once
  is the only way to find that out.
- **A bug fix carries a regression test** that fails on the unfixed code. If you cannot write one,
  you have not understood the bug yet.
- `pytest` with plain `assert` statements, never `unittest.TestCase`. Plain classes are used for
  grouping only. `tests/settings.py` is the settings module for the suite (`DJANGO_SETTINGS_MODULE`
  in `pyproject.toml`).
- **The suite fails any test that resolves a hostname.** `tests/conftest.py` records calls to
  `socket.getaddrinfo` and fails the test afterwards — afterwards, because the version lookup
  swallows connection errors, so a blocked socket alone would stay invisible. It also gives every
  test its own version cache and answers the "latest release" lookup from a fixture. A test that
  fetches a real binary is a broken test.
- **Opt out of the patched HTTP layer with `@pytest.mark.unpatched_http`**, as `tests/test_http.py`
  does. That is only for tests of `utils/http.py` itself.
- Plain test helpers live in `tests/helpers.py`. `write_fake_cli` stands in for `download_with_progress`, so its signature mirrors the production call — it is installed as a `side_effect`. `install_fake_cli` takes a path and puts an executable binary there, as if it had already been installed. The behavioural difference is the chmod, and it is deliberate: `write_fake_cli` leaves the mode alone because production sets it right after the download returns, and a stub that set it too would hide whether it does — `tests/test_integration.py::test_cli_permissions_after_download` is the test that would stop being evidence. Use them; do not write a local copy of either.
- Shared fixtures belong in `tests/conftest.py`. Four are autouse: the network guard, the
  version-cache path, the version-cache reset, and the version-lookup patch. Four are opt-in:
  `bypass_autoreload` (run `tailwind watch` in-process instead of under Django's autoreloader),
  `fake_project_settings` (a `BASE_DIR` that does not exist on disk, so expected paths stay
  readable literals), `tmp_project` (a real project under `tmp_path` with the CLI settings
  pointing inside it, and deliberately **no** binary — whether the CLI exists is what several
  tests are about), and `tmp_project_with_cli` (`tmp_project` plus the binary already on disk).
  Take one as a fixture argument, or `@pytest.mark.usefixtures(...)` it — but do not copy the
  setup into a module. A fixture requested only for its side effect gets
  `# noqa: ARG002  (requested for its side effect)`.
