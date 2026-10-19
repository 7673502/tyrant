import asyncio
import unittest
from dataclasses import replace

from frozendict import frozendict

from tests.scripted_game import play_first_legal_actions
from tyrant.agents.random_agent import RandomAgent
from tyrant.engine.game_runner import GameRunner, _is_offered
from tyrant.engine.replay import replay_dict
from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.exceptions import AgentError, InvalidMoveError, TyrantError
from tyrant.models.action import (
    Action,
    ChancellorEnactAction,
    ClaimChancellorEnactAction,
    ClaimInvestigationAction,
    ClaimPolicyPeekAction,
    ClaimPresidentEnactAction,
    NominateAction,
    PassAction,
    SpeakAction,
    VoteAction,
)
from tyrant.models.agent_fault import AgentFault
from tyrant.models.enums import (
    HIDDEN,
    DiscussionContext,
    GamePhase,
    Party,
    PolicyTile,
    Vote,
)
from tyrant.models.event import ClaimEvent, SpeechEvent
from tyrant.models.game_state import (
    DEFAULT_DISCUSSION_CONTEXTS,
    GameState,
    create_game,
)
from tyrant.models.replay import Replay, record_step


class StubAgent:
    def __init__(self, uid: int, actions_to_play: list[Action]):
        self._uid = uid
        self._actions_to_play = actions_to_play

    @property
    def uid(self) -> int:
        return self._uid

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        return self._actions_to_play.pop(0)


class CapturingAgent:
    def __init__(self, uid: int):
        self._uid = uid
        self.captured_state: GameState | None = None

    @property
    def uid(self) -> int:
        return self._uid

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        self.captured_state = state
        return valid_actions[0]


class RaisingAgent:
    def __init__(self, uid: int):
        self.uid = uid
        self.calls = 0

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        self.calls += 1
        raise AgentError("Agent failure")


class RejectingAgent:
    def __init__(self, uid: int):
        self.uid = uid

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        raise InvalidMoveError("Reply has no JSON object", reply="Not JSON.")


class CrashingAgent:
    def __init__(self, uid: int):
        self.uid = uid
        self.calls = 0

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        self.calls += 1
        raise KeyError("missing")


class ProfiledAgent:
    def __init__(self, uid: int):
        self.uid = uid
        self.profile = frozendict(model="scripted")

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        return valid_actions[0]


class SlowAgent:
    def __init__(self, uid: int):
        self.uid = uid
        self.calls = 0

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        self.calls += 1
        await asyncio.sleep(1)
        return valid_actions[0]


class TestGameRunnerInitialization(unittest.TestCase):
    def test_init_with_initial_state(self):
        """Verifies that GameRunner initializes correctly when provided an explicit GameState."""
        state = create_game((1, 2, 3, 4, 5), 42)
        runner = GameRunner(agents=[], initial_state=state)
        self.assertEqual(runner.state, state)

    def test_init_without_initial_state(self):
        """Verifies that GameRunner generates a new GameState when none is provided."""
        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42)
        self.assertIsInstance(runner.state, GameState)
        self.assertEqual(len(runner.state.players), 5)

    def test_init_custom_configuration(self):
        """Verifies that GameRunner passes fixed_roles and shuffle_players to create_game."""
        from tyrant.models.enums import Role

        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        fixed_roles = {
            1: Role.HITLER,
            2: Role.FASCIST,
            3: Role.LIBERAL,
            4: Role.LIBERAL,
            5: Role.LIBERAL,
        }
        runner = GameRunner(
            agents=agents, seed=42, roles=fixed_roles, shuffle_players=False
        )
        self.assertEqual(tuple(p.uid for p in runner.state.players), (1, 2, 3, 4, 5))
        for p in runner.state.players:
            self.assertEqual(p.role, fixed_roles[p.uid])


class TestGameRunnerDiscussion(unittest.IsolatedAsyncioTestCase):
    def test_init_discussion_disabled_by_default(self):
        """Verifies that GameRunner leaves discussion disabled unless asked."""
        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42)
        self.assertFalse(runner.state.discussion_enabled)

    def test_init_forwards_discussion_enabled(self):
        """Verifies that GameRunner passes discussion_enabled to create_game."""
        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42, discussion_enabled=True)
        self.assertTrue(runner.state.discussion_enabled)

    def test_init_discussion_rounds_default(self):
        """Verifies that GameRunner defaults to two discussion rounds."""
        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42)
        self.assertEqual(runner.state.discussion_rounds, 2)

    def test_init_discussion_contexts_default(self):
        """Verifies that GameRunner defaults to every discussion context except after a failed election."""
        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42)
        self.assertEqual(runner.state.discussion_contexts, DEFAULT_DISCUSSION_CONTEXTS)

    def test_init_forwards_discussion_contexts(self):
        """Verifies that GameRunner passes discussion_contexts to create_game."""
        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        contexts = frozenset({DiscussionContext.AFTER_NOMINATION})
        runner = GameRunner(agents=agents, seed=42, discussion_contexts=contexts)
        self.assertEqual(runner.state.discussion_contexts, contexts)

    def test_init_forwards_discussion_rounds(self):
        """Verifies that GameRunner passes discussion_rounds to create_game."""
        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42, discussion_rounds=5)
        self.assertEqual(runner.state.discussion_rounds, 5)

    async def test_run_completes_game_with_discussion(self):
        """Verifies that random agents finish a game with discussion enabled and leave a transcript."""
        agents = [RandomAgent(uid=i) for i in range(1, 8)]
        runner = GameRunner(agents=agents, seed=42, discussion_enabled=True)
        final_state = await runner.run()
        self.assertEqual(final_state.phase, GamePhase.GAME_OVER)
        self.assertTrue(any(isinstance(e, SpeechEvent) for e in final_state.events))


class TestGameRunnerQueryAgent(unittest.IsolatedAsyncioTestCase):
    async def test_query_agent_scrubs_state(self):
        """Verifies that the GameState passed to the agent is properly scrubbed for hidden information."""
        state = create_game((1, 2, 3, 4, 5), 42)
        president_uid = state.players[state.president_index].uid
        agent = CapturingAgent(uid=president_uid)
        runner = GameRunner(agents=[agent], initial_state=state)

        await runner._query_agent(agent, get_legal_actions(state, president_uid), 0)

        self.assertIsNotNone(agent.captured_state)
        self.assertEqual(agent.captured_state.rng_state, HIDDEN)

    async def test_attempt_rejects_unoffered_action(self):
        """Verifies that an action outside valid_actions raises an InvalidMoveError."""
        state = create_game((1, 2, 3, 4, 5), 42)
        president_uid = state.players[state.president_index].uid
        bad_action = NominateAction(description="Nominate", target_uid=president_uid)
        agent = StubAgent(uid=president_uid, actions_to_play=[bad_action])
        runner = GameRunner(agents=[agent], initial_state=state)

        with self.assertRaises(InvalidMoveError):
            await runner._attempt(agent, state, get_legal_actions(state, president_uid))


class TestGameRunnerResilience(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = create_game((1, 2, 3, 4, 5), 42)
        self.president_uid = self.state.players[self.state.president_index].uid
        self.valid_actions = get_legal_actions(self.state, self.president_uid)
        self.bad_action = NominateAction(
            description="Nominate", target_uid=self.president_uid
        )

    def test_init_resilience_defaults(self):
        """Verifies that GameRunner defaults to two retries and a 120-second timeout."""
        runner = GameRunner(agents=[], initial_state=self.state)
        self.assertEqual(runner.max_retries, 2)
        self.assertEqual(runner.timeout, 120.0)

    async def test_query_agent_well_behaved_called_once(self):
        """Verifies that a well-behaved agent is queried once and its action is used."""
        good_action = self.valid_actions[1]
        agent = StubAgent(uid=self.president_uid, actions_to_play=[good_action])
        runner = GameRunner(agents=[agent], initial_state=self.state)

        _, action = await runner._query_agent(agent, self.valid_actions, 0)

        self.assertEqual(action, good_action)
        self.assertEqual(agent._actions_to_play, [])

    async def test_query_agent_keeps_speak_message(self):
        """Verifies that the agent's SpeakAction message survives validation."""
        speak_action = SpeakAction(description="Speak", message="Trust me.")
        agent = StubAgent(uid=self.president_uid, actions_to_play=[speak_action])
        runner = GameRunner(agents=[agent], initial_state=self.state)

        _, action = await runner._query_agent(
            agent, (SpeakAction(description="Speak"), PassAction(description="Pass")), 0
        )

        self.assertEqual(action, speak_action)

    async def test_query_agent_retries_after_illegal_action(self):
        """Verifies that an illegal action is retried and a later legal action is used."""
        good_action = self.valid_actions[0]
        agent = StubAgent(
            uid=self.president_uid, actions_to_play=[self.bad_action, good_action]
        )
        runner = GameRunner(agents=[agent], initial_state=self.state)

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            _, action = await runner._query_agent(agent, self.valid_actions, 0)

        self.assertEqual(action, good_action)

    async def test_query_agent_falls_back_after_illegal_actions(self):
        """Verifies that repeated illegal actions fall back to a legal action after all retries."""
        agent = StubAgent(uid=self.president_uid, actions_to_play=[self.bad_action] * 3)
        runner = GameRunner(agents=[agent], initial_state=self.state)

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            _, action = await runner._query_agent(agent, self.valid_actions, 0)

        self.assertIn(action, self.valid_actions)
        self.assertEqual(agent._actions_to_play, [])

    async def test_query_agent_falls_back_after_exceptions(self):
        """Verifies that an agent that always raises is retried and then falls back."""
        agent = RaisingAgent(uid=self.president_uid)
        runner = GameRunner(agents=[agent], initial_state=self.state, max_retries=4)

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            _, action = await runner._query_agent(agent, self.valid_actions, 0)

        self.assertIn(action, self.valid_actions)
        self.assertEqual(agent.calls, 5)

    async def test_query_agent_unexpected_exception_propagates(self):
        """Verifies that an exception other than the expected agent failures is raised without retries or faults."""
        agent = CrashingAgent(uid=self.president_uid)
        runner = GameRunner(agents=[agent], initial_state=self.state)

        with self.assertRaises(KeyError):
            await runner._query_agent(agent, self.valid_actions, 0)

        self.assertEqual(agent.calls, 1)
        self.assertEqual(runner.faults, ())

    async def test_run_crashes_on_unexpected_exception(self):
        """Verifies that a game stops with the agent's exception when it raises an unexpected error."""
        agents = [CrashingAgent(uid=i) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42)

        with self.assertRaises(KeyError):
            await runner.run()

    async def test_query_agent_falls_back_after_timeouts(self):
        """Verifies that an agent that exceeds the timeout is retried and then falls back."""
        agent = SlowAgent(uid=self.president_uid)
        runner = GameRunner(
            agents=[agent], initial_state=self.state, max_retries=1, timeout=0.01
        )

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            _, action = await runner._query_agent(agent, self.valid_actions, 0)

        self.assertIn(action, self.valid_actions)
        self.assertEqual(agent.calls, 2)

    async def test_query_agent_well_behaved_records_no_faults(self):
        """Verifies that a well-behaved agent leaves the fault record empty."""
        agent = StubAgent(
            uid=self.president_uid, actions_to_play=[self.valid_actions[0]]
        )
        runner = GameRunner(agents=[agent], initial_state=self.state)

        await runner._query_agent(agent, self.valid_actions, 0)

        self.assertEqual(runner.faults, ())

    async def test_query_agent_records_faults(self):
        """Verifies that each failed attempt is recorded and only the last is marked as a fallback."""
        agent = StubAgent(uid=self.president_uid, actions_to_play=[self.bad_action] * 3)
        runner = GameRunner(agents=[agent], initial_state=self.state)

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING") as logs:
            await runner._query_agent(agent, self.valid_actions, 0)

        self.assertEqual(len(runner.faults), 3)
        self.assertEqual(len(logs.records), 3)
        self.assertEqual(
            tuple(f.fell_back for f in runner.faults), (False, False, True)
        )
        for fault in runner.faults:
            self.assertIsInstance(fault, AgentFault)
            self.assertEqual(fault.uid, self.president_uid)
            self.assertEqual(fault.phase, GamePhase.NOMINATION)
            self.assertIn("InvalidMoveError", fault.reason)

    async def test_query_agent_records_recovered_fault(self):
        """Verifies that a fault followed by a legal action is recorded without a fallback."""
        agent = StubAgent(
            uid=self.president_uid,
            actions_to_play=[self.bad_action, self.valid_actions[0]],
        )
        runner = GameRunner(agents=[agent], initial_state=self.state)

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            await runner._query_agent(agent, self.valid_actions, 0)

        self.assertEqual(len(runner.faults), 1)
        self.assertFalse(runner.faults[0].fell_back)

    async def test_query_agent_records_timeout_fault(self):
        """Verifies that a timeout is recorded as a TimeoutError fault."""
        agent = SlowAgent(uid=self.president_uid)
        runner = GameRunner(
            agents=[agent], initial_state=self.state, max_retries=0, timeout=0.01
        )

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            await runner._query_agent(agent, self.valid_actions, 0)

        self.assertIn("TimeoutError", runner.faults[0].reason)
        self.assertTrue(runner.faults[0].fell_back)

    async def test_query_agent_zero_retries(self):
        """Verifies that max_retries of zero falls back after a single failed attempt."""
        agent = RaisingAgent(uid=self.president_uid)
        runner = GameRunner(agents=[agent], initial_state=self.state, max_retries=0)

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            await runner._query_agent(agent, self.valid_actions, 0)

        self.assertEqual(agent.calls, 1)

    async def test_query_agent_discussion_fallback_passes(self):
        """Verifies that a failing agent in a discussion falls back to the offered pass."""
        agent = RaisingAgent(uid=self.president_uid)
        runner = GameRunner(agents=[agent], initial_state=self.state, max_retries=0)
        options = (SpeakAction(description="Speak"), PassAction(description="Pass"))

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            picks = [
                (await runner._query_agent(agent, options, 0))[1] for _ in range(5)
            ]

        self.assertEqual(picks, [options[1]] * 5)

    async def test_run_failing_agent_only_passes_in_discussion(self):
        """Verifies that every discussion turn a failing agent falls back on is a pass."""
        agents = [RaisingAgent(uid=1)] + [RandomAgent(uid=i) for i in range(2, 6)]
        runner = GameRunner(
            agents=agents, seed=42, max_retries=0, discussion_enabled=True
        )

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            await runner.run()

        turns = [
            step.action
            for step in runner.replay.steps
            if step.uid == 1 and isinstance(step.action, (SpeakAction, PassAction))
        ]
        self.assertTrue(turns)
        for action in turns:
            self.assertIsInstance(action, PassAction)

    async def test_query_agent_claim_fallback_declines(self):
        """Verifies that a failing agent asked for any claim falls back to declining it."""
        claims_state = next(
            s
            for s in play_first_legal_actions(self.state)
            if s.phase == GamePhase.CLAIM_POLICIES
        )
        president_uid = claims_state.players[claims_state.president_index].uid
        menus = (
            get_legal_actions(claims_state, president_uid),
            get_legal_actions(claims_state, claims_state.chancellor),
            get_legal_actions(
                replace(
                    self.state,
                    phase=GamePhase.CLAIM_POLICY_PEEK,
                    drawn_policies=(PolicyTile.FASCIST,) * 3,
                ),
                self.president_uid,
            ),
            get_legal_actions(
                replace(
                    self.state,
                    phase=GamePhase.CLAIM_INVESTIGATION,
                    current_investigation_result=Party.LIBERAL,
                ),
                self.president_uid,
            ),
        )
        expected_types = (
            ClaimPresidentEnactAction,
            ClaimChancellorEnactAction,
            ClaimPolicyPeekAction,
            ClaimInvestigationAction,
        )
        agent = RaisingAgent(uid=self.president_uid)
        runner = GameRunner(agents=[agent], initial_state=self.state, max_retries=0)

        for options, expected_type in zip(menus, expected_types):
            with self.subTest(claim=expected_type.__name__):
                with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
                    _, action = await runner._query_agent(agent, options, 0)
                self.assertIs(action, options[-1])
                self.assertIsInstance(action, expected_type)

    async def test_query_agent_seeded_fallback_is_deterministic(self):
        """Verifies that fallback choices are reproducible for the same seed."""
        chosen = []
        for _ in range(2):
            agent = RaisingAgent(uid=self.president_uid)
            runner = GameRunner(agents=[agent], initial_state=self.state, seed=7)
            with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
                picks = [
                    (await runner._query_agent(agent, self.valid_actions, 0))[1]
                    for _ in range(5)
                ]
            chosen.append(picks)

        self.assertEqual(chosen[0], chosen[1])

    async def test_run_completes_game_with_failing_agents(self):
        """Verifies that a game finishes when every agent always raises."""
        agents = [RaisingAgent(uid=i) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42, max_retries=0)

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            final_state = await runner.run()

        self.assertEqual(final_state.phase, GamePhase.GAME_OVER)


class TestIsOffered(unittest.TestCase):
    def test_is_offered_matching_action(self):
        """Verifies that an action equal to an offered action is accepted."""
        offered = (VoteAction(description="Vote JA", vote=Vote.JA),)
        self.assertTrue(
            _is_offered(VoteAction(description="Vote JA", vote=Vote.JA), offered)
        )

    def test_is_offered_ignores_description(self):
        """Verifies that a different description does not prevent a match."""
        offered = (VoteAction(description="Vote JA", vote=Vote.JA),)
        self.assertTrue(
            _is_offered(VoteAction(description="Other", vote=Vote.JA), offered)
        )

    def test_is_offered_field_mismatch(self):
        """Verifies that an action with different identifying fields is rejected."""
        offered = (VoteAction(description="Vote JA", vote=Vote.JA),)
        self.assertFalse(
            _is_offered(VoteAction(description="Vote JA", vote=Vote.NEIN), offered)
        )

    def test_is_offered_type_mismatch(self):
        """Verifies that an action of a type that was not offered is rejected."""
        offered = (SpeakAction(description="Speak"),)
        self.assertFalse(_is_offered(PassAction(description="Speak"), offered))

    def test_is_offered_base_action_rejected(self):
        """Verifies that a bare Action is not accepted in place of a subclass."""
        offered = (PassAction(description="Pass"),)
        self.assertFalse(_is_offered(Action(description="Pass"), offered))

    def test_is_offered_speak_with_message(self):
        """Verifies that a SpeakAction with an agent-filled message is accepted."""
        offered = (SpeakAction(description="Speak"),)
        self.assertTrue(
            _is_offered(SpeakAction(description="Speak", message="Hello."), offered)
        )


class TestGameRunnerIteration(unittest.IsolatedAsyncioTestCase):
    async def test_run_iteration_applies_action(self):
        """Verifies that a single iteration queries agents and updates the internal state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        president_uid = state.players[state.president_index].uid
        target_uid = state.players[(state.president_index + 1) % 5].uid

        action = NominateAction(description="Nominate", target_uid=target_uid)
        agents = [
            StubAgent(
                uid=p.uid, actions_to_play=[action] if p.uid == president_uid else []
            )
            for p in state.players
        ]
        runner = GameRunner(agents=agents, initial_state=state)

        new_state = await runner._run_iteration()

        self.assertEqual(new_state.phase, GamePhase.VOTING)
        self.assertEqual(new_state.chancellor, target_uid)

    async def test_run_iteration_claims_are_simultaneous(self):
        """Verifies that the president and chancellor are both asked for claims before either claim is applied."""
        state = next(
            s
            for s in play_first_legal_actions(create_game((1, 2, 3, 4, 5), 42))
            if s.phase == GamePhase.CLAIM_POLICIES
        )
        president_uid = state.players[state.president_index].uid
        agents = [CapturingAgent(uid=p.uid) for p in state.players]
        runner = GameRunner(agents=agents, initial_state=state)

        await runner._run_iteration()

        claims_before = sum(isinstance(e, ClaimEvent) for e in state.events)
        for agent in agents:
            if agent.uid in (president_uid, state.chancellor):
                captured = agent.captured_state
                self.assertEqual(captured.phase, GamePhase.CLAIM_POLICIES)
                self.assertEqual(
                    sum(isinstance(e, ClaimEvent) for e in captured.events),
                    claims_before,
                )
                self.assertEqual(captured.claims, state.claims)
            else:
                self.assertIsNone(agent.captured_state)
        self.assertEqual(
            sum(isinstance(e, ClaimEvent) for e in runner.state.events),
            claims_before + 2,
        )

    async def test_run_iteration_stalemate(self):
        """Verifies that a TyrantError is raised if no players have legal actions."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.SETUP)
        agents = [StubAgent(uid=p.uid, actions_to_play=[]) for p in state.players]
        runner = GameRunner(agents=agents, initial_state=state)

        with self.assertRaises(TyrantError):
            await runner._run_iteration()


class TestGameRunnerRun(unittest.IsolatedAsyncioTestCase):
    async def test_run_completes_game(self):
        """Verifies that run loops iterations until the game phase is GAME_OVER."""
        state = create_game((1, 2, 3, 4, 5), 42)

        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            drawn_policies=(state.deck.draw_pile[0], state.deck.draw_pile[1]),
            board=replace(state.board, fascist_played=5),
            chancellor=state.players[1].uid,
        )

        chancellor_uid = state.players[1].uid
        action = ChancellorEnactAction(description="Enact", target_index=0)
        agents = [
            StubAgent(
                uid=p.uid, actions_to_play=[action] if p.uid == chancellor_uid else []
            )
            for p in state.players
        ]

        runner = GameRunner(agents=agents, initial_state=state)
        final_state = await runner.run()

        self.assertEqual(final_state.phase, GamePhase.GAME_OVER)


def _replayed(replay: Replay) -> GameState:
    state = replay.initial_state
    for step in replay.steps:
        state = apply_action(state, step.action, step.uid)
    return state


class TestGameRunnerReplay(unittest.IsolatedAsyncioTestCase):
    def test_init_replay_starts_from_initial_state(self):
        """Verifies that the replay starts empty from the runner's initial state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        agents = [StubAgent(uid=i, actions_to_play=[]) for i in range(1, 6)]
        runner = GameRunner(agents=agents, initial_state=state)
        self.assertIs(runner.replay.initial_state, state)
        self.assertEqual(runner.replay.steps, ())

    async def test_run_replay_reproduces_final_state(self):
        """Verifies that replaying the recorded steps reproduces the final state with discussion."""
        agents = [RandomAgent(uid=i) for i in range(1, 8)]
        runner = GameRunner(agents=agents, seed=42, discussion_enabled=True)
        final_state = await runner.run()
        self.assertEqual(_replayed(runner.replay), final_state)

    async def test_run_replay_records_fallback_actions(self):
        """Verifies that replaying the recorded steps reproduces the final state after fallbacks."""
        agents = [RaisingAgent(uid=i) for i in range(1, 6)]
        runner = GameRunner(agents=agents, seed=42, max_retries=0)

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            final_state = await runner.run()

        self.assertEqual(_replayed(runner.replay), final_state)

    async def test_run_replay_marks_fallback_steps(self):
        """Verifies that only steps played on a failing agent's behalf are marked as fallbacks."""
        agents = [RaisingAgent(uid=1)] + [RandomAgent(uid=i) for i in range(2, 6)]
        runner = GameRunner(agents=agents, seed=42, max_retries=0)

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            await runner.run()

        self.assertTrue(any(step.uid == 1 for step in runner.replay.steps))
        for step in runner.replay.steps:
            self.assertEqual(step.fallback, step.uid == 1)

    async def test_run_iteration_recovered_fault_not_fallback(self):
        """Verifies that a step the agent got right on a retry is not marked as a fallback."""
        state = create_game((1, 2, 3, 4, 5), 42)
        president_uid = state.players[state.president_index].uid
        bad_action = NominateAction(description="Nominate", target_uid=president_uid)
        good_action = get_legal_actions(state, president_uid)[0]
        agents = [
            StubAgent(
                uid=p.uid,
                actions_to_play=[bad_action, good_action]
                if p.uid == president_uid
                else [],
            )
            for p in state.players
        ]
        runner = GameRunner(agents=agents, initial_state=state)

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            await runner._run_iteration()

        self.assertEqual(len(runner.faults), 1)
        self.assertFalse(runner.replay.steps[0].fallback)

    async def test_run_iteration_records_faults_in_replay(self):
        """Verifies that faults are stored in the replay with the index of the step the agent's action became."""
        state = create_game((1, 2, 3, 4, 5), 42)
        president_uid = state.players[state.president_index].uid
        bad_action = NominateAction(description="Nominate", target_uid=president_uid)
        good_action = get_legal_actions(state, president_uid)[0]
        agents = [
            StubAgent(
                uid=p.uid,
                actions_to_play=[bad_action, good_action]
                if p.uid == president_uid
                else [],
            )
            for p in state.players
        ]
        runner = GameRunner(agents=agents, initial_state=state)

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            await runner._run_iteration()

        self.assertEqual(runner.replay.faults, runner.faults)
        self.assertEqual(runner.faults[0].step, 0)
        self.assertIsNone(runner.faults[0].reply)

    async def test_run_iteration_fault_step_matches_agent_step(self):
        """Verifies that during simultaneous voting each fault points at the step of the agent that failed."""
        state = create_game((1, 2, 3, 4, 5), 42)
        president_uid = state.players[state.president_index].uid
        state = apply_action(
            state, get_legal_actions(state, president_uid)[0], president_uid
        )
        failing_uid = state.players[2].uid
        agents = [
            RaisingAgent(uid=p.uid) if p.uid == failing_uid else RandomAgent(uid=p.uid)
            for p in state.players
        ]
        runner = GameRunner(agents=agents, initial_state=state, max_retries=0)
        runner.replay = record_step(
            runner.replay,
            president_uid,
            NominateAction(description="Nominate", target_uid=state.chancellor),
        )

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            await runner._run_iteration()

        fault = runner.replay.faults[0]
        self.assertEqual(runner.replay.steps[fault.step].uid, failing_uid)
        self.assertTrue(runner.replay.steps[fault.step].fallback)

    def test_init_replay_records_agent_profiles(self):
        """Verifies that the replay records each agent's class name and profile."""
        agents = [ProfiledAgent(uid=1)] + [RandomAgent(uid=i) for i in range(2, 6)]
        runner = GameRunner(agents=agents, seed=42)
        self.assertEqual(
            runner.replay.agents[1], frozendict(type="ProfiledAgent", model="scripted")
        )
        self.assertEqual(runner.replay.agents[2], frozendict(type="RandomAgent"))

    async def test_run_sends_live_updates(self):
        """Verifies that the live updates rebuild the same replay as replay_dict."""
        messages = []
        agents = [RaisingAgent(uid=1)] + [RandomAgent(uid=i) for i in range(2, 6)]
        runner = GameRunner(
            agents=agents, seed=42, max_retries=0, on_update=messages.append
        )

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            await runner.run()

        view = replay_dict(runner.replay)
        self.assertEqual(messages[0]["type"], "start")
        self.assertEqual(
            messages[0]["replay"], view | {"steps": [], "faults": [], "result": None}
        )
        self.assertEqual(
            [m["step"] for m in messages if m["type"] == "step"], view["steps"]
        )
        self.assertEqual(
            [m["fault"] for m in messages if m["type"] == "fault"], view["faults"]
        )
        self.assertNotEqual(view["faults"], [])
        self.assertEqual(messages[-1], {"type": "end", "result": view["result"]})

    async def test_run_fault_update_precedes_its_step(self):
        """Verifies that a fault is sent before the step it points at."""
        messages = []
        agents = [RaisingAgent(uid=1)] + [RandomAgent(uid=i) for i in range(2, 6)]
        runner = GameRunner(
            agents=agents, seed=42, max_retries=0, on_update=messages.append
        )

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            await runner.run()

        sent_steps = 0
        for message in messages:
            if message["type"] == "step":
                sent_steps += 1
            elif message["type"] == "fault":
                self.assertGreaterEqual(message["fault"]["step"], sent_steps)

    async def test_query_agent_records_rejected_reply(self):
        """Verifies that a fault keeps the raw reply carried by an InvalidMoveError."""
        state = create_game((1, 2, 3, 4, 5), 42)
        president_uid = state.players[state.president_index].uid
        agent = RejectingAgent(uid=president_uid)
        runner = GameRunner(agents=[agent], initial_state=state, max_retries=0)

        with self.assertLogs("tyrant.engine.game_runner", level="WARNING"):
            await runner._query_agent(agent, get_legal_actions(state, president_uid), 4)

        self.assertEqual(runner.faults[0].reply, "Not JSON.")
        self.assertEqual(runner.faults[0].step, 4)


if __name__ == "__main__":
    unittest.main()
