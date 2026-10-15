import unittest
from dataclasses import fields, is_dataclass

from tyrant.models.agent_fault import AgentFault
from tyrant.models.enums import GamePhase


class TestAgentFault(unittest.TestCase):
    def test_agent_fault_immutability(self):
        """Verifies that AgentFault is a frozen dataclass and its fields are immutable."""
        self.assertTrue(is_dataclass(AgentFault))
        self.assertTrue(AgentFault.__dataclass_params__.frozen)

        fault = AgentFault(
            uid=1,
            phase=GamePhase.NOMINATION,
            reason="InvalidMoveError('Bad reply')",
            fell_back=False,
            step=3,
            reply="Not JSON.",
        )
        for field in fields(fault):
            with self.assertRaises(Exception):
                setattr(fault, field.name, None)

    def test_agent_fault_reply_defaults_to_none(self):
        """Verifies that a fault without a rejected reply stores None."""
        fault = AgentFault(
            uid=1,
            phase=GamePhase.NOMINATION,
            reason="TimeoutError()",
            fell_back=True,
            step=0,
        )
        self.assertIsNone(fault.reply)


if __name__ == "__main__":
    unittest.main()
