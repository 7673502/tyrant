import unittest
from secret_tyrant.game import BallotBox, Vote

class TestBallotBox(unittest.TestCase):
    def setUp(self):
        self.ballot_box = BallotBox()

    def test_init(self):
        self.assertEqual(len(self.ballot_box.votes), 0)
        self.assertEqual(self.ballot_box.vote_count(), 0)

    def test_submit_vote(self):
        self.ballot_box.submit_vote(0, Vote.JA)

        self.assertEqual(self.ballot_box.votes, {0 : Vote.JA})
        self.assertEqual(self.ballot_box.get_result(), Vote.JA)

    def test_get_result_ja_majority(self):
        for i in range(6):
            self.ballot_box.submit_vote(i, Vote.JA)

        for i in range(6, 10):
            self.ballot_box.submit_vote(i, Vote.NEIN)

        self.assertEqual(self.ballot_box.get_result(), Vote.JA)
                
    def test_get_result_nein_majority(self):
        for i in range(2):
            self.ballot_box.submit_vote(i, Vote.JA)

        for i in range(2, 6):
            self.ballot_box.submit_vote(i, Vote.NEIN)

        self.assertEqual(self.ballot_box.get_result(), Vote.NEIN)

    def test_get_result_tie(self):
        self.ballot_box.submit_vote(0, Vote.JA)
        self.ballot_box.submit_vote(1, Vote.NEIN)

        self.assertEqual(self.ballot_box.get_result(), Vote.NEIN)
    
    def test_vote_change(self):
        self.ballot_box.submit_vote(1, Vote.NEIN)
        self.ballot_box.submit_vote(1, Vote.JA)

        self.assertEqual(self.ballot_box.vote_count(), 1)
        self.assertEqual(self.ballot_box.get_result(), Vote.JA)

