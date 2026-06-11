from unittest import TestCase

from clingo.core import Library

from tests.helper_build_programs import build_candidate


class TestCandidate(TestCase):
    """
    Test the Candidate class.
    """

    def setUp(self):
        self.lib = Library(message_limit=0)

    def test_candidate_prove(self):
        candidate = build_candidate(
            self.lib, ("k(a) k(b) no(k(c)) no(k(d))", "a b c d")
        )
        self.assertFalse(candidate.proven())

        candidate = build_candidate(
            self.lib, ("k(a) k(b) no(k(c)) no(k(d))", "a b no(c) no(d)")
        )
        self.assertTrue(candidate.proven())

        candidate = build_candidate(
            self.lib,
            ("k(a) k(b) no(k(no1(c))) no(k(not1(d)))", "a b no1(c) no(not1(d))"),
        )
        self.assertFalse(candidate.proven())

        candidate = build_candidate(
            self.lib,
            ("k(a) k(b) no(k(no1(c))) no(k(not1(d)))", "a b no(no1(c)) no(not1(d))"),
        )
        self.assertTrue(candidate.proven())
