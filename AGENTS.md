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
│   └── tailwind.py             # the whole `tailwind` command group
├── templates/tailwind_cli/     # base.html and the tailwind_css.html partial
├── templatetags/               # {% tailwind_css %}
└── utils/http.py               # urllib download helpers
```

- **`config.py`** — `Config` reads the Django settings and derives every path from them, and
  `get_platform_info()` picks the binary for the current OS and architecture. New settings belong
  here, with a default, not in the commands. A handful of direct `settings.BASE_DIR` reads in
  `tailwind.py` predate that rule, so grep for `settings.` before assuming `Config` is the only
  reader.
- **`management/commands/tailwind.py`** — one django-typer group holding all nine subcommands:
  `build`, `watch`, `runserver`, `setup`, `config`, `troubleshoot`, `optimize`, `download_cli`, and
  `remove_cli`. `runserver` is a transparent passthrough — every argument except
  `--force-default-runserver` is forwarded verbatim to Django's `runserver` or `runserver_plus`.
- **`utils/http.py`** — every network call in the package, on `urllib` rather than `requests` so the
  package stays dependency-light.

## Things that are easy to get wrong

- **Tailwind CSS 4.x only.** There is no config-file-based v3 path left; template discovery happens
  exclusively through `@source` directives in the source CSS.
- **`mise run build-docs` fails on any Sphinx warning**, which is how a dead cross-reference or a moved `literalinclude` target gets caught — a plain build reports both as warnings and publishes regardless. `docs/conf.py` suppresses only `misc.highlighting_failure`, the class Pygments raises on Tailwind 4 at-rules.
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
- Plain test helpers live in `tests/helpers.py` — `write_fake_cli` stands in for `download_with_progress` and is what every test that fakes a download uses. Do not write a local copy.
- Shared fixtures belong in `tests/conftest.py`, which holds the network guard, the version-cache
  isolation, the version-lookup patch, and two opt-in fixtures: `bypass_autoreload` (run `tailwind
  watch` in-process instead of under Django's autoreloader) and `fake_project_settings` (a
  `BASE_DIR` that does not exist on disk, so expected paths stay readable literals). Opt in with
  `@pytest.mark.usefixtures(...)` rather than copying the setup into the module.
