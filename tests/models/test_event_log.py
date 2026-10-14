import unittest
from dataclasses import fields, replace

from frozendict import frozendict

from tests.scripted_game import play_first_legal_actions
from tyrant.models.claim import (
    ChancellorEnactClaim,
    InvestigationClaim,
    PeekClaim,
    PresidentEnactClaim,
)
from tyrant.models.enums import (
    DiscussionContext,
    GamePhase,
    Party,
    PolicyTile,
    PresidentialPower,
    Role,
    Vote,
    WinCondition,
)
from tyrant.models.event import (
    ClaimEvent,
    ElectionEvent,
    ExecutionEvent,
    GameOverEvent,
    InvestigationEvent,
    NominationEvent,
    PolicyEnactedEvent,
    SpecialElectionEvent,
    SpeechEvent,
    VetoEvent,
)
from tyrant.models.game_state import (
    GameState,
    _end_game,
    call_special_election,
    cast_vote,
    chancellor_enact,
    claim_enact,
    claim_investigation,
    claim_peek,
    create_game,
    execute_player,
    investigate_loyalty,
    nominate_chancellor,
    president_veto_response,
    scrub_state,
    speak,
)

UIDS = (1, 2, 3, 4, 5, 6, 7)


def _president(state: GameState) -> int:
    return state.players[state.president_index].uid


def _other(state: GameState, *excluded: int) -> int:
    return next(
        p.uid
        for p in state.players
        if p.uid != _president(state) and p.uid not in excluded
    )


def _vote_all(state: GameState, vote: Vote) -> GameState:
    for p in state.players:
        if p.is_alive:
            state = cast_vote(state, p.uid, vote)
    return state


def _enact_state(state: GameState, fascist_played: int = 0) -> GameState:
    return replace(
        state,
        phase=GamePhase.CHANCELLOR_ENACT,
        chancellor=_other(state),
        drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        board=replace(state.board, fascist_played=fascist_played),
    )


class TestEndGame(unittest.TestCase):
    def test_end_game_immutability(self):
        """Verifies that _end_game returns a new instance without mutating the input state."""
        state = create_game(UIDS, 42)
        new_state = _end_game(state, Party.LIBERAL, WinCondition.HITLER_EXECUTED)
        self.assertIsNot(state, new_state)
        self.assertEqual(state.events, ())
        for field in fields(new_state):
            with self.assertRaises(Exception):
                setattr(new_state, field.name, None)

    def test_end_game_records_result(self):
        """Verifies that _end_game sets the winner and appends a GameOverEvent."""
        state = _end_game(
            create_game(UIDS, 42), Party.FASCIST, WinCondition.HITLER_ELECTED
        )
        self.assertEqual(state.phase, GamePhase.GAME_OVER)
        self.assertEqual(state.winner, Party.FASCIST)
        self.assertEqual(
            state.events,
            (
                GameOverEvent(
                    winner=Party.FASCIST, condition=WinCondition.HITLER_ELECTED
                ),
            ),
        )


class TestEventLog(unittest.TestCase):
    def setUp(self):
        self.state = create_game(UIDS, 42)

    def test_create_game_has_no_events(self):
        """Verifies that a new game starts with an empty event log."""
        self.assertEqual(self.state.events, ())

    def test_nomination_records_event(self):
        """Verifies that nominating a chancellor records a NominationEvent."""
        target = _other(self.state)
        state = nominate_chancellor(self.state, target)
        self.assertEqual(
            state.events,
            (
                NominationEvent(
                    president_uid=_president(self.state), chancellor_uid=target
                ),
            ),
        )

    def test_passed_election_records_full_votes(self):
        """Verifies that a passed election records every vote and a JA result."""
        target = _other(self.state)
        state = _vote_all(nominate_chancellor(self.state, target), Vote.JA)
        election = state.events[-1]
        self.assertEqual(
            election,
            ElectionEvent(
                president_uid=_president(self.state),
                chancellor_uid=target,
                votes=frozendict({uid: Vote.JA for uid in UIDS}),
                result=Vote.JA,
            ),
        )

    def test_failed_election_records_nein_result(self):
        """Verifies that a failed election records a NEIN result."""
        state = _vote_all(
            nominate_chancellor(self.state, _other(self.state)), Vote.NEIN
        )
        election = state.events[-1]
        self.assertIsInstance(election, ElectionEvent)
        self.assertEqual(election.result, Vote.NEIN)
        self.assertEqual(len(election.votes), len(UIDS))

    def test_top_deck_after_failed_elections_records_event(self):
        """Verifies that a third failed election records a top-decked PolicyEnactedEvent."""
        state = self.state
        for _ in range(3):
            state = _vote_all(nominate_chancellor(state, _other(state)), Vote.NEIN)
        enacted = state.events[-1]
        self.assertIsInstance(enacted, PolicyEnactedEvent)
        self.assertTrue(enacted.top_deck)
        self.assertIsInstance(state.events[-2], ElectionEvent)

    def test_top_deck_win_records_game_over(self):
        """Verifies that a winning top-deck records the policy win condition last."""
        state = replace(
            self.state,
            board=replace(self.state.board, liberal_played=4, fascist_played=5),
        )
        for _ in range(3):
            state = _vote_all(nominate_chancellor(state, _other(state)), Vote.NEIN)
        enacted = state.events[-2]
        expected = {
            PolicyTile.LIBERAL: GameOverEvent(
                winner=Party.LIBERAL, condition=WinCondition.LIBERAL_POLICIES
            ),
            PolicyTile.FASCIST: GameOverEvent(
                winner=Party.FASCIST, condition=WinCondition.FASCIST_POLICIES
            ),
        }
        self.assertEqual(state.phase, GamePhase.GAME_OVER)
        self.assertIsInstance(enacted, PolicyEnactedEvent)
        self.assertTrue(enacted.top_deck)
        self.assertEqual(state.events[-1], expected[enacted.policy])

    def test_hitler_elected_records_election_then_game_over(self):
        """Verifies that electing Hitler records the election before the game result."""
        hitler = next(p.uid for p in self.state.players if p.role == Role.HITLER)
        state = replace(
            self.state,
            board=replace(self.state.board, fascist_played=3),
            president_index=next(
                i for i, p in enumerate(self.state.players) if p.uid != hitler
            ),
        )
        state = _vote_all(nominate_chancellor(state, hitler), Vote.JA)
        self.assertIsInstance(state.events[-2], ElectionEvent)
        self.assertEqual(
            state.events[-1],
            GameOverEvent(winner=Party.FASCIST, condition=WinCondition.HITLER_ELECTED),
        )

    def test_chancellor_enact_records_government(self):
        """Verifies that an enacted policy records its president and chancellor."""
        state = _enact_state(self.state)
        new_state = chancellor_enact(state, 1)
        self.assertEqual(
            new_state.events[-1],
            PolicyEnactedEvent(
                policy=PolicyTile.LIBERAL,
                president_uid=_president(state),
                chancellor_uid=state.chancellor,
            ),
        )
        self.assertFalse(new_state.events[-1].top_deck)

    def test_chancellor_enact_win_records_game_over(self):
        """Verifies that enacting the sixth fascist policy records a fascist policy win."""
        new_state = chancellor_enact(_enact_state(self.state, fascist_played=5), 0)
        self.assertIsInstance(new_state.events[-2], PolicyEnactedEvent)
        self.assertEqual(
            new_state.events[-1],
            GameOverEvent(
                winner=Party.FASCIST, condition=WinCondition.FASCIST_POLICIES
            ),
        )

    def test_denied_veto_records_event(self):
        """Verifies that a denied veto is recorded with approved set to False."""
        state = replace(
            _enact_state(self.state, fascist_played=5),
            phase=GamePhase.PRESIDENT_VETO_RESPONSE,
        )
        new_state = president_veto_response(state, False)
        self.assertEqual(
            new_state.events,
            (
                VetoEvent(
                    president_uid=_president(state),
                    chancellor_uid=state.chancellor,
                    approved=False,
                ),
            ),
        )

    def test_approved_veto_records_event(self):
        """Verifies that an approved veto is recorded with approved set to True."""
        state = replace(
            _enact_state(self.state, fascist_played=5),
            phase=GamePhase.PRESIDENT_VETO_RESPONSE,
        )
        new_state = president_veto_response(state, True)
        self.assertEqual(
            new_state.events,
            (
                VetoEvent(
                    president_uid=_president(state),
                    chancellor_uid=state.chancellor,
                    approved=True,
                ),
            ),
        )

    def test_approved_veto_top_deck_records_event(self):
        """Verifies that an approved veto that triggers a top-deck records both events."""
        state = replace(
            _enact_state(self.state, fascist_played=5),
            phase=GamePhase.PRESIDENT_VETO_RESPONSE,
            election_tracker=replace(self.state.election_tracker, failed_elections=2),
        )
        new_state = president_veto_response(state, True)
        self.assertIsInstance(new_state.events[0], VetoEvent)
        self.assertIsInstance(new_state.events[1], PolicyEnactedEvent)
        self.assertTrue(new_state.events[1].top_deck)

    def test_enact_claims_record_government(self):
        """Verifies that enact claims are linked to the government that made them."""
        state = chancellor_enact(_enact_state(self.state), 1)
        president, chancellor = _president(state), state.chancellor
        president_claim = PresidentEnactClaim(
            uid=president,
            policies=(PolicyTile.LIBERAL, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        chancellor_claim = ChancellorEnactClaim(
            uid=chancellor, policies=(PolicyTile.LIBERAL, PolicyTile.FASCIST)
        )
        state = claim_enact(claim_enact(state, president_claim), chancellor_claim)
        self.assertEqual(
            state.events[-2:],
            (
                ClaimEvent(
                    claim=president_claim,
                    president_uid=president,
                    chancellor_uid=chancellor,
                    target_uid=None,
                ),
                ClaimEvent(
                    claim=chancellor_claim,
                    president_uid=president,
                    chancellor_uid=chancellor,
                    target_uid=None,
                ),
            ),
        )

    def test_investigation_and_claim_record_target(self):
        """Verifies that an investigation and its claim both record the target."""
        state = replace(
            self.state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.INVESTIGATE_LOYALTY,
        )
        president, target = _president(state), _other(state)
        state = investigate_loyalty(state, target)
        claim = InvestigationClaim(uid=president, party=Party.LIBERAL)
        state = claim_investigation(state, claim)
        self.assertEqual(
            state.events,
            (
                InvestigationEvent(president_uid=president, target_uid=target),
                ClaimEvent(
                    claim=claim,
                    president_uid=president,
                    chancellor_uid=None,
                    target_uid=target,
                ),
            ),
        )

    def test_peek_claim_records_president(self):
        """Verifies that a peek claim is linked to the president who used the power."""
        state = replace(self.state, phase=GamePhase.CLAIM_POLICY_PEEK)
        claim = PeekClaim(uid=_president(state), policies=None)
        new_state = claim_peek(state, claim)
        self.assertEqual(
            new_state.events,
            (
                ClaimEvent(
                    claim=claim,
                    president_uid=_president(state),
                    chancellor_uid=None,
                    target_uid=None,
                ),
            ),
        )

    def test_special_election_records_event(self):
        """Verifies that calling a special election records the president and target."""
        state = replace(self.state, phase=GamePhase.PRESIDENTIAL_POWER)
        target = _other(state)
        new_state = call_special_election(state, target)
        self.assertEqual(
            new_state.events,
            (SpecialElectionEvent(president_uid=_president(state), target_uid=target),),
        )

    def test_execution_records_event(self):
        """Verifies that executing a player records the president and target."""
        hitler = next(p.uid for p in self.state.players if p.role == Role.HITLER)
        state = replace(self.state, phase=GamePhase.PRESIDENTIAL_POWER)
        target = _other(state, hitler)
        new_state = execute_player(state, target)
        self.assertEqual(
            new_state.events,
            (ExecutionEvent(president_uid=_president(state), target_uid=target),),
        )

    def test_hitler_execution_records_game_over(self):
        """Verifies that executing Hitler records the execution and a liberal win."""
        hitler = next(p.uid for p in self.state.players if p.role == Role.HITLER)
        state = replace(
            self.state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            president_index=next(
                i for i, p in enumerate(self.state.players) if p.uid != hitler
            ),
        )
        new_state = execute_player(state, hitler)
        self.assertEqual(
            new_state.events,
            (
                ExecutionEvent(president_uid=_president(state), target_uid=hitler),
                GameOverEvent(
                    winner=Party.LIBERAL, condition=WinCondition.HITLER_EXECUTED
                ),
            ),
        )

    def test_speak_records_speech_event(self):
        """Verifies that speaking and passing both record a SpeechEvent."""
        state = nominate_chancellor(
            replace(self.state, discussion_enabled=True), _other(self.state)
        )
        first, second = state.discussion.speaker_order[:2]
        state = speak(speak(state, first, "Hello."), second, None)
        self.assertEqual(
            state.events[-2:],
            (
                SpeechEvent(
                    uid=first, text="Hello.", context=DiscussionContext.AFTER_NOMINATION
                ),
                SpeechEvent(
                    uid=second, text=None, context=DiscussionContext.AFTER_NOMINATION
                ),
            ),
        )

    def test_scripted_game_ends_with_single_result(self):
        """Verifies that a full game records exactly one GameOverEvent as its final event."""
        final = play_first_legal_actions(create_game(UIDS, 42))[-1]
        results = [e for e in final.events if isinstance(e, GameOverEvent)]
        self.assertEqual(len(results), 1)
        self.assertEqual(final.events[-1].winner, final.winner)

    def test_events_are_append_only(self):
        """Verifies that every transition in a full game only appends to the event log."""
        states = play_first_legal_actions(
            create_game(UIDS, 42, discussion_enabled=True)
        )
        for before, after in zip(states, states[1:]):
            self.assertEqual(after.events[: len(before.events)], before.events)

    def test_scrub_state_passes_events_through(self):
        """Verifies that every viewer sees the full event log at every point in a game."""
        states = play_first_legal_actions(
            create_game(UIDS, 42, discussion_enabled=True)
        )
        for state in states:
            for uid in UIDS:
                self.assertEqual(scrub_state(state, uid).events, state.events)


if __name__ == "__main__":
    unittest.main()
