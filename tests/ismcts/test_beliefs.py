import unittest
from dataclasses import replace

from frozendict import frozendict

from tyrant.agents.ismcts.beliefs import party_of, role_assignments, role_weights
from tyrant.models.claim import ChancellorEnactClaim, PresidentEnactClaim
from tyrant.models.board import Board
from tyrant.models.enums import Party, PolicyTile, Role, Vote
from tyrant.models.event import (
    ClaimEvent,
    ElectionEvent,
    ExecutionEvent,
    NominationEvent,
    PolicyEnactedEvent,
)
from tyrant.models.game_state import GameState, create_game, scrub_state

ROLES = frozendict(
    {
        0: Role.LIBERAL,
        1: Role.LIBERAL,
        2: Role.LIBERAL,
        3: Role.FASCIST,
        4: Role.HITLER,
    }
)


def _game(**changes) -> GameState:
    """Returns a 5-player game seated in UID order with the fixed test roles."""
    state = create_game((0, 1, 2, 3, 4), seed=1, roles=ROLES, shuffle_players=False)
    return replace(state, **changes)


def _government(president: int, chancellor: int, policy: PolicyTile) -> tuple:
    """Returns the events of an elected government that enacted the policy."""
    return (
        NominationEvent(president_uid=president, chancellor_uid=chancellor),
        ElectionEvent(
            president_uid=president,
            chancellor_uid=chancellor,
            votes=frozendict({uid: Vote.JA for uid in range(5)}),
            result=Vote.JA,
        ),
        PolicyEnactedEvent(
            policy=policy, president_uid=president, chancellor_uid=chancellor
        ),
    )


class TestRoleAssignments(unittest.TestCase):
    def test_role_assignments_immutability(self):
        """Verifies that role_assignments leaves the state unchanged and returns immutable deals."""
        state = scrub_state(_game(), 0)
        before = replace(state)
        deals = role_assignments(state, 0)
        self.assertEqual(state, before)
        self.assertIsInstance(deals, tuple)
        for deal in deals:
            self.assertIsInstance(deal, frozendict)

    def test_role_assignments_liberal_viewer(self):
        """Verifies that a liberal viewer in a 5-player game has 12 possible deals."""
        deals = role_assignments(scrub_state(_game(), 0), 0)
        self.assertEqual(len(deals), 12)
        self.assertTrue(all(deal[0] == Role.LIBERAL for deal in deals))

    def test_role_assignments_fascist_viewer(self):
        """Verifies that a fascist viewer in a 5-player game has only the true deal."""
        deals = role_assignments(scrub_state(_game(), 3), 3)
        self.assertEqual(deals, (ROLES,))

    def test_role_assignments_hitler_zone_chancellor(self):
        """Verifies that a chancellor elected in the Hitler zone is never Hitler."""
        events = (
            _government(0, 1, PolicyTile.FASCIST)
            + _government(1, 2, PolicyTile.FASCIST)
            + _government(2, 3, PolicyTile.FASCIST)
            + _government(3, 4, PolicyTile.LIBERAL)[:2]
        )
        state = scrub_state(_game(events=events, board=Board(5, 0, 3)), 0)
        deals = role_assignments(state, 0)
        self.assertTrue(deals)
        self.assertTrue(all(deal[4] != Role.HITLER for deal in deals))
        self.assertTrue(any(deal[3] == Role.HITLER for deal in deals))

    def test_role_assignments_executed_player(self):
        """Verifies that an executed player is never Hitler."""
        events = (ExecutionEvent(president_uid=0, target_uid=2),)
        deals = role_assignments(scrub_state(_game(events=events), 0), 0)
        self.assertTrue(all(deal[2] != Role.HITLER for deal in deals))


class TestRoleWeights(unittest.TestCase):
    def test_role_weights_immutability(self):
        """Verifies that role_weights leaves the state and deals unchanged and returns a tuple."""
        state = scrub_state(_game(events=_government(0, 1, PolicyTile.FASCIST)), 0)
        deals = role_assignments(state, 0)
        before = (replace(state), deals)
        weights = role_weights(state, deals)
        self.assertEqual((state, deals), before)
        self.assertIsInstance(weights, tuple)
        self.assertEqual(len(weights), len(deals))

    def test_role_weights_claim_conflict(self):
        """Verifies that conflicting claims lower the weight of deals where that government is all liberal."""
        events = (
            NominationEvent(president_uid=1, chancellor_uid=2),
            ClaimEvent(
                claim=PresidentEnactClaim(
                    uid=1,
                    policies=(
                        PolicyTile.FASCIST,
                        PolicyTile.LIBERAL,
                        PolicyTile.LIBERAL,
                    ),
                    discarded=PolicyTile.FASCIST,
                ),
                president_uid=1,
                chancellor_uid=2,
                target_uid=None,
            ),
            ClaimEvent(
                claim=ChancellorEnactClaim(
                    uid=2, policies=(PolicyTile.FASCIST, PolicyTile.FASCIST)
                ),
                president_uid=1,
                chancellor_uid=2,
                target_uid=None,
            ),
        )
        state = scrub_state(_game(events=events), 0)
        deals = role_assignments(state, 0)
        weights = role_weights(state, deals)
        liberal = [
            w
            for deal, w in zip(deals, weights)
            if party_of(deal[1]) is Party.LIBERAL and party_of(deal[2]) is Party.LIBERAL
        ]
        other = [
            w
            for deal, w in zip(deals, weights)
            if party_of(deal[1]) is Party.FASCIST or party_of(deal[2]) is Party.FASCIST
        ]
        self.assertTrue(liberal and other)
        self.assertLess(max(liberal), min(other))


if __name__ == "__main__":
    unittest.main()
