import unittest
from dataclasses import replace

from frozendict import frozendict

from tyrant.agents.ismcts.claims import claim_action
from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.models.action import (
    ChancellorEnactAction,
    NominateAction,
    PresidentDiscardAction,
    VoteAction,
)
from tyrant.models.enums import GamePhase, Party, PolicyTile, Role, Vote
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


def _claims_state(
    president: int,
    chancellor: int,
    drawn: tuple[PolicyTile, ...],
    discard: int,
    enact: int,
) -> GameState:
    """Plays one government with a fixed hand up to its policy claims."""
    state = create_game((0, 1, 2, 3, 4), seed=1, roles=ROLES, shuffle_players=False)
    state = replace(state, president_index=president)
    state = apply_action(
        state, NominateAction(description="", target_uid=chancellor), president
    )
    for uid in range(5):
        state = apply_action(state, VoteAction(description="", vote=Vote.JA), uid)
    state = replace(
        state,
        drawn_policies=drawn,
        knowledge=state.knowledge[:-1]
        + (
            PresidentDrawKnowledge(
                uid=president, chancellor_uid=chancellor, policies=drawn
            ),
        ),
    )
    state = apply_action(
        state, PresidentDiscardAction(description="", target_index=discard), president
    )
    return apply_action(
        state, ChancellorEnactAction(description="", target_index=enact), chancellor
    )


def _claim(state: GameState, uid: int):
    """Returns the heuristic claim for the player in the scrubbed state."""
    return claim_action(scrub_state(state, uid), uid, get_legal_actions(state, uid))


class TestClaimAction(unittest.TestCase):
    def test_claim_action_immutability(self):
        """Verifies that claim_action leaves the state unchanged and returns an offered action."""
        state = scrub_state(_claims_state(0, 3, (L, F, F), 1, 1), 0)
        before = replace(state)
        actions = get_legal_actions(state, 0)
        claim = claim_action(state, 0, actions)
        self.assertEqual(state, before)
        self.assertIn(claim, actions)

    def test_claim_action_liberal_truth(self):
        """Verifies that a liberal president claims exactly what they drew and discarded."""
        claim = _claim(_claims_state(0, 3, (L, F, F), 1, 1), 0)
        self.assertEqual(claim.claim_policies, (F, F, L))
        self.assertEqual(claim.claim_discarded, F)

    def test_claim_action_fascist_chancellor(self):
        """Verifies that a fascist chancellor who enacted a fascist policy from a mixed hand claims two fascist policies."""
        state = _claims_state(0, 3, (L, F, F), 1, 1)
        self.assertEqual(state.events[-1].policy, F)
        self.assertEqual(_claim(state, 3).claim_policies, (F, F))

    def test_claim_action_fascist_chancellor_truth(self):
        """Verifies that a fascist chancellor who enacted a liberal policy claims the truth."""
        state = _claims_state(0, 3, (L, F, F), 1, 0)
        self.assertEqual(_claim(state, 3).claim_policies, (F, L))

    def test_claim_action_fascist_president(self):
        """Verifies that a fascist president who discarded a liberal policy claims to have discarded a fascist one."""
        claim = _claim(_claims_state(3, 0, (F, L, L), 1, 1), 3)
        self.assertEqual(claim.claim_policies, (F, F, L))
        self.assertEqual(claim.claim_discarded, F)

    def test_claim_action_fascist_investigation(self):
        """Verifies that a fascist investigator calls a fascist teammate liberal."""
        state = create_game((0, 1, 2, 3, 4), seed=1, roles=ROLES, shuffle_players=False)
        state = replace(
            state,
            phase=GamePhase.CLAIM_INVESTIGATION,
            president_index=3,
            investigations=frozendict({4: 3}),
            current_investigation_result=Party.FASCIST,
        )
        self.assertEqual(_claim(state, 3).claim_party, Party.LIBERAL)


if __name__ == "__main__":
    unittest.main()
