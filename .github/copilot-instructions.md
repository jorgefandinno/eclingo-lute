# Copilot instructions for `eclingo`

`eclingo` is a solver for Epistemic Logic Programs built on top of `clingo`. Most work in this repository is about preserving the parse → reify → generate/test pipeline rather than editing isolated Python modules.

## Environment

Use a Python environment that already has `clingo` installed. The repository docs and existing assistant guidance assume a conda environment such as:

```bash
conda activate clingo5
pip install -e .[dev]
```

## Test and lint commands

Run the existing `nox` sessions from the `clingo5` environment (or an equivalent environment with `clingo` available):

```bash
# Fast suite used during normal development
nox -Rs tests

# Slow integration/example tests
nox -Rs slow_tests

# Full test run with coverage; coverage must stay at or above 99%
nox -Rs all_tests

# Single test file
python -m unittest tests/test_eclingo.py -v

# Single test class
python -m unittest tests.test_eclingo.TestEclingoGround -v

# Auto-format
nox -rs format

# Type checking
nox -rs typecheck

# Linters
nox -rs pylint
nox -rs lint_flake8
```

`noxfile.py` is the source of truth for automated sessions. The fast suite, slow suite, and coverage run are intentionally separate.

## High-level architecture

The core pipeline is:

**Parse ELP syntax → Ground and reify with clingo/clingox → Generate candidate world views → Test candidates → Build `WorldView` output**

Key pieces:

- `src/eclingo/main.py` is the CLI entrypoint. It registers eclingo-specific options, always appends `--outf=3`, and either prints the rewritten program or prints world views.
- `src/eclingo/control.py` coordinates the full flow: add program text, ground it, prepare the solver, and iterate world views. It also takes over model enumeration from plain clingo by forcing `solve.project` and `solve.models`.
- `src/eclingo/parsing/parser.py` is where epistemic syntax is normalized before grounding. It parses `&k{}` / `&m{}` theory atoms, rewrites them into auxiliary atoms, and wraps user atoms before they reach the solver.
- `src/eclingo/grounder.py` feeds parsed ASTs into clingo, then reifies the grounded program via `clingox.reify.Reifier`. The solver layer consumes reified facts rather than the original AST.
- `src/eclingo/solver/solvers.py` wires together the three solver stages:
  - `generator.py` enumerates candidate world views from the reified program and ASP encodings in `*.lp`
  - `tester.py` checks whether a candidate is a valid world view and can derive preprocessing facts first
  - `world_view_builder.py` turns accepted candidates back into `EpistemicLiteral` / `WorldView` output, optionally filtered by `#show`

## Key repository conventions

- User atoms are wrapped with the `u(...)` prefix during parsing to avoid collisions with internal predicates.
- Epistemic literals are lowered to auxiliary atoms. In practice, `&k{L}` becomes a `k(...)` atom over the wrapped literal, while `not1(...)` and `not2(...)` encode `not L` and `not not L` forms inside epistemic contexts.
- The default CLI semantics are `g94`. In parsing, `g94` applies the extra double-negation transform for epistemic literals; `c19-1` does not.
- The solver is deliberately generate-and-test over reified facts, not a direct AST or source-level algorithm. Changes that affect semantics usually need coordinated updates across parsing, reification, generator encodings, tester logic, and world-view reconstruction.
- When propagation is enabled, candidate generation runs in two phases: proven candidates first, then unproved candidates.
- `#show` handling is solver-specific: show signatures are rewritten into helper rules during parsing, and `WorldWiewBuilderReificationWithShow` uses those reified show facts to filter the final world view output.
- `helper_test/` contains shared test helpers. Files named `tests/_test_*.py` are draft/disabled tests and are not part of the normal `nox` suites.
