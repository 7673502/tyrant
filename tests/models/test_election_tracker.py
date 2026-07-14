import unittest
from dataclasses import FrozenInstanceError
from tyrant.models.election_tracker import ElectionTracker, increment_election_tracker


class TestElectionTracker(unittest.TestCase):
    def setUp(self):
        self.election_tracker = ElectionTracker()

    def test_init(self):
        """Tests that the election tracker initializes with zero failed elections."""
        self.assertEqual(self.election_tracker.failed_elections, 0)

    def test_failure(self):
        """Tests that incrementing failed elections correctly triggers a true value after three failures."""
        tracker, passed = increment_election_tracker(self.election_tracker)
        self.assertFalse(passed)
        tracker, passed = increment_election_tracker(tracker)
        self.assertFalse(passed)
        tracker, passed = increment_election_tracker(tracker)
        self.assertTrue(passed)

        tracker, passed = increment_election_tracker(tracker)
        self.assertFalse(passed)
        tracker, passed = increment_election_tracker(tracker)
        self.assertFalse(passed)
        tracker, passed = increment_election_tracker(tracker)
        self.assertTrue(passed)

    def test_immutability(self):
        """Tests that the ElectionTracker dataclass is frozen and cannot be mutated."""
        with self.assertRaises(FrozenInstanceError):
            self.election_tracker.failed_elections = 1

    def test_increment_election_tracker_immutability(self):
        """Tests that increment_election_tracker returns a new instance and does not mutate the original."""
        new_election_tracker, _ = increment_election_tracker(self.election_tracker)

        self.assertEqual(0, self.election_tracker.failed_elections)
        self.assertEqual(1, new_election_tracker.failed_elections)


if __name__ == "__main__":
    unittest.main()
