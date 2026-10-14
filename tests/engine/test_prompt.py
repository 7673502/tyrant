import unittest

from tyrant.engine.prompt import RESPONSE_FORMAT, RULES, SYSTEM_PROMPT
from tyrant.models.discussion import MAX_SPEECH_LENGTH
from tyrant.models.enums import WinCondition


class TestSystemPrompt(unittest.TestCase):
    def test_system_prompt_starts_with_rules(self):
        """Verifies that the system prompt is the rules followed by the response format."""
        self.assertEqual(SYSTEM_PROMPT, RULES + "\n" + RESPONSE_FORMAT)

    def test_system_prompt_contains_speech_limit(self):
        """Verifies that the system prompt states the maximum speech length."""
        self.assertIn(str(MAX_SPEECH_LENGTH), SYSTEM_PROMPT)

    def test_rules_name_every_win_condition(self):
        """Verifies that the rules mention every win condition by its rendered value."""
        for condition in WinCondition:
            with self.subTest(condition=condition):
                self.assertIn(f"`{condition.value}`", RULES)
