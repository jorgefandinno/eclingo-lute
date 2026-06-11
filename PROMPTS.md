# Migrating clingo versions 5.8 -> 6 (claude)
We are going to update the project from using clingo package version 5.8 to the version 6.
- You can find the description of the API for clingo package version 5.8 in https://potassco.org/clingo/python-api/current/clingo/control.html
- You can find the description of the API for clingo package version 6 in https://potassco.org/clingo-preview/python-api/clingo.html
- These two versions have incompatible APIs.
- The current project uses clingo package version 5.8.

Create a plan to modify the code from using version 5.8 to version 6.
- In version 6, many functions take an argument `lib: clingo.core.Library` that was not part of the signature in version 5. Make a list of those functions and their correspondences between version to remember later.
- If any function calls a function that requires this new argument, the function also will take `lib: clingo.core.Library` as an argument. In the application, library must be created in the function `secondary_main` in the file `src/eclingo/main.py`. For tests, the library must be created in the `setUp` method and pased as an argument. Do not create objects of the class `clingo.core.Library` anywhere else.
- Major changes occur in the module `clingo.ast`. This module represents the abstract syntax tree of a logic program and the functions to parse and manipulate it.
  - In version 5.8, there is a single class `AST` with an attribut `ast_type` that specifies the type of the node.
  - In version 6, each node type has its own class.
  - For example, an object of the class `AST` with `ast_type = clingo.ast.ASTType.Rule` in version 5.8 corresponds to an object of the class `clingo.ast.StatementRule`.
  - Identify each `ASTType.*` in version 5.8 with is corresponding class in version 6. For example, `clingo.ast.ASTType.Rule` correspons to `clingo.ast.StatementRule`. Make a list of these correspondences to remember later.
- In version 5.8, there is a class `Transformer`. In version 6, we must use  `node.transform(lib, obj)`, `node.update(lib, **kw)`, `node.visit(obj)` instead. Check the the skill `clingo-5vs6-transformer`.
- Create an order for the submodules to start rewritting.
  - Start by describing the changes to `src/eclingo/clingox` and its subpackages. You will need to modify the tests in `tests/clingox` accordingly. Inside this module, start by submodules that have no dependencies in the project. Then, submodules that use the already modified modules.
  - Continue making a list for the rest of modules. Frist submodules that have no dependencies in the project Then, submodules that use the already modified modules.

You can run clingo 5.8 using the conda environment `clingo5`.
You can run clingo 6 using the conda environment `clingo6`.
In case of doubt ask.

# Fable summary

The migration is complete. eclingo now runs entirely on clingo 6, with every nox session green: the fast suite (106 tests), the clingox suite, the slow integration suite (validated against the pre-migration golden world-view files), 99% coverage, and a clean mypy run. The CLI produces the same output format as before for plain runs, --semantics=g94, --preprocessing-level=1, --output-e=rewritten, and --ignore-shows.

How the plan's risky parts landed:

- Vendored Reifier — rebuilt around clingo 6's observe-after-ground model: rules arrive via replay, while the output table and theory atoms are reconstructed in end_step(base). The output is byte-identical to clingox under clingo 5.8 on shared examples, so the solver meta-encodings needed no changes.
- Epistemic literal representation — clingo 6's typed AST forbids 5.8's trick of storing Literal nodes inside theory atom elements, so the pipeline now encodes the parsed literal as a canonical theory term (not-wrappers) with converters in ast_reify.py; sign logic moved onto BodyTheoryAtom.sign, and a new reify_epistemic_elements handles the u(...)-wrapping inside &k{...}.
- All nine Transformers became singledispatch functions per the skill pattern; ProgramBuilder became an AST→text→parse_string round trip; assign_external became assumptions over Free externals (clingo 6 freezes externals after the first solve).

Discoveries worth knowing (saved to memory and noted in code comments):

- Symbols from different Library objects are never equal — tests/generated_programs.py therefore exports its library and the data-driven tests reuse it.
- A Model is invalidated when its solve handle finishes; the tester/builder now use handle.last().
- Assumptions over atoms absent from the program raise in clingo 6 (5.8 treated them as false); the tester/builder filter them with the old semantics.
- One clingo 6.0.0 bug needed a workaround: passing fresh literals as HeadDisjunction elements crashes, so rewritten disjunction heads are wrapped in conditional literals and print as u(a): ; u(b): . — semantically identical.

Housekeeping: the six stale test/helper files plus pprint.py/ast_to_dict and their tests were deleted as agreed; pyproject.toml now requires clingo ^6.0.0 (the unused clingox pin and test-PyPI source are gone); noxfile.py runs sessions in the current env since the clingo 6 preview isn't on PyPI (I installed coverage/mypy/pylint/flake8 into clingo6 for this); CLAUDE.md paths point at clingo6.

Loose ends, non-blocking: tests/build_programs.py, tests/programs_back.py, and helper_test/inspector.py still contain clingo-5 code — they're standalone generation utilities never run by nox, and build_programs.py additionally shells out to clingo-5-only CLI options, so regenerating generated_programs.py would be a separate effort. Note that tests/test_app.py invokes python from PATH, so nox should be run with the clingo6 env activated (as CLAUDE.md says). My final typing/pragma fixes in six src files are uncommitted, on top of your "CLAUDE working" commits.