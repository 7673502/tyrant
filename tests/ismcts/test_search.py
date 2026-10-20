import unittest
from dataclasses import replace
from random import Random

from frozendict import frozendict

from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.ismcts.beliefs import role_assignments, role_weights
from tyrant.ismcts.search import search
from tyrant.models.action import (
    ChancellorEnactAction,
    NominateAction,
    PresidentDiscardAction,
    VoteAction,
)
from tyrant.models.board import Board
from tyrant.models.deck import NUM_FASCIST_POLICIES, NUM_LIBERAL_POLICIES
from tyrant.models.enums import PolicyTile, Role, Vote
from tyrant.models.game_state import GameState, create_game, scrub_state
from tyrant.models.knowledge import PresidentDrawKnowledge

ROLES = frozendict(
    {
        0: Role.LIBERAL,
        1: Role.LIBERAL,
        2: Role.LIBERAL,
        3: Role.FASCIST,
        4: Role.HITLER,
    }
)
F = PolicyTile.FASCIST
L = PolicyTile.LIBERAL


def _chancellor_state(
    chancellor: int, hand: tuple[PolicyTile, PolicyTile], board: Board
) -> GameState:
    """Returns the chancellor's scrubbed view of their decision with the given hand and board, after President 0 discarded a fascist policy."""
    state = create_game((0, 1, 2, 3, 4), seed=1, roles=ROLES, shuffle_players=False)
    state = replace(state, board=board)
    state = apply_action(
        state, NominateAction(description="", target_uid=chancellor), 0
    )
    for uid in range(5):
        state = apply_action(state, VoteAction(description="", vote=Vote.JA), uid)
    drawn = hand + (F,)
    enacted = board.liberal_played + board.fascist_played
    total = NUM_LIBERAL_POLICIES + NUM_FASCIST_POLICIES
    state = replace(
        state,
        deck=replace(state.deck, draw_pile=state.deck.draw_pile[: total - enacted - 3]),
        drawn_policies=drawn,
        knowledge=state.knowledge[:-1]
        + (PresidentDrawKnowledge(uid=0, chancellor_uid=chancellor, policies=drawn),),
    )
    state = apply_action(
        state, PresidentDiscardAction(description="", target_index=2), 0
    )
    return scrub_state(state, chancellor)


def _search(state: GameState, uid: int, iterations: int, seed: int):
    """Runs a search for the player with the belief model's deals and weights."""
    deals = role_assignments(state, uid)
    return search(
        state, uid, deals, role_weights(state, deals), iterations, 0.7, Random(seed)
    )


class TestSearch(unittest.TestCase):
    def test_search_immutability(self):
        """Verifies that search leaves the state unchanged and returns an offered action."""
        game = create_game((0, 1, 2, 3, 4), seed=2)
        uid = game.players[game.president_index].uid
        state = scrub_state(game, uid)
        before = replace(state)
        action = _search(state, uid, 50, 0)
        self.assertEqual(state, before)
        self.assertIn(action, get_legal_actions(state, uid))

    def test_search_deterministic(self):
        """Verifies that the same seed gives the same offered action."""
        for seed in range(5):
            with self.subTest(seed=seed):
                state = create_game((0, 1, 2, 3, 4, 5, 6), seed=seed)
                uid = state.players[state.president_index].uid
                scrubbed = scrub_state(state, uid)
                first = _search(scrubbed, uid, 60, seed)
                self.assertEqual(first, _search(scrubbed, uid, 60, seed))
                self.assertIn(first, get_legal_actions(scrubbed, uid))

    def test_search_liberal_wins(self):
        """Verifies that a liberal chancellor at 4 liberal policies enacts the winning liberal policy."""
        state = _chancellor_state(1, (L, F), Board(5, 4, 0))
        action = _search(state, 1, 200, 0)
        self.assertIsInstance(action, ChancellorEnactAction)
        self.assertEqual(state.drawn_policies[action.target_index], L)

    def test_search_fascist_wins(self):
        """Verifies that a fascist chancellor at 5 fascist policies enacts the winning fascist policy."""
        state = _chancellor_state(3, (F, L), Board(5, 0, 5))
        action = _search(state, 3, 200, 0)
        self.assertIsInstance(action, ChancellorEnactAction)
        self.assertEqual(state.drawn_policies[action.target_index], F)


if __name__ == "__main__":
    unittest.main()
