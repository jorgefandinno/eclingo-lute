# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`eclingo` is a solver for Epistemic Logic Programs (ELPs) built on top of the ASP system [`clingo`](https://github.com/potassco/clingo). It computes *world views* of epistemic logic programs under the G94 semantics (Gelfond 1994) and C19 semantics. The key extension over standard ASP is the modal operators `&k{}` (knows) and `&m{}` (may know) in rule bodies.

## Development Setup

Requires `clingo` installed via conda:
```bash
conda activate clingo5
pip install -e .[dev]
```

## Commands

### Testing

All commands below must be run inside the `clingo5` conda environment (or via its full path `/home/jorge/miniconda3/envs/clingo5/bin/nox`):

```bash
# Run all fast tests (recommended during development)
/home/jorge/miniconda3/envs/clingo5/bin/nox -Rs tests

# Run slow tests (integration/example tests)
/home/jorge/miniconda3/envs/clingo5/bin/nox -Rs slow_tests

# Run all tests + coverage (fails under 99%)
/home/jorge/miniconda3/envs/clingo5/bin/nox -Rs all_tests

# Run a single test file directly
/home/jorge/miniconda3/envs/clingo5/bin/python -m unittest tests/test_eclingo.py -v

# Run a single test class
/home/jorge/miniconda3/envs/clingo5/bin/python -m unittest tests.test_eclingo.TestEclingoGround -v
```

Note: `nox -r` skips recreating virtual environments (faster subsequent runs).

### Code Quality
```bash
/home/jorge/miniconda3/envs/clingo5/bin/nox -rs format          # auto-format with black + isort
/home/jorge/miniconda3/envs/clingo5/bin/nox -rs typecheck       # run mypy
/home/jorge/miniconda3/envs/clingo5/bin/nox -rs pylint          # run pylint
/home/jorge/miniconda3/envs/clingo5/bin/nox -rs lint_flake8     # run flake8
```

### Running eclingo
```bash
eclingo <file.lp>                        # solve an ELP
eclingo --semantics=g94 <file.lp>        # use G94 semantics
eclingo --output-e=rewritten <file.lp>   # show rewritten program
eclingo --preprocessing-level=1 <file.lp> # enable preprocessing
```

## Architecture

The pipeline is: **Parse → Ground (Reify) → Solve (Generate → Test → Build WorldView)**

### `src/eclingo/`

- **`main.py`** — CLI entry point; `Application` class wraps clingo's application framework. `secondary_main` always appends `--outf=3` (reification output format).
- **`control.py`** — `Control` orchestrates the full pipeline: `add_program` → `ground` → `preprocess` → `prepare_solver` → `solve` (yields `WorldView` objects).
- **`config.py`** — `AppConfig` holds all configuration: `eclingo_semantics` (`"g94"` or `"c19-1"`), `preprocessing_level`, `propagate`, `ignore_shows`.
- **`grounder.py`** — `Grounder` parses ELP syntax into standard ASP via `parse_program`, then reifies the grounded program using `clingox.reify.Reifier`, producing `reified_facts: List[Symbol]`.
- **`literals.py`** — `Literal` and `EpistemicLiteral` data classes used in world view output.
- **`util.py`** — `partition4`: partitions a list of symbols into 4 groups by predicate name.

### `src/eclingo/parsing/`

- **`parser.py`** — `_ProgramParser` transforms ELP syntax to standard ASP before grounding. Key steps:
  1. Applies `eclingo_theory` (theory definition for `&k{}` / `&m{}`).
  2. Calls `parse_epistemic_literals_elements` and `parse_m_literals`.
  3. Applies `reify_symbolic_atoms` (from `clingox`) with prefix `"u"`.
  4. Applies `replace_epistemic_literals_by_auxiliary_atoms` to replace `&k{L}` with atom `k(L)`.
  - For G94 semantics, additionally calls `double_negate_epistemic_listerals`.

- **`transformers/theory_parser_epistemic.py`** — Core transformation functions that convert `&k{...}` / `&m{...}` theory atoms into auxiliary atoms (`k(...)`, `not1(...)`, `not2(...)`).
- **`transformers/ast_reify.py`** — Converts theory atoms to AST function terms for reification.
- **`transformers/parser_negations.py`** — Handles strong negation (`-`) replacement in epistemic contexts.

### `src/eclingo/solver/`

The solver implements a generate-and-test algorithm over reified programs:

- **`solvers.py`** — `SolverReification` orchestrates the solver. On init: builds world view builder, tester, runs preprocessing, builds generator. `solve()` iterates generator candidates and yields those passing the tester.
- **`generator.py`** — `GeneratorReification` uses clingo to enumerate candidate world views from the reified program. Loads `base_program.lp`, `generator_opt_common_program.lp`, `generator_opt_fact_program.lp`, and (optionally) `propagation_program`. When propagation is enabled, runs in two phases: proven candidates first, then unproven.
- **`tester.py`** — `CandidateTesterReification` verifies whether a candidate is a valid world view by testing with assumptions. Also provides `fast_preprocessing()` which uses a fixpoint approximation loop to derive forced-true/false epistemic atoms before solving.
- **`candidate.py`** — `Candidate(pos, neg, extra_assumptions)` namedtuple; `proven()` returns True if all epistemic assumptions are already covered by `extra_assumptions` (no tester call needed).
- **`world_view.py`** — `WorldView(symbols)` namedtuple; `symbols` is a list of `EpistemicLiteral`.
- **`world_view_builder.py`** — Converts a `Candidate` to a `WorldView`. `WorldWiewBuilderReificationWithShow` additionally filters by `#show` statements.
- **`base_program.lp`** — Core meta-encoding: computes `hold/1`, `fact/1`, `atom_map/2`, `positive_candidate/1`, `negative_candidate/1` from reified program facts.

### Key Conventions

- **Reification**: The program is reified by `clingox.reify.Reifier`, producing facts like `rule/2`, `atom_tuple/2`, `literal_tuple/2`, `output/2` which the solver meta-encodings reason over.
- **Symbolic atom prefix `u`**: All user atoms are wrapped as `u(atom)` during parsing to avoid name collisions with internal predicates.
- **Epistemic atoms**: `&k{L}` becomes `k(u(L))` internally; `not1`/`not2` represent `not` / `not not` forms of the literal inside.
- **Two semantics**: `"g94"` (default for CLI) applies double negation to epistemic literals during parsing; `"c19-1"` does not.
- **Test separation**: `tests/` contains unit + integration tests; `helper_test/` contains shared test utilities. Files prefixed with `_test_` are disabled/draft tests.
- **Coverage threshold**: 99% required; `src/eclingo/__main__.py` and `src/eclingo/__init__.py` are excluded.
