import asyncio
import importlib.util
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from frozendict import frozendict

from tyrant.engine.game_runner import GameRunner
from tyrant.engine.router import get_legal_actions
from tyrant.exceptions import AgentError, InvalidMoveError
from tyrant.llm.prompt import MAX_NOTES_LENGTH, SYSTEM_PROMPT, build_prompt
from tyrant.models.enums import DiscussionContext, GamePhase
from tyrant.models.event import SpeechEvent
from tyrant.models.game_state import create_game

HAS_LITELLM = importlib.util.find_spec("litellm") is not None

if HAS_LITELLM:
    import litellm
    from litellm import ModelResponse, Usage
    from litellm.types.utils import PromptTokensDetailsWrapper

    from tyrant.llm.agent import LLMAgent

UIDS = (1, 2, 3, 4, 5)
MODEL = "openai/gpt-4o-mini"


def _reply(action: int, **fields: str) -> str:
    return "Let me think.\n" + json.dumps({"action": action, **fields})


class ScriptedCompletion:
    """Answers each acompletion call with the next scripted reply through litellm's mock_response."""

    def __init__(self, *replies):
        self.replies = iter(replies)
        self.calls: list[dict] = []
        self.responses: list = []
        self.acompletion = litellm.acompletion

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        response = await self.acompletion(**kwargs, mock_response=next(self.replies))
        self.responses.append(response)
        return response


@unittest.skipUnless(HAS_LITELLM, "litellm is not installed")
class TestLLMAgent(unittest.TestCase):
    def setUp(self):
        self.state = create_game(UIDS, 42)
        self.uid = self.state.players[self.state.president_index].uid
        self.actions = get_legal_actions(self.state, self.uid)
        self.agent = LLMAgent(self.uid, MODEL)

    async def _choose_each(self, count: int) -> list:
        results = []
        for _ in range(count):
            try:
                results.append(await self.agent.choose_action(self.state, self.actions))
            except InvalidMoveError as e:
                results.append(e)
        return results

    def _play(self, *replies) -> tuple[ScriptedCompletion, list]:
        scripted = ScriptedCompletion(*replies)
        with patch.object(litellm, "acompletion", scripted):
            results = asyncio.run(self._choose_each(len(replies)))
        return scripted, results

    def test_valid_reply_becomes_action(self):
        """Verifies that the option named by a reply passed through completion_kwargs is returned."""
        agent = LLMAgent(
            self.uid, MODEL, completion_kwargs=frozendict(mock_response=_reply(2))
        )
        action = asyncio.run(agent.choose_action(self.state, self.actions))
        self.assertIs(action, self.actions[1])

    def test_sends_system_prompt_and_built_prompt(self):
        """Verifies that the system prompt and the built prompt are sent to the configured model."""
        scripted, _ = self._play(_reply(1))
        self.assertEqual(scripted.calls[0]["model"], MODEL)
        self.assertEqual(
            scripted.calls[0]["messages"],
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_prompt(self.state, self.uid, self.actions),
                },
            ],
        )

    def test_persona_extends_system_prompt(self):
        """Verifies that a persona is sent after the shared system prompt under its own heading."""
        self.agent = LLMAgent(self.uid, MODEL, persona="Cautious.")
        scripted, _ = self._play(_reply(1))
        system = scripted.calls[0]["messages"][0]
        self.assertEqual(system["role"], "system")
        self.assertTrue(system["content"].startswith(SYSTEM_PROMPT))
        self.assertTrue(system["content"].endswith("## Your Personality\nCautious.\n"))

    def test_profile_has_model_and_persona(self):
        """Verifies that the profile names the model and the persona."""
        agent = LLMAgent(self.uid, MODEL, persona="Cautious.")
        self.assertEqual(agent.profile, frozendict(model=MODEL, persona="Cautious."))

    def test_accepted_notes_replace_previous_notes(self):
        """Verifies that notes from an accepted reply replace the old notes and appear in the next prompt."""
        scripted, _ = self._play(
            _reply(1, notes="Player 2 is shady."),
            _reply(1, notes="Player 3 is shady."),
            _reply(1),
        )
        self.assertEqual(self.agent.notes, "Player 3 is shady.")
        self.assertEqual(
            scripted.calls[2]["messages"][1]["content"],
            build_prompt(self.state, self.uid, self.actions, "Player 3 is shady."),
        )

    def test_reply_without_notes_keeps_notes(self):
        """Verifies that an accepted reply without notes keeps the previous notes."""
        self._play(_reply(1, notes="Trust nobody."), _reply(2))
        self.assertEqual(self.agent.notes, "Trust nobody.")

    def test_rejected_reply_changes_nothing_and_adds_feedback(self):
        """Verifies that a rejected reply keeps the notes, raises, and is fed back once on the next call."""
        rejected = _reply(99, notes="Lost notes.")
        scripted, results = self._play(
            _reply(1, notes="Kept notes."), rejected, _reply(2), _reply(1)
        )
        self.assertIsInstance(results[1], InvalidMoveError)
        self.assertEqual(results[1].reply, rejected)
        self.assertEqual(self.agent.notes, "Kept notes.")
        self.assertIs(results[2], self.actions[1])
        retry = scripted.calls[2]["messages"]
        self.assertEqual(len(retry), 4)
        self.assertEqual(retry[2], {"role": "assistant", "content": rejected})
        self.assertEqual(retry[3]["role"], "user")
        self.assertIn("rejected", retry[3]["content"])
        self.assertIn(f"between 1 and {len(self.actions)}", retry[3]["content"])
        self.assertEqual(len(scripted.calls[3]["messages"]), 2)

    def test_retry_message_asks_for_plain_json(self):
        """Verifies that the retry feedback asks for one trailing JSON object and no tool-call syntax."""
        scripted, _ = self._play(_reply(99), _reply(1))
        feedback = scripted.calls[1]["messages"][3]["content"]
        self.assertIn('end with one JSON object like {"action": 2', feedback)
        self.assertIn("Do not use tool-call or XML syntax.", feedback)

    def test_rejection_not_replayed_for_new_state_with_same_options(self):
        """Verifies that a rejected reply is not fed back when the next decision has a different state but the same options."""
        scripted = ScriptedCompletion(_reply(99), _reply(1))
        later_state = replace(
            self.state,
            events=self.state.events
            + (
                SpeechEvent(
                    uid=self.uid, text=None, context=DiscussionContext.AFTER_NOMINATION
                ),
            ),
        )

        async def choose():
            with self.assertRaises(InvalidMoveError):
                await self.agent.choose_action(self.state, self.actions)
            return await self.agent.choose_action(later_state, self.actions)

        with patch.object(litellm, "acompletion", scripted):
            action = asyncio.run(choose())
        self.assertIs(action, self.actions[0])
        self.assertEqual(len(scripted.calls[1]["messages"]), 2)

    def test_rejection_replayed_for_same_state_after_provider_error(self):
        """Verifies that a rejection survives a provider error and is fed back when the same state is asked again."""
        replies = iter((_reply(99), None, _reply(1)))
        calls = []
        acompletion = litellm.acompletion

        async def flaky(**kwargs):
            calls.append(kwargs)
            reply = next(replies)
            if reply is None:
                raise ConnectionError("Connection reset")
            return await acompletion(**kwargs, mock_response=reply)

        async def choose():
            with self.assertRaises(InvalidMoveError):
                await self.agent.choose_action(self.state, self.actions)
            with self.assertRaises(AgentError):
                await self.agent.choose_action(self.state, self.actions)
            return await self.agent.choose_action(self.state, self.actions)

        with patch.object(litellm, "acompletion", flaky):
            action = asyncio.run(choose())
        self.assertIs(action, self.actions[0])
        self.assertEqual(len(calls[2]["messages"]), 4)

    def test_provider_error_raises_agent_error(self):
        """Verifies that an exception from the provider call is raised as an AgentError with the original as its cause."""

        async def failing(**kwargs):
            raise ConnectionError("Connection reset")

        with patch.object(litellm, "acompletion", failing):
            with self.assertRaises(AgentError) as raised:
                asyncio.run(self.agent.choose_action(self.state, self.actions))
        self.assertIsInstance(raised.exception.__cause__, ConnectionError)

    def test_notes_are_capped_and_collapsed(self):
        """Verifies that saved notes have collapsed whitespace and are cut at a word boundary within MAX_NOTES_LENGTH characters."""
        self._play(_reply(1, notes="a \n\n b " + "word " * MAX_NOTES_LENGTH))
        self.assertLessEqual(len(self.agent.notes), MAX_NOTES_LENGTH)
        self.assertTrue(self.agent.notes.startswith("a b word"))
        self.assertTrue(self.agent.notes.endswith("word…"))

    def test_usage_totals_add_up(self):
        """Verifies that token and cost totals sum every response, including rejected ones."""
        cached = ModelResponse(
            model="gpt-4o-mini",
            choices=[{"message": {"role": "assistant", "content": _reply(1)}}],
            usage=Usage(
                prompt_tokens=100,
                completion_tokens=5,
                total_tokens=105,
                prompt_tokens_details=PromptTokensDetailsWrapper(cached_tokens=80),
            ),
        )
        scripted, _ = self._play(_reply(1), _reply(99), cached)
        self.assertEqual(
            self.agent.prompt_tokens,
            sum(r.usage.prompt_tokens for r in scripted.responses),
        )
        self.assertEqual(
            self.agent.completion_tokens,
            sum(r.usage.completion_tokens for r in scripted.responses),
        )
        self.assertEqual(self.agent.cached_tokens, 80)
        self.assertAlmostEqual(
            self.agent.cost,
            sum(
                litellm.completion_cost(completion_response=r)
                for r in scripted.responses
            ),
        )
        self.assertGreater(self.agent.cost, 0)

    def test_unknown_cost_does_not_fail_move(self):
        """Verifies that a model without a known price still moves and counts tokens at zero cost."""
        agent = LLMAgent(
            self.uid,
            "openai/not-a-real-model",
            completion_kwargs=frozendict(mock_response=_reply(1)),
        )
        with patch.object(litellm, "suppress_debug_info", True):
            action = asyncio.run(agent.choose_action(self.state, self.actions))
        self.assertIs(action, self.actions[0])
        self.assertEqual(agent.cost, 0.0)
        self.assertGreater(agent.prompt_tokens, 0)

    def _play_recorded(self, *replies) -> tuple[ScriptedCompletion, list, list]:
        exchanges = []
        self.agent = LLMAgent(self.uid, MODEL, on_exchange=exchanges.append)
        scripted, results = self._play(*replies)
        return scripted, results, exchanges

    def test_on_exchange_receives_prompt_and_reply(self):
        """Verifies that on_exchange gets the sent messages and the raw reply of an accepted call."""
        reply = _reply(1, notes="Hmm.")
        scripted, _, exchanges = self._play_recorded(reply)
        self.assertEqual(len(exchanges), 1)
        self.assertEqual(exchanges[0]["uid"], self.uid)
        self.assertEqual(exchanges[0]["messages"], scripted.calls[0]["messages"])
        self.assertEqual(exchanges[0]["reply"], reply)
        self.assertIsNone(exchanges[0]["error"])
        json.dumps(exchanges[0])

    def test_on_exchange_receives_rejected_reply_and_retry_messages(self):
        """Verifies that a rejected call reports its error and the retry call reports the feedback messages."""
        rejected = _reply(99)
        scripted, _, exchanges = self._play_recorded(rejected, _reply(1))
        self.assertEqual(len(exchanges), 2)
        self.assertEqual(exchanges[0]["reply"], rejected)
        self.assertIn("InvalidMoveError", exchanges[0]["error"])
        self.assertEqual(len(exchanges[1]["messages"]), 4)
        self.assertEqual(exchanges[1]["messages"], scripted.calls[1]["messages"])
        self.assertIsNone(exchanges[1]["error"])

    def test_on_exchange_receives_provider_error(self):
        """Verifies that a failed provider call reports no reply, zero usage and the AgentError."""
        exchanges = []
        agent = LLMAgent(self.uid, MODEL, on_exchange=exchanges.append)

        async def failing(**kwargs):
            raise ConnectionError("Connection reset")

        with patch.object(litellm, "acompletion", failing):
            with self.assertRaises(AgentError):
                asyncio.run(agent.choose_action(self.state, self.actions))
        self.assertEqual(len(exchanges), 1)
        self.assertIsNone(exchanges[0]["reply"])
        self.assertEqual(exchanges[0]["prompt_tokens"], 0)
        self.assertEqual(exchanges[0]["cost"], 0.0)
        self.assertIn("Connection reset", exchanges[0]["error"])

    def test_on_exchange_reports_per_call_usage(self):
        """Verifies that each exchange holds that call's usage and that they sum to the agent's totals."""
        scripted, _, exchanges = self._play_recorded(_reply(1), _reply(2))
        for exchange, response in zip(exchanges, scripted.responses):
            with self.subTest(response=response.id):
                self.assertEqual(
                    exchange["prompt_tokens"], response.usage.prompt_tokens
                )
                self.assertEqual(
                    exchange["completion_tokens"], response.usage.completion_tokens
                )
        self.assertAlmostEqual(sum(e["cost"] for e in exchanges), self.agent.cost)
        self.assertEqual(
            sum(e["prompt_tokens"] for e in exchanges), self.agent.prompt_tokens
        )

    def test_seeded_game_with_discussion_finishes(self):
        """Verifies that five agents with mocked replies finish a seeded game with discussion and no faults."""
        reply = _reply(1, message="I am a liberal.", notes="Still watching.")
        agents = [
            LLMAgent(uid, MODEL, completion_kwargs=frozendict(mock_response=reply))
            for uid in UIDS
        ]
        runner = GameRunner(agents, seed=7, discussion_enabled=True)
        state = asyncio.run(runner.run())
        self.assertEqual(state.phase, GamePhase.GAME_OVER)
        self.assertEqual(runner.faults, ())
        for agent in agents:
            with self.subTest(uid=agent.uid):
                self.assertEqual(agent.notes, "Still watching.")


if __name__ == "__main__":
    unittest.main()
