"""The django-click group behind ``manage.py tailwind``.

django-click gives us a Django-aware click group for free, but four things Django's own
``BaseCommand`` provides are missing from it, and each was a real regression when this package moved
off django-typer: it never runs the system checks, it swallows ``CommandError`` instead of letting a
``call_command`` caller catch it, it does not route ``call_command`` keyword options to the command
they belong to, and it leaves out several of Django's standard options. They are restored here
rather than in ``tailwind.py``, so the command module stays about the commands, and so every
django-click import sits in one file — the package ships no type information, which is why the calls
into the base class carry pyright suppressions.

None of the four is specific to this package: they are django-click defects that any project using
it would hit. This module is meant to be a bridge, not a permanent private fork of django-click's
semantics — see the bean ``django-tailwind-cli-96c3`` for the upstream report, and delete whichever
part lands upstream.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from contextvars import ContextVar
from typing import IO, Any

import click
from django.core.management.base import BaseCommand, CommandError
from djclick.adapter import (  # pyright: ignore[reportMissingTypeStubs]
    GroupAdapter,
    GroupRegistrator,
    suppress_colors,  # pyright: ignore[reportUnknownVariableType]
)

# Two questions, two variables: whether to run the checks, and whether we are under call_command.
# They are answered by different things — the first by --skip-checks or Django's default, the second
# by which entry point we came through — and only the second decides whether CommandError may
# escape. ContextVars rather than attributes: Django caches one group instance per process, so
# instance state would be shared by every caller and every thread.
_skip_checks: ContextVar[bool] = ContextVar("django_tailwind_cli_skip_checks", default=False)
_in_call_command: ContextVar[bool] = ContextVar("django_tailwind_cli_in_call_command", default=False)


def _skip_checks_option(_ctx: click.Context, _param: click.Parameter, value: bool) -> bool:  # noqa: FBT001
    if value:
        _skip_checks.set(True)
    return value


def _keyword_names(param: click.Parameter) -> Iterator[tuple[str, bool]]:
    """Every ``call_command`` keyword that spells this parameter, and whether it negates it.

    ``--color/--no-color`` is reachable as ``color=False`` and as ``no_color=True``; Django's own
    commands take both, and django-click's ``stealth_options`` derives names from ``opts`` only, so
    the negative half of every such flag goes missing.
    """
    if param.name:
        yield param.name, False
    for opt in param.secondary_opts:
        yield opt.lstrip("-").replace("-", "_"), True


def _as_argv(param: click.Parameter, value: Any) -> list[str]:
    """Spell one option the way click's parser expects to read it."""
    if isinstance(param, click.Argument) or param.multiple or param.nargs != 1:
        # Django's call_command spreads these into argv; this does not, and a wrong spelling would
        # reach the command as a plausible-looking value. Refuse loudly instead — no option in this
        # package has that shape yet, and the day one does, this is where it should stop.
        raise TypeError(f"'{param.name}' cannot be passed to call_command as a keyword.")
    if value is None:
        return []
    if getattr(param, "is_flag", False):
        if value:
            return [param.opts[0]]
        return [param.secondary_opts[0]] if param.secondary_opts else []
    return [param.opts[0], str(value)]


def keyword_argv(params: Sequence[click.Parameter], kwargs: dict[str, Any]) -> list[str]:
    """Take the keywords that belong to ``params`` and spell them back as argv.

    Going back through argv rather than into ``ctx.params`` is the whole trick: django-click builds
    the context first and pushes ``call_command``'s keywords in afterwards, so every option whose
    effect lives in a parse callback — colour, verbosity, ``--traceback`` — is quietly inert. Argv
    lets click's own callbacks do their job, and needs no list of which options those are.
    """
    argv: list[str] = []
    for param in params:
        for name, negated in _keyword_names(param):
            if name not in kwargs:
                continue
            value = kwargs.pop(name)
            # `no_color=False` is Django's default rather than a request to force colour on, so a
            # falsy negative spelling means nothing was asked for.
            argv.extend([] if negated and not value else _as_argv(param, not value if negated else value))
            break
    return argv


class TailwindCommand(click.Command):
    """A subcommand that runs Django's system checks before its body.

    Deliberately not the group callback, which is where this used to sit: click builds a
    subcommand's context — where an eager ``--help`` prints and exits — only *after* the group
    callback has returned, so checks hung off the callback also ran for ``tailwind build --help``.
    Django never checks for a help screen, and a project whose checks fail is exactly when someone
    reaches for it.
    """

    def invoke(self, ctx: click.Context) -> Any:
        run_system_checks()
        return super().invoke(ctx)


class TailwindGroup(GroupAdapter):
    """A django-click group that behaves the way a Django management command is expected to.

    * ``CommandError`` is let out of ``call_command`` instead of being turned into an exit code.
      django-click's own ``invoke`` catches it, prints it and exits 1 — right for the command line,
      whose ``run_from_argv`` only catches ``click.ClickException``, but wrong for a caller that is
      entitled to catch the exception.
    * Options given to ``call_command`` as keywords reach the command they name, group and
      subcommand alike, and one that names neither is refused rather than dropped.
    * ``skip_checks`` is honoured, so the system checks follow Django's rule: run on the command
      line, skipped for ``call_command`` unless asked for.
    * ``stdout`` and ``stderr`` are honoured, as they are for every other Django command.
    """

    command_class = TailwindCommand

    @property
    def stealth_options(self) -> list[str]:
        """Every keyword ``call_command`` may be handed.

        django-click reports only the group's parameters, so Django's unknown-option guard rejects
        ``call_command("tailwind", "build", verbose=True)`` before we ever see it. It also drops
        ``stdout``/``stderr`` out of ``base_stealth_options``, which every other Django command
        takes.

        Exactly the names :func:`keyword_argv` can route, so the guard and the router agree: a name
        that passed the guard and then had nowhere to go would be dropped in silence, which is the
        failure the guard exists to prevent.
        """
        return ["stdout", "stderr", *self._routable_names(self.params), *self._subcommand_names()]

    def _routable_names(self, params: Sequence[click.Parameter]) -> set[str]:
        return {name for param in params for name, _ in _keyword_names(param)}

    def _subcommand_names(self) -> set[str]:
        return {name for command in self.commands.values() for name in self._routable_names(command.params)}

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Entry point for ``call_command``; ``run_from_argv`` does not come through here."""
        # Django defaults skip_checks to True for call_command, and django-click drops the key
        # before we could read it downstream.
        skip_checks = bool(kwargs.pop("skip_checks", True))
        # django-click's stand-in argument parser echoes the positional arguments back as a keyword;
        # they are already in `args`.
        kwargs.pop("args", None)
        stdout: IO[str] | None = kwargs.pop("stdout", None)
        stderr: IO[str] | None = kwargs.pop("stderr", None)

        argv = [*keyword_argv(self.params, kwargs), *(str(a) for a in args)]
        command = next((self.commands[arg] for arg in argv if arg in self.commands), None)
        if command is not None:
            argv.extend(keyword_argv(command.params, kwargs))
        self._refuse_leftovers(command, kwargs)

        tokens = (_skip_checks.set(skip_checks), _in_call_command.set(True))
        try:
            with ExitStack() as stack:
                # The package writes through click, which resolves sys.stdout per call, so
                # redirecting is enough to honour the streams instead of quietly ignoring them.
                if stdout is not None:
                    stack.enter_context(redirect_stdout(stdout))
                if stderr is not None:
                    stack.enter_context(redirect_stderr(stderr))
                return super().execute(*argv)  # pyright: ignore[reportUnknownMemberType]
        except click.UsageError as e:
            # A misspelled subcommand reaches a programmatic caller as click's NoSuchCommand
            # otherwise. Django raises CommandError for an unknown command name, and so did this
            # package under django-typer; on the command line click keeps its own usage output.
            raise CommandError(str(e)) from e
        finally:
            _skip_checks.reset(tokens[0])
            _in_call_command.reset(tokens[1])

    def _refuse_leftovers(self, command: click.Command | None, kwargs: dict[str, Any]) -> None:
        """Anything still here belongs to a *different* subcommand, or to none at all."""
        if not kwargs:
            return
        unknown = ", ".join(sorted(kwargs))
        if command is None:
            raise TypeError(f"Unknown option(s) for the tailwind command: {unknown}.")
        valid = sorted(self._routable_names(command.params))
        detail = f"Valid options are: {', '.join(valid)}." if valid else "It takes no options."
        raise TypeError(f"Unknown option(s) for the {command.name} subcommand: {unknown}. {detail}")

    def run_from_argv(self, argv: list[str]) -> None:
        """Entry point for the command line, and the only place ``--skip-checks`` can be set.

        Bounded by a token so the flag cannot outlive one invocation: the option callback has no
        scope of its own, and a process that runs the command twice — a test suite, most obviously
        — would otherwise carry the first run's choice into the second.
        """
        token = _skip_checks.set(False)
        try:
            super().run_from_argv(argv)  # pyright: ignore[reportUnknownMemberType]
        finally:
            _skip_checks.reset(token)

    def invoke(self, ctx: click.Context) -> Any:
        if _in_call_command.get():
            # click.Group.invoke, not super(), to skip the CommandError handling in between.
            return click.Group.invoke(self, ctx)
        return super().invoke(ctx)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


class group(GroupRegistrator):  # noqa: N801  (matches djclick's own lowercase decorator classes)
    """``@group()``, registering :class:`TailwindGroup` instead of django-click's plain adapter.

    The class has to be swapped this way round: ``BaseRegistrator.__call__`` hardcodes
    ``cls=self.cls``, so ``cls`` cannot be passed through the decorator.
    """

    cls = TailwindGroup
    common_options = [
        *GroupRegistrator.common_options,
        # Two of Django's standard options django-click leaves out. --skip-checks is the more
        # pressing one now that this group runs the checks itself: without it the command line has
        # no way to opt out. `default=None` matters — suppress_colors is django-click's own
        # callback for --color, and a flag defaulting to False would tell it colour was refused.
        click.option(
            "--skip-checks",
            is_flag=True,
            expose_value=False,
            callback=_skip_checks_option,
            help="Skip system checks.",
        ),
        click.option(
            "--force-color",
            is_flag=True,
            default=None,
            expose_value=False,
            callback=suppress_colors,
            help="Force colorization of the command output.",
        ),
    ]

    def __call__(self, func: Callable[..., Any]) -> TailwindGroup:
        """Annotated only to say what django-click already returns."""
        return super().__call__(func)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportReturnType]


def run_system_checks() -> None:
    """Run Django's system checks the way a ``BaseCommand`` would before ``handle()``.

    django-click skips them entirely — it drops ``skip_checks`` and never calls ``check()`` — which
    would leave ``django_tailwind_cli.W001`` firing only on ``manage.py check`` and ``runserver``.
    ``call_command`` skips them by default, as it does for every other Django command.

    Raised from inside a subcommand (see :class:`TailwindCommand`), so a ``SystemCheckError`` —
    which subclasses ``CommandError`` — lands inside django-click's error rendering and prints one
    red line rather than a raw traceback.
    """
    if _skip_checks.get():
        return

    ctx = click.get_current_context(silent=True)
    color = None if ctx is None else ctx.color
    # check() writes through Django's own styling, so --color has to be translated rather than
    # passed on.
    BaseCommand(no_color=color is False, force_color=color is True).check()
