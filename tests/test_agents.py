import unittest
from dataclasses import FrozenInstanceError, is_dataclass, replace

from tyrant.exceptions import TyrantError
from tyrant.models.agents import Action, _get_legal_actions_nomination
from tyrant.models.election_tracker import ElectionTracker
from tyrant.models.enums import Vote
from tyrant.models.game_state import cast_vote, create_game, nominate_chancellor


class TestAction(unittest.TestCase):
    def test_action_immutability(self):
        """Test that the Action dataclass is frozen."""
        action = Action(id="vote_ja", description="Vote JA")
        self.assertTrue(is_dataclass(action))

        with self.assertRaises(FrozenInstanceError):
            action.id = "vote_nein"


class TestGetLegalActionsNomination(unittest.TestCase):
    def test__get_legal_actions_nomination_immutability(self):
        """Ensure the output of _get_legal_actions_nomination is an immutable tuple."""
        state = create_game(tuple(range(5)))
        president = state.players[state.president_index]
        actions = _get_legal_actions_nomination(state, president.uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_nomination_non_president(self):
        """Ensure every non-president player receives an empty tuple."""
        for player_count in range(5, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(player_count)))
                president_uid = state.players[state.president_index].uid
                for p in state.players:
                    if p.uid != president_uid:
                        actions = _get_legal_actions_nomination(state, p.uid)
                        self.assertEqual(actions, tuple())

    def test__get_legal_actions_nomination_president_start(self):
        """Ensure that for every player count at the beginning of the game, everyone else is eligible for chancellorship."""
        for player_count in range(5, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(player_count)))
                president_uid = state.players[state.president_index].uid
                actions = _get_legal_actions_nomination(state, president_uid)
                self.assertEqual(len(actions), player_count - 1)
                for action in actions:
                    self.assertTrue(action.id.startswith("nominate_"))

    def test__get_legal_actions_nomination_president_5_player(self):
        """Ensure that in 5 player, the previous chancellor cannot be elected but previous president can."""
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uids = [p.uid for p in state.players if p.uid != president_uid]
        prev_chancellor = other_uids[0]
        prev_president = other_uids[1]

        state = replace(
            state,
            previous_chancellor=prev_chancellor,
            previous_president=prev_president,
        )
        actions = _get_legal_actions_nomination(state, president_uid)
        action_ids = [a.id for a in actions]

        self.assertNotIn(f"nominate_{prev_chancellor}", action_ids)
        self.assertIn(f"nominate_{prev_president}", action_ids)
        self.assertEqual(len(actions), 3)

    def test__get_legal_actions_nomination_president_5_alive(self):
        """Ensure the previous chancellor cannot be elected but previous president can when only 5 players are alive."""
        for player_count in range(6, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(player_count)))
                new_players = list(state.players)
                killed = 0
                for i, p in enumerate(new_players):
                    if i != state.president_index and killed < (player_count - 5):
                        new_players[i] = replace(p, is_alive=False)
                        killed += 1
                state = replace(state, players=tuple(new_players))

                president_uid = state.players[state.president_index].uid
                alive_others = [
                    p.uid
                    for p in state.players
                    if p.is_alive and p.uid != president_uid
                ]
                prev_chancellor = alive_others[0]
                prev_president = alive_others[1]

                state = replace(
                    state,
                    previous_chancellor=prev_chancellor,
                    previous_president=prev_president,
                )
                actions = _get_legal_actions_nomination(state, president_uid)
                action_ids = [a.id for a in actions]

                self.assertNotIn(f"nominate_{prev_chancellor}", action_ids)
                self.assertIn(f"nominate_{prev_president}", action_ids)
                self.assertEqual(len(actions), 3)

    def test__get_legal_actions_nomination_president_6_10(self):
        """Ensure that neither the previous chancellor nor previous president can be elected."""
        for player_count in range(6, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(player_count)))
                president_uid = state.players[state.president_index].uid
                other_uids = [p.uid for p in state.players if p.uid != president_uid]
                prev_chancellor = other_uids[0]
                prev_president = other_uids[1]

                state = replace(
                    state,
                    previous_chancellor=prev_chancellor,
                    previous_president=prev_president,
                )
                actions = _get_legal_actions_nomination(state, president_uid)
                action_ids = [a.id for a in actions]

                self.assertNotIn(f"nominate_{prev_chancellor}", action_ids)
                self.assertNotIn(f"nominate_{prev_president}", action_ids)
                self.assertEqual(len(actions), player_count - 3)

    def test__get_legal_actions_invalid_uid(self):
        """Ensure TyrantError is raised for trying to get actions for an invalid uid."""
        state = create_game(tuple(range(5)))
        invalid_uid = 999
        with self.assertRaises(TyrantError):
            _ = _get_legal_actions_nomination(state, invalid_uid)

    def test__get_legal_actions_nomination_excludes_dead_players(self):
        """Ensure a dead player is not included in the legal actions for nomination."""
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uids = [p.uid for p in state.players if p.uid != president_uid]
        dead_player_uid = other_uids[0]

        new_players = list(state.players)
        for i, p in enumerate(new_players):
            if p.uid == dead_player_uid:
                new_players[i] = replace(p, is_alive=False)
        state = replace(state, players=tuple(new_players))

        actions = _get_legal_actions_nomination(state, president_uid)
        action_ids = [a.id for a in actions]

        self.assertNotIn(f"nominate_{dead_player_uid}", action_ids)

    def test__get_legal_actions_nomination_excludes_self(self):
        """Ensure the active president is not included in the legal actions for nomination."""
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid

        actions = _get_legal_actions_nomination(state, president_uid)
        action_ids = [a.id for a in actions]

        self.assertNotIn(f"nominate_{president_uid}", action_ids)

    def test__get_legal_actions_nomination_after_top_deck(self):
        """Ensure all alive players are eligible if term limits are cleared after a top deck."""
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uids = [p.uid for p in state.players if p.uid != president_uid]

        state = replace(
            state,
            previous_chancellor=other_uids[0],
            previous_president=other_uids[1],
            election_tracker=ElectionTracker(failed_elections=2),
        )

        state = nominate_chancellor(state, other_uids[2])
        for p in state.players:
            state = cast_vote(state, p.uid, Vote.NEIN)

        self.assertIsNone(state.previous_chancellor)
        self.assertIsNone(state.previous_president)

        new_president_uid = state.players[state.president_index].uid
        actions = _get_legal_actions_nomination(state, new_president_uid)

        self.assertEqual(len(actions), 4)


if __name__ == "__main__":
    unittest.main()
