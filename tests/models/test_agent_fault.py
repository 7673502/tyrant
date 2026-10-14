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
            uid=1, phase=GamePhase.NOMINATION, reason="TimeoutError()", fell_back=False
        )
        for field in fields(fault):
            with self.assertRaises(Exception):
                setattr(fault, field.name, None)


if __name__ == "__main__":
    unittest.main()
