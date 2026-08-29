"""Creating and protecting the Tailwind source CSS.

The file at `.django_tailwind_cli/source.css` is managed: every build regenerates it, so this
module also decides when the content on disk was written by a person rather than by us, and keeps
a copy before replacing it.

It also works out which installed apps sit outside `BASE_DIR` and site-packages, because Tailwind's
own scan does not reach them and they need an explicit `@source` directive.
"""

from __future__ import annotations

import re
import site
import sysconfig
from pathlib import Path

import typer
from django.apps import apps
from django.conf import settings

from django_tailwind_cli.config import get_config


def _should_recreate_file(file_path: Path, content: str) -> bool:
    """Check if a file needs to be recreated by comparing its content with what we would write.

    Args:
        file_path: Path to the file to check.
        content: New content that would be written.

    Returns:
        True if file should be recreated, False if it's up to date.
    """
    if not file_path.exists():
        return True

    try:
        current_content = file_path.read_text()
        if current_content != content:
            return True
    except (OSError, UnicodeDecodeError):
        # If we can't read the file, recreate it
        return True

    return False


DEFAULT_SOURCE_CSS = '@import "tailwindcss";\n'
DAISY_UI_SOURCE_CSS = '@import "tailwindcss";\n@plugin "daisyui";\n'
AUTO_SOURCE_COMMENT = "/* Auto-generated: installed apps outside BASE_DIR and site-packages. */"


def _get_site_packages_paths() -> list[Path]:
    """Return all known site-packages paths used to filter out regular installs.

    We combine ``site.getsitepackages()``, ``site.getusersitepackages()`` and
    ``sysconfig.get_paths()`` to catch every standard location — editable
    installs of the user's own source packages live outside all of these.
    """

    paths: set[Path] = set()
    for p in site.getsitepackages():
        paths.add(Path(p).resolve())
    try:
        user_site = site.getusersitepackages()
        if user_site:
            paths.add(Path(user_site).resolve())
    except AttributeError:  # pragma: no cover - defensive
        pass
    for key in ("purelib", "platlib"):
        p = sysconfig.get_paths().get(key)
        if p:
            paths.add(Path(p).resolve())
    return sorted(paths)


def discover_external_app_base_dirs() -> list[Path]:
    """Return base dirs of installed Django apps that need explicit @source.

    An app is considered "external" if its path is NOT under ``BASE_DIR``
    (Tailwind's CWD walk would not reach it) AND NOT under any known
    site-packages directory (regular pip installs are not user-editable
    source). This targets the editable-install case from issue #187.
    """

    base_dir = Path(settings.BASE_DIR).resolve()
    site_packages = _get_site_packages_paths()
    external: list[Path] = []

    for app_config in apps.get_app_configs():
        app_path = Path(app_config.path).resolve()
        if app_path.is_relative_to(base_dir):
            continue
        if any(app_path.is_relative_to(sp) for sp in site_packages):
            continue
        external.append(app_path)

    return sorted(external)


def build_source_css_content(*, use_daisy_ui: bool, inject_external_apps: bool) -> str:
    """Build the auto-generated source.css content.

    Starts from the minimal ``@import "tailwindcss";`` (+ ``@plugin "daisyui";``
    when DaisyUI is enabled) and appends one ``@source`` directive per
    discovered external Django app base dir.
    """
    lines = ['@import "tailwindcss";']
    if use_daisy_ui:
        lines.append('@plugin "daisyui";')

    if inject_external_apps:
        external = discover_external_app_base_dirs()
        if external:
            lines.append("")
            lines.append(AUTO_SOURCE_COMMENT)
            for app_path in external:
                lines.append(f'@source "{app_path}";')

    return "\n".join(lines) + "\n"


_GENERATED_LINE_PATTERNS = (
    r"\s*",  # blank lines
    r'@import\s+"tailwindcss";',
    r'@plugin\s+"daisyui";',
    re.escape(AUTO_SOURCE_COMMENT),
)
_GENERATED_LINE = re.compile("^(?:" + "|".join(_GENERATED_LINE_PATTERNS) + ")$")

# Only ever written below AUTO_SOURCE_COMMENT, which is what tells one of ours from a hand-added
# one — and a hand-added @source is the likeliest edit there is, since it is how you widen
# template discovery.
_SOURCE_LINE = re.compile(r'^@source\s+"[^"]*";$')


def _looks_auto_generated(content: str) -> bool:
    """Return True if every line of ``content`` is one this library writes itself.

    Comparing against the *currently* generated content would be wrong: it changes when DaisyUI is
    toggled or when the set of external apps changes, and neither means the user edited the file.
    Checking the vocabulary instead only asks "could we have written this?".

    Position matters for one line type. We only ever write ``@source`` below the auto-generated
    comment, so one above it is the user widening template discovery by hand.
    """
    below_auto_source_comment = False
    for line in content.splitlines():
        if line == AUTO_SOURCE_COMMENT:
            below_auto_source_comment = True
        elif _SOURCE_LINE.match(line):
            if not below_auto_source_comment:
                return False
        elif not _GENERATED_LINE.match(line):
            return False
    return True


def _preserve_hand_edits(src_css: Path) -> None:
    """Copy the hand-edited source CSS aside and say where it went.

    The managed file is regenerated on every build, so the edits are going to be lost either way.
    Keeping a copy makes that recoverable instead of merely announced. The backup lives in the
    managed directory, which carries its own ``.gitignore``.
    """
    backup = src_css.with_suffix(".css.bak")
    backup.write_text(src_css.read_text())

    typer.secho(
        f"⚠️  '{src_css}' has hand edits that are about to be replaced.",
        fg=typer.colors.YELLOW,
        bold=True,
    )
    typer.secho(
        "   This file is managed by django-tailwind-cli and regenerated on every build.",
        fg=typer.colors.YELLOW,
    )
    typer.secho(f"   Your version has been copied to '{backup}'.", fg=typer.colors.YELLOW)
    typer.secho(
        "   To own it yourself, point TAILWIND_CLI_SRC_CSS at a file of your own — the library\n"
        "   never overwrites that one.",
        fg=typer.colors.YELLOW,
    )


def ensure_source_css(*, verbose: bool = False) -> None:
    """Write the managed source CSS for every configured entry.

    A single-file setup has one entry; `TAILWIND_CLI_CSS_MAP` has one per pair. Nothing happens for
    an entry whose file the user owns and that already exists.
    """
    c = get_config()

    if verbose:
        typer.secho("📄 Checking Tailwind CSS source configuration...", fg=typer.colors.CYAN)
        typer.secho(f"   • Overwrite default: {c.overwrite_default_config}", fg=typer.colors.BLUE)
        typer.secho(f"   • DaisyUI enabled: {c.use_daisy_ui}", fg=typer.colors.BLUE)

    # Built once: every entry gets the same seed, only the destination differs. A file that
    # already exists keeps whatever is in it — with a CSS_MAP those files are the user's, so
    # a later DaisyUI or @source change does not reach them. That is deliberate; the docs say so.
    content = build_source_css_content(
        use_daisy_ui=c.use_daisy_ui,
        inject_external_apps=c.auto_source_external_apps,
    )

    if verbose:
        typer.secho(f"📝 Content template: {'DaisyUI' if c.use_daisy_ui else 'Default'}", fg=typer.colors.BLUE)

    for entry in c.css_entries:
        _ensure_one_source_css(entry.src_css, content, manages_the_file=c.overwrite_default_config, verbose=verbose)


def _ensure_one_source_css(src_css: Path, content: str, *, manages_the_file: bool, verbose: bool) -> None:
    """Write one source CSS file, if it is ours to write and it is not already right.

    `manages_the_file` is False for a path the user configured — we create it once and never touch
    it again, because from then on it is theirs.
    """
    if manages_the_file:
        should_create = _should_recreate_file(src_css, content)
        existing_msg = "exists with different content" if src_css.exists() else "does not exist"
    else:
        should_create = not src_css.exists()
        existing_msg = "exists (preserving)" if src_css.exists() else "does not exist"

    if verbose:
        kind = "default config" if manages_the_file else "custom config"
        typer.secho(f"🔍 {src_css} ({kind}): {existing_msg}", fg=typer.colors.BLUE)

    if not should_create:
        if verbose:
            typer.secho("⏭️  Source CSS file is up-to-date, no changes needed", fg=typer.colors.GREEN)
        return

    if manages_the_file and src_css.exists() and not _looks_auto_generated(src_css.read_text()):
        _preserve_hand_edits(src_css)

    if verbose:
        typer.secho("📝 Creating/updating source CSS file...", fg=typer.colors.CYAN)

    src_css.parent.mkdir(parents=True, exist_ok=True)
    src_css.write_text(content)

    if verbose:
        typer.secho(f"✅ Created directory: {src_css.parent}", fg=typer.colors.GREEN)
        typer.secho(f"📄 Content length: {len(content)} characters", fg=typer.colors.BLUE)

    typer.secho(f"Created Tailwind Source CSS at '{src_css}'", fg=typer.colors.GREEN)
