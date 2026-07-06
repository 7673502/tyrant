import unittest
from dataclasses import FrozenInstanceError
from tyrant.models.ballot_box import BallotBox, submit_vote
from tyrant.models.enums import Vote


class TestBallotBox(unittest.TestCase):
    def setUp(self):
        self.ballot_box = BallotBox()

    def test_init(self):
        """Tests that the ballot box initializes with zero votes."""
        self.assertEqual(len(self.ballot_box.votes), 0)
        self.assertEqual(self.ballot_box.vote_count, 0)

    def test_submit_vote(self):
        """Tests submitting a vote to the ballot box."""
        self.ballot_box = submit_vote(self.ballot_box, 0, Vote.JA)

        self.assertEqual(self.ballot_box.votes, {0: Vote.JA})
        self.assertEqual(self.ballot_box.result, Vote.JA)

    def test_result_ja_majority(self):
        """Tests that the ballot box returns a ja result when there is a majority of ja votes."""
        for i in range(6):
            self.ballot_box = submit_vote(self.ballot_box, i, Vote.JA)

        for i in range(6, 10):
            self.ballot_box = submit_vote(self.ballot_box, i, Vote.NEIN)

        self.assertEqual(self.ballot_box.result, Vote.JA)

    def test_result_nein_majority(self):
        """Tests that the ballot box returns a nein result when there is a majority of nein votes."""
        for i in range(2):
            self.ballot_box = submit_vote(self.ballot_box, i, Vote.JA)

        for i in range(2, 6):
            self.ballot_box = submit_vote(self.ballot_box, i, Vote.NEIN)

        self.assertEqual(self.ballot_box.result, Vote.NEIN)

    def test_result_tie(self):
        """Tests that the ballot box returns a nein result when there is a tie."""
        self.ballot_box = submit_vote(self.ballot_box, 0, Vote.JA)
        self.ballot_box = submit_vote(self.ballot_box, 1, Vote.NEIN)

        self.assertEqual(self.ballot_box.result, Vote.NEIN)

    def test_vote_change(self):
        """Tests that a player can successfully change their submitted vote."""
        self.ballot_box = submit_vote(self.ballot_box, 1, Vote.NEIN)
        self.ballot_box = submit_vote(self.ballot_box, 1, Vote.JA)

        self.assertEqual(self.ballot_box.vote_count, 1)
        self.assertEqual(self.ballot_box.result, Vote.JA)

    def test_immutability(self):
        """Tests that the BallotBox dataclass is frozen and cannot be mutated."""
        with self.assertRaises(FrozenInstanceError):
            self.ballot_box.votes = {}

    def test_submit_vote_immutability(self):
        """Tests that submit_vote returns a new instance and does not mutate the original."""
        new_ballot_box = submit_vote(self.ballot_box, 0, Vote.JA)

        self.assertNotIn(0, self.ballot_box.votes)
        self.assertEqual(0, self.ballot_box.vote_count)
        self.assertEqual(0, len(self.ballot_box.votes))
        self.assertEqual(1, new_ballot_box.vote_count)
