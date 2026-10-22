import unittest
from collections import Counter
from collections.abc import Iterator
from dataclasses import replace
from random import Random

from frozendict import frozendict

from tyrant.agents.ismcts.beliefs import role_assignments
from tyrant.agents.ismcts.determinize import determinize
from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.models.action import (
    ChancellorEnactAction,
    NominateAction,
    PresidentDiscardAction,
    VoteAction,
)
from tyrant.models.claim import PeekClaim
from tyrant.models.deck import NUM_FASCIST_POLICIES, NUM_LIBERAL_POLICIES
from tyrant.models.enums import HIDDEN, GamePhase, PolicyTile, Vote
from tyrant.models.event import ClaimEvent
from tyrant.models.game_state import GameState, create_game, scrub_state


def _random_states(player_count: int, seed: int) -> Iterator[GameState]:
    """Yields every state of a game played with random legal actions, up to but not including the end."""
    rng = Random(seed)
    state = create_game(tuple(range(player_count)), seed=seed)
    while state.phase != GamePhase.GAME_OVER:
        yield state
        uid, actions = next(
            (p.uid, get_legal_actions(state, p.uid))
            for p in state.players
            if get_legal_actions(state, p.uid)
        )
        state = apply_action(state, rng.choice(actions), uid)


def _play_out(state: GameState, rng: Random) -> GameState:
    """Plays random legal actions until the game ends."""
    while state.phase != GamePhase.GAME_OVER:
        uid, actions = next(
            (p.uid, get_legal_actions(state, p.uid))
            for p in state.players
            if get_legal_actions(state, p.uid)
        )
        state = apply_action(state, rng.choice(actions), uid)
    return state


def _determinize_for(state: GameState, viewer_uid: int, rng: Random) -> GameState:
    """Scrubs the state for the viewer and determinizes it with a random fitting deal."""
    scrubbed = scrub_state(state, viewer_uid)
    roles = rng.choice(role_assignments(scrubbed, viewer_uid))
    return determinize(scrubbed, viewer_uid, roles, rng)


def _tiles(state: GameState) -> Counter:
    """Counts every policy on the board, in the piles and in the government's hand."""
    hand = () if state.phase == GamePhase.CLAIM_POLICY_PEEK else state.drawn_policies
    return Counter(state.deck.draw_pile + state.deck.discard_pile + hand) + Counter(
        {
            PolicyTile.LIBERAL: state.board.liberal_played,
            PolicyTile.FASCIST: state.board.fascist_played,
        }
    )


class TestDeterminize(unittest.TestCase):
    def test_determinize_immutability(self):
        """Verifies that determinize returns a new state without mutating the scrubbed state."""
        state = create_game((0, 1, 2, 3, 4), seed=3)
        scrubbed = scrub_state(state, 0)
        before = replace(scrubbed)
        roles = role_assignments(scrubbed, 0)[0]
        result = determinize(scrubbed, 0, roles, Random(0))
        self.assertIsNot(result, scrubbed)
        self.assertEqual(scrubbed, before)

    def test_determinize_fuzz(self):
        """Verifies that determinized states of random games are complete, consistent and playable."""
        rng = Random(0)
        for player_count in range(5, 11):
            for seed in range(3):
                for step, state in enumerate(_random_states(player_count, seed)):
                    viewer_uid = rng.randrange(player_count)
                    with self.subTest(players=player_count, seed=seed, step=step):
                        scrubbed = scrub_state(state, viewer_uid)
                        deals = role_assignments(scrubbed, viewer_uid)
                        true_roles = frozendict({p.uid: p.role for p in state.players})
                        self.assertIn(true_roles, deals)
                        result = determinize(
                            scrubbed, viewer_uid, rng.choice(deals), rng
                        )
                        self.assertEqual(
                            _tiles(result),
                            Counter(
                                {
                                    PolicyTile.LIBERAL: NUM_LIBERAL_POLICIES,
                                    PolicyTile.FASCIST: NUM_FASCIST_POLICIES,
                                }
                            ),
                        )
                        self.assertEqual(
                            len(result.deck.draw_pile), len(state.deck.draw_pile)
                        )
                        self.assertEqual(
                            len(result.deck.discard_pile),
                            len(state.deck.discard_pile),
                        )
                        self.assertEqual(
                            len(result.drawn_policies), len(state.drawn_policies)
                        )
                        if scrubbed.drawn_policies:
                            self.assertEqual(
                                result.drawn_policies, scrubbed.drawn_policies
                            )
                        for seen, dealt in zip(scrubbed.players, result.players):
                            if seen.role is not HIDDEN:
                                self.assertEqual(dealt.role, seen.role)
                            if seen.party is not HIDDEN:
                                self.assertEqual(dealt.party, seen.party)
                        if step % 4 == 0:
                            final = _play_out(result, rng)
                            self.assertEqual(final.phase, GamePhase.GAME_OVER)

    def test_determinize_peek(self):
        """Verifies that the peeking president's determinizations keep the peeked policies on top of the draw pile."""
        rng = Random(0)
        checked = 0
        for seed in range(40):
            for state in _random_states(5, seed):
                peeking = state.phase == GamePhase.CLAIM_POLICY_PEEK
                claimed = (
                    state.phase == GamePhase.NOMINATION
                    and state.events
                    and isinstance(state.events[-1], ClaimEvent)
                    and isinstance(state.events[-1].claim, PeekClaim)
                )
                if not (peeking or claimed):
                    continue
                president_uid = (
                    state.players[state.president_index].uid
                    if peeking
                    else state.events[-1].president_uid
                )
                for _ in range(5):
                    result = _determinize_for(state, president_uid, rng)
                    self.assertEqual(
                        result.deck.draw_pile[-3:], state.deck.draw_pile[-3:]
                    )
                checked += 1
        self.assertGreater(checked, 0)

    def test_determinize_discards(self):
        """Verifies that the government's determinizations keep the policies it discarded."""
        rng = Random(0)
        state = create_game((0, 1, 2, 3, 4), seed=5, shuffle_players=False)
        state = apply_action(state, NominateAction(description="", target_uid=1), 0)
        for uid in range(5):
            state = apply_action(state, VoteAction(description="", vote=Vote.JA), uid)
        state = apply_action(
            state, PresidentDiscardAction(description="", target_index=0), 0
        )
        for _ in range(10):
            result = _determinize_for(state, 0, rng)
            self.assertEqual(result.deck.discard_pile, state.deck.discard_pile)
            chancellor_view = _determinize_for(state, 1, rng)
            self.assertEqual(chancellor_view.drawn_policies, state.drawn_policies)

        state = apply_action(
            state, ChancellorEnactAction(description="", target_index=0), 1
        )
        for _ in range(10):
            result = _determinize_for(state, 0, rng)
            self.assertEqual(
                sorted(result.deck.discard_pile), sorted(state.deck.discard_pile)
            )
            chancellor_view = _determinize_for(state, 1, rng)
            self.assertIn(
                state.deck.discard_pile[-1], chancellor_view.deck.discard_pile
            )


if __name__ == "__main__":
    unittest.main()
