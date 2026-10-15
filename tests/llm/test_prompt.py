import asyncio
import copy
import json
import unittest
from random import Random

from tyrant.engine.game_runner import GameRunner
from tyrant.engine.renderer import render_text
from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.exceptions import InvalidMoveError
from tyrant.llm.prompt import (
    RESPONSE_FORMAT,
    RULES,
    SYSTEM_PROMPT,
    build_prompt,
    parse_action,
    render_actions,
)
from tyrant.models.action import Action, PassAction, SpeakAction, VoteAction
from tyrant.models.discussion import MAX_SPEECH_LENGTH
from tyrant.models.enums import GamePhase, Vote, WinCondition
from tyrant.models.game_state import GameState, create_game, scrub_state

UIDS = (1, 2, 3, 4, 5)
SEEDS = (0, 1, 2)
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


class FakeLLMAgent:
    """Builds a prompt and answers with canned JSON naming a random option."""

    def __init__(self, uid: int, seed: int):
        self.uid = uid
        self.rng = Random(seed * len(UIDS) + uid)

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        prompt = build_prompt(state, self.uid, valid_actions)
        number = self.rng.randrange(len(valid_actions)) + 1
        reply = {"action": number, "message": f"Prompt had {len(prompt)} characters."}
        return parse_action(f"Thinking it over.\n{json.dumps(reply)}", valid_actions)


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


class TestParseAction(unittest.TestCase):
    def test_parse_action_immutability(self):
        """Verifies that parse_action returns a new speak action without mutating the offered ones."""
        before = copy.deepcopy(DISCUSSION_ACTIONS)
        action = parse_action('{"action": 1, "message": "Hi"}', DISCUSSION_ACTIONS)
        self.assertIsNot(action, DISCUSSION_ACTIONS[0])
        self.assertEqual(DISCUSSION_ACTIONS, before)

    def test_parse_action_bare_json(self):
        """Verifies that a reply of only a JSON object selects the numbered option."""
        self.assertIs(parse_action('{"action": 2}', VOTE_ACTIONS), VOTE_ACTIONS[1])

    def test_parse_action_after_reasoning(self):
        """Verifies that reasoning before the JSON object is ignored."""
        response = 'Player 3 seems trustworthy {maybe}.\n\n{"action": 1}'
        self.assertIs(parse_action(response, VOTE_ACTIONS), VOTE_ACTIONS[0])

    def test_parse_action_last_object_wins(self):
        """Verifies that the last JSON object with an action is used."""
        response = 'First {"action": 1}, then {"action": 2} and {"note": 1}.'
        self.assertIs(parse_action(response, VOTE_ACTIONS), VOTE_ACTIONS[1])

    def test_parse_action_ignores_message_on_other_actions(self):
        """Verifies that a message on a non-speak option returns the offered action unchanged."""
        response = '{"action": 2, "message": "Hello"}'
        self.assertIs(parse_action(response, DISCUSSION_ACTIONS), DISCUSSION_ACTIONS[1])

    def test_parse_action_speak_with_message(self):
        """Verifies that choosing to speak returns the speak action carrying the message."""
        action = parse_action(
            '{"action": 1, "message": "I trust Player 2."}', DISCUSSION_ACTIONS
        )
        self.assertEqual(
            action,
            SpeakAction(
                description="Say something to the table", message="I trust Player 2."
            ),
        )

    def test_parse_action_rejects_missing_json(self):
        """Verifies that a reply without a JSON object raises InvalidMoveError."""
        with self.assertRaises(InvalidMoveError):
            parse_action("I vote ja.", VOTE_ACTIONS)

    def test_parse_action_rejects_bad_action_numbers(self):
        """Verifies that out-of-range, non-integer and missing actions raise InvalidMoveError."""
        for response in (
            '{"action": 0}',
            '{"action": 3}',
            '{"action": "1"}',
            '{"action": true}',
            '{"message": "Hi"}',
        ):
            with self.subTest(response=response):
                with self.assertRaises(InvalidMoveError):
                    parse_action(response, VOTE_ACTIONS)

    def test_parse_action_rejects_speech_without_message(self):
        """Verifies that speaking without a message or with an empty one raises InvalidMoveError."""
        for response in (
            '{"action": 1}',
            '{"action": 1, "message": ""}',
            '{"action": 1, "message": "   "}',
            '{"action": 1, "message": 5}',
        ):
            with self.subTest(response=response):
                with self.assertRaises(InvalidMoveError):
                    parse_action(response, DISCUSSION_ACTIONS)


class TestPromptGame(unittest.TestCase):
    def test_prompted_games_finish_without_faults(self):
        """Verifies that agents answering through build_prompt and parse_action finish games with no faults."""
        for seed in SEEDS:
            with self.subTest(seed=seed):
                agents = [FakeLLMAgent(uid, seed) for uid in UIDS]
                runner = GameRunner(agents, seed=seed, discussion_enabled=True)
                state = asyncio.run(runner.run())
                self.assertEqual(state.phase, GamePhase.GAME_OVER)
                self.assertEqual(runner.faults, ())
