# mypy: allow-untyped-defs
"""Unit and regression tests for ``--help-group`` (#9452).

``pytest --help-group=<name>`` shows the help for a single option group, so
projects can see their own options without scrolling through all of
``pytest --help``.
"""

from __future__ import annotations

import argparse

from _pytest.config import ExitCode
from _pytest.helpconfig import HelpAction
from _pytest.pytester import Pytester
import pytest


CUSTOM_CONFTEST = """
def pytest_addoption(parser):
    group = parser.getgroup("custom", "custom options")
    group.addoption("--foo", help="foo option help")
    group.addoption("--bar-thing", action="store_true", help="bar option help")
"""

FILTERING_PENDING = pytest.mark.xfail(
    reason="--help-group output filtering is not implemented yet (#9452)",
    strict=True,
)


@pytest.fixture
def custom_group(pytester: Pytester) -> None:
    pytester.makeconftest(CUSTOM_CONFTEST)


# --- HelpAction ---------------------------------------------------------------


def test_help_action_without_value_sets_flag() -> None:
    """``--help`` takes no value and just turns help on."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--help-x", action=HelpAction, dest="help")
    namespace = parser.parse_args(["--help-x"])
    assert namespace.help is True


def test_help_action_with_value_stores_group_and_turns_on_help() -> None:
    """``--help-group`` stores the group name and also turns help on."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--help-group", action=HelpAction, nargs=None, dest="help_group"
    )
    namespace = parser.parse_args(["--help-group", "custom"])
    assert namespace.help_group == "custom"
    assert namespace.help is True


def test_help_action_defaults_to_false() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--help-group", action=HelpAction, nargs=None, dest="help_group"
    )
    assert parser.parse_args([]).help_group is False


# --- Normal filtering ---------------------------------------------------------


@FILTERING_PENDING
@pytest.mark.parametrize(
    "args", [["--help-group=custom"], ["--help", "--help-group=custom"]]
)
def test_help_group_shows_only_that_group(
    pytester: Pytester, custom_group: None, args: list[str]
) -> None:
    result = pytester.runpytest(*args)
    assert result.ret == ExitCode.OK
    result.stdout.fnmatch_lines(
        [
            "*custom options*",
            "*--foo=FOO*foo option help*",
            "*--bar-thing*bar option help*",
        ]
    )
    # Options from other groups are hidden.
    result.stdout.no_fnmatch_line("*-k EXPRESSION*")
    result.stdout.no_fnmatch_line("*--durations=N*")
    result.stdout.no_fnmatch_line("*--version*")


@FILTERING_PENDING
def test_help_group_works_for_builtin_group(pytester: Pytester) -> None:
    result = pytester.runpytest("--help-group=debugconfig")
    assert result.ret == ExitCode.OK
    result.stdout.fnmatch_lines(["*-V, --version*"])
    result.stdout.no_fnmatch_line("*-k EXPRESSION*")


def test_help_group_does_not_run_tests(pytester: Pytester, custom_group: None) -> None:
    pytester.makepyfile("def test_fails(): assert False")
    result = pytester.runpytest("--help-group=custom")
    assert result.ret == ExitCode.OK
    result.stdout.no_fnmatch_line("*1 failed*")
    result.stdout.no_fnmatch_line("*test_fails*")


def test_help_group_ignores_missing_required_options(pytester: Pytester) -> None:
    """Like ``--help``, it works even if a required option wasn't passed."""
    pytester.makeconftest(
        """
        def pytest_addoption(parser):
            group = parser.getgroup("custom", "custom options")
            group.addoption("--needed", required=True, help="needed option help")
        """
    )
    result = pytester.runpytest("--help-group=custom")
    assert result.ret == ExitCode.OK
    result.stdout.fnmatch_lines(["*--needed*needed option help*"])


# --- Invalid commands ---------------------------------------------------------


def test_help_group_unknown_name(pytester: Pytester, custom_group: None) -> None:
    result = pytester.runpytest("--help-group=nope")
    assert result.ret == ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(
        ["*unknown help group 'nope'; available groups:*general*custom*"]
    )


def test_help_group_empty_name(pytester: Pytester) -> None:
    result = pytester.runpytest("--help-group=")
    assert result.ret == ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*unknown help group ''*"])


def test_help_group_missing_value(pytester: Pytester) -> None:
    result = pytester.runpytest("--help-group")
    assert result.ret == ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*--help-group: expected one argument*"])


def test_help_group_unknown_name_does_not_run_tests(pytester: Pytester) -> None:
    pytester.makepyfile("def test_fails(): assert False")
    result = pytester.runpytest("--help-group=nope")
    assert result.ret == ExitCode.USAGE_ERROR
    result.stdout.no_fnmatch_line("*1 failed*")


# --- Regression: everything else works like before ------------------------------


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_full_help_still_shows_every_section(pytester: Pytester, flag: str) -> None:
    result = pytester.runpytest(flag)
    assert result.ret == ExitCode.OK
    result.stdout.fnmatch_lines(
        [
            "*-k EXPRESSION*",
            "*--durations=N*",
            "*-V, --version*",
            "*--help-group=HELP_GROUP*",
            "*configuration options*",
            "Environment variables:",
            "*to see*markers*pytest --markers*",
        ]
    )


def test_full_help_still_shows_custom_options(
    pytester: Pytester, custom_group: None
) -> None:
    result = pytester.runpytest("--help")
    assert result.ret == ExitCode.OK
    result.stdout.fnmatch_lines(
        ["*-k EXPRESSION*", "*custom options*", "*--foo=FOO*foo option help*"]
    )


def test_normal_run_has_help_options_off(pytester: Pytester) -> None:
    pytester.makepyfile(
        """
        def test_options(request):
            assert request.config.option.help is False
            assert request.config.option.help_group is False
        """
    )
    result = pytester.runpytest()
    assert result.ret == ExitCode.OK
    result.assert_outcomes(passed=1)
