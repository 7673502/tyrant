import copy
import unittest

from tyrant.engine.prompt import (
    RESPONSE_FORMAT,
    RULES,
    SYSTEM_PROMPT,
    build_prompt,
    render_actions,
)
from tyrant.engine.renderer import render_text
from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.models.action import PassAction, SpeakAction, VoteAction
from tyrant.models.discussion import MAX_SPEECH_LENGTH
from tyrant.models.enums import GamePhase, Vote, WinCondition
from tyrant.models.game_state import GameState, create_game, scrub_state

UIDS = (1, 2, 3, 4, 5)
VOTE_ACTIONS = (
    VoteAction(description="Vote JA", vote=Vote.JA),
    VoteAction(description="Vote NEIN", vote=Vote.NEIN),
)
DISCUSSION_ACTIONS = (
    SpeakAction(description="Say something to the table"),
    PassAction(description="Stay silent"),
)


def _discussion_state() -> GameState:
    state = create_game(UIDS, 42, discussion_enabled=True)
    while state.phase != GamePhase.DISCUSSION:
        uid, action = next(
            (p.uid, get_legal_actions(state, p.uid)[0])
            for p in state.players
            if get_legal_actions(state, p.uid)
        )
        state = apply_action(state, action, uid)
    return state


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


class TestRenderActions(unittest.TestCase):
    def test_render_actions_immutability(self):
        """Verifies that render_actions returns equal text without mutating the actions."""
        before = copy.deepcopy(DISCUSSION_ACTIONS)
        self.assertEqual(
            render_actions(DISCUSSION_ACTIONS), render_actions(DISCUSSION_ACTIONS)
        )
        self.assertEqual(DISCUSSION_ACTIONS, before)

    def test_render_actions_numbers_descriptions(self):
        """Verifies that each action is listed under a heading with its 1-based number and description."""
        self.assertEqual(
            render_actions(VOTE_ACTIONS),
            "## Your Options\n1. Vote JA\n2. Vote NEIN",
        )

    def test_render_actions_notes_message_for_speak_only(self):
        """Verifies that only the speak option asks for a message."""
        lines = render_actions(DISCUSSION_ACTIONS).splitlines()
        self.assertIn("`message`", lines[1])
        self.assertNotIn("`message`", lines[2])


class TestBuildPrompt(unittest.TestCase):
    def setUp(self):
        self.state = _discussion_state()
        self.uid = self.state.discussion.current_speaker
        self.scrubbed = scrub_state(self.state, self.uid)
        self.actions = get_legal_actions(self.state, self.uid)

    def test_build_prompt_immutability(self):
        """Verifies that build_prompt returns equal text without mutating its inputs."""
        state_before = copy.deepcopy(self.scrubbed)
        actions_before = copy.deepcopy(self.actions)
        first = build_prompt(self.scrubbed, self.uid, self.actions)
        self.assertEqual(first, build_prompt(self.scrubbed, self.uid, self.actions))
        self.assertEqual(self.scrubbed, state_before)
        self.assertEqual(self.actions, actions_before)

    def test_build_prompt_is_state_then_options(self):
        """Verifies that the prompt is the rendered state followed by the options section."""
        self.assertEqual(
            build_prompt(self.scrubbed, self.uid, self.actions),
            render_text(self.scrubbed, self.uid) + "\n" + render_actions(self.actions),
        )
