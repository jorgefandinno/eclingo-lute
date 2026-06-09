# Migrating clingo versions 5.8 -> 6
We are going to update the project from using clingo package version 5.8 to the version 6.
You can find the description of the API for clingo package version 5.8 in https://potassco.org/clingo/python-api/current/clingo/control.html
You can find the description of the API for clingo package version 6 in https://potassco.org/clingo-preview/python-api/clingo.html
These two versions have incompatible APIs.
The current project uses clingo package version 5.8.
Create a plan to modify the code from using version 5.8 to version 6.
In version 6, many functions take an argument `lib: clingo.core.Library` that was not part of the signature in version 5. If any function calls a function that requires this new argument, the function also will take `lib: clingo.core.Library` as an argument. The library will be created in the function `secondary_main` in the file `src/eclingo/main.py`.
Start by describing the changes to `src/eclingo/clingox` and its subpackages. You will need to modify the tests in `tests/clingox` accordingly.
In your plan, start by modules that have no dependencies in the project. Then, modules that use the already modified modules, and so on.
You can run clingo 5.8 using the conda environment `clingo5`.
You can run clingo 6 using the conda environment `clingo6`.
In case of doubt ask.

---

