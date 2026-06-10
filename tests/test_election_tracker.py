import unittest
from secret_tyrant.game import ElectionTracker

class TestElectionTracker(unittest.TestCase):
    def setUp(self):
        self.election_tracker = ElectionTracker()

    def test_init(self):
        self.assertEqual(self.election_tracker.failed_elections, 0)

    def test_failure(self):
        self.assertFalse(self.election_tracker.increment())
        self.assertFalse(self.election_tracker.increment())
        self.assertTrue(self.election_tracker.increment())

        self.assertFalse(self.election_tracker.increment())
        self.assertFalse(self.election_tracker.increment())
        self.assertTrue(self.election_tracker.increment())

