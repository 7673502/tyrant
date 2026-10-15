import unittest

from tyrant.exceptions import AgentError, InvalidMoveError, TyrantError


class TestExceptions(unittest.TestCase):
    def test_invalid_move_error_reply_defaults_to_none(self):
        """Verifies that an InvalidMoveError without a reply stores None and keeps its message."""
        error = InvalidMoveError("Not offered")
        self.assertIsNone(error.reply)
        self.assertEqual(str(error), "Not offered")

    def test_invalid_move_error_keeps_reply(self):
        """Verifies that an InvalidMoveError stores the rejected reply it was given."""
        error = InvalidMoveError("Bad JSON", reply="Not JSON.")
        self.assertEqual(error.reply, "Not JSON.")
        self.assertEqual(str(error), "Bad JSON")

    def test_agent_error_is_tyrant_error(self):
        """Verifies that AgentError is a TyrantError."""
        self.assertTrue(issubclass(AgentError, TyrantError))


if __name__ == "__main__":
    unittest.main()
