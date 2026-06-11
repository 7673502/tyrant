import unittest
from tyrant.models import BallotBox, Vote

class TestBallotBox(unittest.TestCase):
    def setUp(self):
        self.ballot_box = BallotBox()

    def test_init(self):
        """Tests that the ballot box initializes with zero votes."""
        self.assertEqual(len(self.ballot_box.votes), 0)
        self.assertEqual(self.ballot_box.vote_count(), 0)

    def test_submit_vote(self):
        """Tests submitting a vote to the ballot box."""
        self.ballot_box.submit_vote(0, Vote.JA)

        self.assertEqual(self.ballot_box.votes, {0 : Vote.JA})
        self.assertEqual(self.ballot_box.get_result(), Vote.JA)

    def test_get_result_ja_majority(self):
        """Tests that the ballot box returns a ja result when there is a majority of ja votes."""
        for i in range(6):
            self.ballot_box.submit_vote(i, Vote.JA)

        for i in range(6, 10):
            self.ballot_box.submit_vote(i, Vote.NEIN)

        self.assertEqual(self.ballot_box.get_result(), Vote.JA)
                
    def test_get_result_nein_majority(self):
        """Tests that the ballot box returns a nein result when there is a majority of nein votes."""
        for i in range(2):
            self.ballot_box.submit_vote(i, Vote.JA)

        for i in range(2, 6):
            self.ballot_box.submit_vote(i, Vote.NEIN)

        self.assertEqual(self.ballot_box.get_result(), Vote.NEIN)

    def test_get_result_tie(self):
        """Tests that the ballot box returns a nein result when there is a tie."""
        self.ballot_box.submit_vote(0, Vote.JA)
        self.ballot_box.submit_vote(1, Vote.NEIN)

        self.assertEqual(self.ballot_box.get_result(), Vote.NEIN)
    
    def test_vote_change(self):
        """Tests that a player can successfully change their submitted vote."""
        self.ballot_box.submit_vote(1, Vote.NEIN)
        self.ballot_box.submit_vote(1, Vote.JA)

        self.assertEqual(self.ballot_box.vote_count(), 1)
        self.assertEqual(self.ballot_box.get_result(), Vote.JA)

