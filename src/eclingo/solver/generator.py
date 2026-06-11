from pathlib import Path
from typing import Iterator, Optional, Sequence

from clingo.backend import ExternalType
from clingo.control import Control
from clingo.core import Library
from clingo.solve import Model
from clingo.symbol import Function, Symbol

from eclingo import util
from eclingo.clingox.backend import SymbolicBackend
from eclingo.config import AppConfig
from eclingo.solver.tester import PreprocessingResult

from .candidate import Assumptions, Candidate

current_script_path = Path(__file__).parent


with open(current_script_path / "base_program.lp") as f:
    base_program = f.read()

with open(current_script_path / "generator_opt_common_program.lp") as f:
    common_opt_program = f.read()


preprocessing_program = """\
:- cautious(SA), atom_map(SA, A), not hold(A).
positive_extra_assumptions(OSA) :- cautious(OSA), symbolic_epistemic_atom(k(OSA)).
#show positive_extra_assumptions/1.

% hold(A)  :- atom_map(SA, A), cautious_objetive(SA). % this is incorrect, objecti atoms may hold wihtout been proved
% kp_hold(KA) :- epistemic_atom_map(k(SA), KA), cautious_objetive(SA).
"""


with open(current_script_path / "generator_opt_fact_program.lp") as f:
    fact_optimization_program = f.read()


propagation_program = """\
:- kp_hold(OA), epistemic_map(KA, OA), not hold(KA).

kp_hold(OA) :- cautious(OSA),  objective_atom_map(OSA, OA).

kp_conjunction(B) :- literal_tuple(B), kp_hold(A) : literal_tuple(B,  A), A > 0, not epistemic_atom_int(A);
                                          hold(A) : literal_tuple(B,  A), A > 0,     epistemic_atom_int(A);
                                   kp_not_hold(A) : literal_tuple(B, -A), A > 0, not epistemic_atom_int(A);
                                      not hold(A) : literal_tuple(B, -A), A > 0,     epistemic_atom_int(A).

kp_not_conjunction(B) :- literal_tuple(B), kp_not_hold(A), literal_tuple(B,  A), A > 0, not epistemic_atom_int(A).
kp_not_conjunction(B) :- literal_tuple(B),    not hold(A), literal_tuple(B,  A), A > 0,     epistemic_atom_int(A).
kp_not_conjunction(B) :- literal_tuple(B),     kp_hold(A), literal_tuple(B, -A), A > 0, not epistemic_atom_int(A).
kp_not_conjunction(B) :- literal_tuple(B),        hold(A), literal_tuple(B, -A), A > 0,     epistemic_atom_int(A).

kp_body(normal(B))     :- rule(_, normal(B)), kp_conjunction(B).
kp_not_body(normal(B)) :- rule(_, normal(B)), kp_not_conjunction(B).

singleton_disjuntion(H) :- rule(disjunction(H), _), #count{A : atom_tuple(H, A)} = 1.

kp_hold(A) : atom_tuple(H,A) :- rule(disjunction(H), B), singleton_disjuntion(H), kp_body(B).

rule_head_tuple(H, B) :- rule(disjunction(H), B).
rule_head_tuple(H, B) :- rule(choice(H), B).

kp_not_hold(A) :- objective_atom_int(A), kp_not_body(B) : atom_tuple(H,A), rule_head_tuple(H, B).

zhold(SA)        :- hold(A), atom_map(SA, A).
z_kp_hold(SA)     :- kp_hold(A), atom_map(SA, A).
z_kp_not_hold(SA) :- kp_not_hold(A), atom_map(SA, A).
z_rule_head(disjunction(SA),rule(H,B)) :- rule(H, B), H = disjunction(H1), atom_tuple(H1,A), atom_map(SA, A).
z_rule_head(choice(SA),rule(H,B)) :- rule(H, B), H = choice(H1), atom_tuple(H1,A), atom_map(SA, A).
z_rule_body(normal(SA),rule(H,B)) :- rule(H, normal(B)), literal_tuple(B,A), A > 0, atom_map(SA, A).
z_rule_body(normal(-SA),rule(H,B)) :- rule(H, normal(B)), literal_tuple(B,-A), A > 0, atom_map(SA, A).

positive_extra_assumptions(OSA) :-
    kp_hold(OA),
    objective_atom_map(OSA,OA),
    symbolic_epistemic_atom(k(OSA)).
negative_extra_assumptions(OSA) :-
    kp_not_hold(OA),
    objective_atom_map(OSA,OA),
    symbolic_epistemic_atom(k(OSA)).
% negative_extra_assumptions(not1(OSA)) :-
%    kp_hold(OA),
%    objective_atom_map(OSA,OA),
%    symbolic_epistemic_atom(k(not1(OSA))).
#show positive_extra_assumptions/1.
#show negative_extra_assumptions/1.

#external only_proved_candidates.
#external only_unproved_candidates.

explit_proven_candidates :- only_proved_candidates.
explit_proven_candidates :- only_unproved_candidates.

unproved(OA) :- explit_proven_candidates, epistemic_map(KA, OA), hold(KA), not kp_hold(OA).
exists_unproved :- explit_proven_candidates, unproved(_).

:-     exists_unproved, only_proved_candidates.
:- not exists_unproved, only_unproved_candidates.
"""


class GeneratorReification:
    def __init__(
        self,
        lib: Library,
        config: AppConfig,
        reified_program: Sequence[Symbol],
        preprocessing_facts: Optional[PreprocessingResult] = None,
    ) -> None:
        self._lib = lib
        self._config = config
        self.control = Control(lib, ["0"])
        self.control.config.solve.project.value = "show,3"
        self.reified_program = reified_program
        self.__initialeze_control(reified_program, preprocessing_facts)
        self.num_candidates = 0

    def __initialeze_control(self, reified_program, preprocessing_facts) -> None:
        with SymbolicBackend(self.control.backend) as backend:
            for symbol in reified_program:
                backend.add_rule([symbol])
        program = base_program + common_opt_program + fact_optimization_program
        if self._config.propagate:
            program += propagation_program
        if preprocessing_facts is not None:
            program += preprocessing_program
        self.control.parse_string(program)
        if preprocessing_facts is not None:
            with SymbolicBackend(self.control.backend) as backend:
                for atom in preprocessing_facts.lower:
                    backend.add_rule([Function(self._lib, "cautious", [atom])], [], [])
        self.control.ground()
        if self._config.propagate:
            # the externals are made free so that their truth values can be
            # set with assumptions
            with SymbolicBackend(self.control.backend) as backend:
                backend.add_external(
                    Function(self._lib, "only_proved_candidates"),
                    ExternalType.Free,
                )
                backend.add_external(
                    Function(self._lib, "only_unproved_candidates"),
                    ExternalType.Free,
                )

    def __call__(self) -> Iterator[Candidate]:
        if not self._config.propagate:
            yield from self._candidates()
        else:
            # note that with clingo 6 the truth value of externals cannot be
            # updated once the program has been solved, so assumptions are
            # used instead
            only_proved = Function(self._lib, "only_proved_candidates")
            only_unproved = Function(self._lib, "only_unproved_candidates")
            yield from self._candidates([(only_proved, True), (only_unproved, False)])
            yield from self._candidates([(only_proved, False), (only_unproved, True)])

    def _candidates(self, assumptions: Sequence = ()) -> Iterator[Candidate]:
        with self.control.start_solve(
            assumptions=list(assumptions), yield_=True
        ) as handle:
            for model in handle:
                candidate = self._model_to_candidate(model)
                self.num_candidates += 1
                yield candidate

    def _model_to_candidate(self, model: Model) -> Candidate:
        (
            positive_candidate,
            negative_candidate,
            positive_extra_assumptions,
            negative_extra_assumptions,
            _,
        ) = util.partition4(
            model.symbols(shown=True),
            lambda symbol: symbol.name == "positive_candidate",
            lambda symbol: symbol.name == "negative_candidate",
            lambda symbol: symbol.name == "positive_extra_assumptions",
            lambda symbol: symbol.name == "negative_extra_assumptions",
            fun=lambda symbol: symbol.arguments[0],
        )
        extra_assumptions = Assumptions(
            positive_extra_assumptions, negative_extra_assumptions
        )
        return Candidate(positive_candidate, negative_candidate, extra_assumptions)
