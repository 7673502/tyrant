import unittest
from dataclasses import replace

from tyrant.models.enums import GamePhase, Party, PolicyTile, PresidentialPower, Vote
from tyrant.models.game_state import (
    GameState,
    cast_vote,
    create_game,
    investigate_loyalty,
    nominate_chancellor,
    policy_peek,
    president_discard,
    scrub_state,
)
from tyrant.models.knowledge import (
    ChancellorReceiveKnowledge,
    InvestigationKnowledge,
    PeekKnowledge,
    PresidentDrawKnowledge,
)

UIDS = (1, 2, 3, 4, 5, 6, 7)


def _president(state: GameState) -> int:
    return state.players[state.president_index].uid


def _elected(state: GameState) -> GameState:
    target = next(p.uid for p in state.players if p.uid != _president(state))
    state = nominate_chancellor(state, target)
    for p in state.players:
        state = cast_vote(state, p.uid, Vote.JA)
    return state


class TestPrivateKnowledge(unittest.TestCase):
    def setUp(self):
        self.state = create_game(UIDS, 42)

    def test_create_game_has_no_knowledge(self):
        """Verifies that a new game starts with no private knowledge."""
        self.assertEqual(self.state.knowledge, ())

    def test_election_records_president_draw(self):
        """Verifies that a passed election records the three cards the president drew."""
        state = _elected(self.state)
        self.assertEqual(
            state.knowledge,
            (
                PresidentDrawKnowledge(
                    uid=_president(state),
                    chancellor_uid=state.chancellor,
                    policies=state.drawn_policies,
                ),
            ),
        )

    def test_president_discard_records_chancellor_receive(self):
        """Verifies that a president discard records the two cards the chancellor received."""
        state = president_discard(_elected(self.state), 0)
        self.assertEqual(
            state.knowledge[-1],
            ChancellorReceiveKnowledge(
                uid=state.chancellor,
                president_uid=_president(state),
                policies=state.drawn_policies,
            ),
        )

    def test_policy_peek_records_peeked_cards(self):
        """Verifies that a policy peek records the three peeked cards for the president."""
        state = replace(
            self.state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.POLICY_PEEK,
        )
        new_state = policy_peek(state)
        self.assertEqual(
            new_state.knowledge,
            (PeekKnowledge(uid=_president(state), policies=new_state.drawn_policies),),
        )

    def test_investigation_records_result(self):
        """Verifies that an investigation records the target's party for the president."""
        state = replace(
            self.state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.INVESTIGATE_LOYALTY,
        )
        target = next(p for p in state.players if p.uid != _president(state))
        new_state = investigate_loyalty(state, target.uid)
        self.assertEqual(
            new_state.knowledge,
            (
                InvestigationKnowledge(
                    uid=_president(state), target_uid=target.uid, party=target.party
                ),
            ),
        )

    def test_knowledge_survives_after_transient_fields_clear(self):
        """Verifies that private knowledge remains after drawn policies are cleared."""
        state = president_discard(_elected(self.state), 0)
        drawn = state.knowledge[0].policies
        state = replace(state, drawn_policies=())
        self.assertEqual(state.knowledge[0].policies, drawn)

    def test_scrub_state_keeps_only_viewer_knowledge(self):
        """Verifies that scrub_state returns only the viewer's own knowledge entries."""
        state = replace(
            self.state,
            knowledge=(
                PeekKnowledge(uid=1, policies=(PolicyTile.LIBERAL,) * 3),
                InvestigationKnowledge(uid=2, target_uid=3, party=Party.FASCIST),
                PeekKnowledge(uid=1, policies=(PolicyTile.FASCIST,) * 3),
            ),
        )
        self.assertEqual(
            scrub_state(state, 1).knowledge,
            (state.knowledge[0], state.knowledge[2]),
        )
        self.assertEqual(scrub_state(state, 2).knowledge, (state.knowledge[1],))
        self.assertEqual(scrub_state(state, 3).knowledge, ())


if __name__ == "__main__":
    unittest.main()
