"""
If using conda, then be sure to be in the nox environment different from "base" before running this file.

Note that clingo 6 is not available on PyPI, so the sessions run in the
current environment, which must provide clingo 6 and the development tools
(coverage, mypy, black, isort, pylint, flake8).

To run all tests: nox -Rs all_tests
The above also runs coverage.
The follwing only run a subset of tests and they do not run coverage.
To run only fast test: nox -Rs tests
To run only slow test: nox -Rs slow_tests
"""
import os

import nox

IS_GITHUB = "GITHUB_ACTIONS" in os.environ


@nox.session(python=False)
def format(session: nox.Session):
    session.run("isort", "--profile", "black", "src/eclingo", external=True)
    args = session.posargs if session.posargs else ["src/eclingo", "tests"]
    session.run("black", *args, external=True)


@nox.session(python=False)
def typecheck(session: nox.Session):
    session.run("mypy", "--implicit-optional", "src/eclingo", external=True)


@nox.session(python=False)
def all_tests(session: nox.Session):
    session.notify("tests")
    session.notify("slow_tests")
    session.notify("test_clingox")
    session.notify("coverage")


@nox.session(python=False)
def tests(session: nox.Session):
    session.run(
        "coverage",
        "run",
        "--data-file",
        ".coverage_fast",
        "-m",
        "unittest",
        "tests/test_reification.py",
        "tests/test_reification2.py",
        "tests/test_reification3.py",
        "tests/test_reification4.py",
        "tests/test_reification5.py",
        "tests/test_eclingo.py",
        "tests/test_generator_reification.py",
        "tests/test_literals.py",
        "tests/test_parsing.py",
        "tests/test_solver_reification.py",
        "tests/test_worldview_builder_reification.py",
        "tests/test_tester_reification.py",
        "tests/test_theory_atom_parser.py",
        "tests/test_astutil.py",
        "tests/test_transformers.py",
        "tests/test_util.py",
        "tests/test_preprocessor.py",
        "tests/test_propagator.py",
        "-v",
        external=True,
    )


@nox.session(python=False)
def test_clingox(session: nox.Session):
    session.run(
        "coverage",
        "run",
        "--data-file",
        ".coverage_clingox",
        "-m",
        "unittest",
        "tests/clingox/testing/test_ast.py",
        "tests/clingox/test_ast.py",
        "tests/clingox/test_reify.py",
        "tests/clingox/test_theory.py",
        "tests/clingox/test_backend.py",
        "tests/clingox/test_program.py",
        "tests/clingox/test_solving.py",
        "-v",
        external=True,
    )


@nox.session(python=False)
def slow_tests(session: nox.Session):
    session.run(
        "coverage",
        "run",
        "--data-file",
        ".coverage_slow",
        "-m",
        "unittest",
        "tests/test_app.py",
        "tests/test_eclingo_examples.py",
        "-v",
        external=True,
    )


@nox.session(python=False)
def coverage(session: nox.Session):
    omit = ["src/eclingo/__main__.py", "src/eclingo/__init__.py", "tests/*", "helper_test/*"]
    session.run(
        "coverage",
        "combine",
        ".coverage_fast",
        ".coverage_slow",
        ".coverage_clingox",
        external=True,
    )
    session.run(
        "coverage",
        "report",
        "--sort=cover",
        "--fail-under=99",
        "--omit",
        ",".join(omit),
        external=True,
    )


@nox.session(python=False)
def pylint(session: nox.Session):
    session.run("pylint", "src/eclingo", external=True)


@nox.session(python=False)
def lint_flake8(session: nox.Session):
    session.run("flake8", "src/eclingo", external=True)
