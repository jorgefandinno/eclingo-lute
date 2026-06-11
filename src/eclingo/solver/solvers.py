import time
from typing import Iterator, Sequence

from clingo.core import Library
from clingo.symbol import Symbol

from eclingo.config import AppConfig
from eclingo.solver.generator import GeneratorReification
from eclingo.solver.tester import CandidateTesterReification

from .candidate import Candidate
from .world_view_builder import (
    WorldWiewBuilderReification,
    WorldWiewBuilderReificationWithShow,
)


class SolverReification:
    def __init__(
        self, lib: Library, reified_program: Sequence[Symbol], config: AppConfig
    ) -> None:
        self._lib = lib
        self._config = config
        self.reified_program = reified_program

        start_time = time.time()
        if config.ignore_shows:
            self._build_world_view_reification = WorldWiewBuilderReification(lib)
        else:
            self._build_world_view_reification = WorldWiewBuilderReificationWithShow(
                lib, reified_program
            )
        self.world_wivew_builder_grounding_time = time.time() - start_time

        start_time = time.time()
        self.test_candidate_reification = CandidateTesterReification(
            lib, self._config, reified_program
        )
        self.tester_grounding_time = time.time() - start_time

        self.preprocessing_time = 0.0
        start_time = time.time()
        if self._config.preprocessing_level == 0:  # pragma: no cover
            prepreocessing_info = None
            self.unsatisfiable = False
        else:
            prepreocessing_info = self.test_candidate_reification.fast_preprocessing()
            self.unsatisfiable = prepreocessing_info.unsatisfiable

            self.tester_grounding_time += self.test_candidate_reification.grounding_time
            self.preprocessing_time -= self.test_candidate_reification.grounding_time
            self.test_candidate_reification.grounding_time = 0
        self.preprocessing_time += time.time() - start_time

        start_time = time.time()
        self.generate_candidates_reification = GeneratorReification(
            lib,
            self._config,
            reified_program,
            prepreocessing_info,
        )
        self.generator_grounding_time = time.time() - start_time

    def solve(self) -> Iterator[Candidate]:
        if self.unsatisfiable:
            return
        for candidate in self.generate_candidates_reification():
            if candidate.proven() or self.test_candidate_reification(candidate):
                yield self._build_world_view_reification(candidate)

    def number_of_candidates(self) -> int:  # pragma: no cover
        return self.generate_candidates_reification.num_candidates

    def number_of_tester_calls(self) -> int:  # pragma: no cover
        return self.test_candidate_reification.num_solve_calls
