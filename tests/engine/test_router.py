import unittest
from dataclasses import replace

from tyrant.engine.router import get_legal_actions
from tyrant.exceptions import TyrantError
from tyrant.models.election_tracker import ElectionTracker
from tyrant.models.enums import GamePhase, PolicyTile, Vote
from tyrant.models.game_state import cast_vote, create_game, nominate_chancellor


class TestGetLegalActionsNomination(unittest.TestCase):
    def test__get_legal_actions_nomination_immutability(self):
        """Ensure the output of _get_legal_actions_nomination is an immutable tuple."""
        state = create_game(tuple(range(5)))
        president = state.players[state.president_index]
        actions = get_legal_actions(state, president.uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_nomination_non_president(self):
        """Ensure every non-president player receives an empty tuple."""
        for player_count in range(5, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(player_count)))
                president_uid = state.players[state.president_index].uid
                for p in state.players:
                    if p.uid != president_uid:
                        actions = get_legal_actions(state, p.uid)
                        self.assertEqual(actions, tuple())

    def test__get_legal_actions_nomination_president_start(self):
        """Ensure that for every player count at the beginning of the game, everyone else is eligible for chancellorship."""
        for player_count in range(5, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(player_count)))
                president_uid = state.players[state.president_index].uid
                actions = get_legal_actions(state, president_uid)
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
        actions = get_legal_actions(state, president_uid)
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
                actions = get_legal_actions(state, president_uid)
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
                actions = get_legal_actions(state, president_uid)
                action_ids = [a.id for a in actions]

                self.assertNotIn(f"nominate_{prev_chancellor}", action_ids)
                self.assertNotIn(f"nominate_{prev_president}", action_ids)
                self.assertEqual(len(actions), player_count - 3)

    def test__get_legal_actions_invalid_uid(self):
        """Ensure TyrantError is raised for trying to get actions for an invalid uid."""
        state = create_game(tuple(range(5)))
        invalid_uid = 999
        with self.assertRaises(TyrantError):
            _ = get_legal_actions(state, invalid_uid)

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

        actions = get_legal_actions(state, president_uid)
        action_ids = [a.id for a in actions]

        self.assertNotIn(f"nominate_{dead_player_uid}", action_ids)

    def test__get_legal_actions_nomination_excludes_self(self):
        """Ensure the active president is not included in the legal actions for nomination."""
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid

        actions = get_legal_actions(state, president_uid)
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
        actions = get_legal_actions(state, new_president_uid)

        self.assertEqual(len(actions), 4)


class TestGetLegalActionsVoting(unittest.TestCase):
    def test__get_legal_actions_voting_immutability(self):
        """Ensure the output of _get_legal_actions_voting is an immutable tuple."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.VOTING)
        actions = get_legal_actions(state, state.players[0].uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_voting_alive_player(self):
        """Ensure an alive player who has not voted receives vote actions."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.VOTING)
        actions = get_legal_actions(state, state.players[0].uid)
        action_ids = [a.id for a in actions]
        self.assertIn("vote_ja", action_ids)
        self.assertIn("vote_nein", action_ids)
        self.assertEqual(len(actions), 2)

    def test__get_legal_actions_voting_dead_player(self):
        """Ensure a dead player receives an empty tuple of actions."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.VOTING)
        dead_uid = state.players[0].uid

        new_players = list(state.players)
        new_players[0] = replace(new_players[0], is_alive=False)
        state = replace(state, players=tuple(new_players))

        actions = get_legal_actions(state, dead_uid)
        self.assertEqual(actions, tuple())

    def test__get_legal_actions_voting_invalid_uid(self):
        """Ensure TyrantError is raised for trying to get actions for an invalid uid."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.VOTING)
        invalid_uid = 999
        with self.assertRaises(TyrantError):
            _ = get_legal_actions(state, invalid_uid)

    def test__get_legal_actions_voting_already_voted(self):
        """Ensure an alive player who has already cast a vote receives an empty tuple."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.VOTING)
        voter_uid = state.players[0].uid

        from tyrant.models.ballot_box import submit_vote

        new_ballot_box = submit_vote(state.ballot_box, voter_uid, Vote.JA)
        state = replace(state, ballot_box=new_ballot_box)

        actions = get_legal_actions(state, voter_uid)
        self.assertEqual(actions, tuple())


class TestGetLegalActionsPresidentDiscard(unittest.TestCase):
    def test__get_legal_actions_president_discard_immutability(self):
        """Ensure the output of _get_legal_actions_president_discard is an immutable tuple."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        actions = get_legal_actions(state, state.players[state.president_index].uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_president_discard_president_receives_actions(self):
        """Ensure the active president receives discard actions for each drawn policy."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        president_uid = state.players[state.president_index].uid
        actions = get_legal_actions(state, president_uid)

        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0].id, "discard_0")
        self.assertEqual(actions[0].description, "Discard Fascist")
        self.assertEqual(actions[1].id, "discard_1")
        self.assertEqual(actions[1].description, "Discard Liberal")
        self.assertEqual(actions[2].id, "discard_2")
        self.assertEqual(actions[2].description, "Discard Fascist")

    def test__get_legal_actions_president_discard_non_president(self):
        """Ensure every non-president player receives an empty tuple."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        president_uid = state.players[state.president_index].uid

        for p in state.players:
            if p.uid != president_uid:
                actions = get_legal_actions(state, p.uid)
                self.assertEqual(actions, tuple())

    def test__get_legal_actions_president_discard_dead_player(self):
        """Ensure a dead player receives an empty tuple of actions."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )

        dead_uid = state.players[0].uid
        new_players = list(state.players)
        new_players[0] = replace(new_players[0], is_alive=False)
        state = replace(state, players=tuple(new_players))

        actions = get_legal_actions(state, dead_uid)
        self.assertEqual(actions, tuple())

    def test__get_legal_actions_president_discard_invalid_uid(self):
        """Ensure TyrantError is raised for trying to get actions for an invalid uid."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        invalid_uid = 999
        with self.assertRaises(TyrantError):
            _ = get_legal_actions(state, invalid_uid)


class TestGetLegalActionsChancellorEnact(unittest.TestCase):
    def test__get_legal_actions_chancellor_enact_immutability(self):
        """Ensure the output is an immutable tuple."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            nominated_chancellor=state.players[1].uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        actions = get_legal_actions(state, state.players[1].uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_chancellor_enact_chancellor_receives_actions(self):
        """Ensure the active nominated_chancellor receives the exact enact actions for the drawn policies."""
        state = create_game(tuple(range(5)))
        chancellor_uid = state.players[1].uid
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            nominated_chancellor=chancellor_uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        actions = get_legal_actions(state, chancellor_uid)
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0].id, "enact_0")
        self.assertEqual(actions[0].description, "Enact Fascist")
        self.assertEqual(actions[1].id, "enact_1")
        self.assertEqual(actions[1].description, "Enact Liberal")

    def test__get_legal_actions_chancellor_enact_non_chancellor(self):
        """Ensure every other player (including the active president) receives an empty tuple."""
        state = create_game(tuple(range(5)))
        chancellor_uid = state.players[1].uid
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            nominated_chancellor=chancellor_uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        for p in state.players:
            if p.uid != chancellor_uid:
                actions = get_legal_actions(state, p.uid)
                self.assertEqual(actions, tuple())

    def test__get_legal_actions_chancellor_enact_dead_player(self):
        """Ensure a dead player receives an empty tuple."""
        state = create_game(tuple(range(5)))
        dead_uid = state.players[1].uid
        new_players = list(state.players)
        new_players[1] = replace(new_players[1], is_alive=False)
        state = replace(
            state,
            players=tuple(new_players),
            phase=GamePhase.CHANCELLOR_ENACT,
            nominated_chancellor=dead_uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        actions = get_legal_actions(state, dead_uid)
        self.assertEqual(actions, tuple())

    def test__get_legal_actions_chancellor_enact_invalid_uid(self):
        """Ensure TyrantError is raised for trying to get actions for an invalid uid."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            nominated_chancellor=state.players[1].uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        invalid_uid = 999
        with self.assertRaises(TyrantError):
            _ = get_legal_actions(state, invalid_uid)

    def test__get_legal_actions_chancellor_enact_veto_locked(self):
        """Ensure the veto action is NOT in the returned tuple when veto_power_unlocked is False."""
        state = create_game(tuple(range(5)))
        chancellor_uid = state.players[1].uid
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            nominated_chancellor=chancellor_uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        self.assertFalse(state.board.veto_power_unlocked)
        actions = get_legal_actions(state, chancellor_uid)
        action_ids = [a.id for a in actions]
        self.assertNotIn("veto", action_ids)
        self.assertEqual(len(actions), 2)

    def test__get_legal_actions_chancellor_enact_veto_unlocked(self):
        """Ensure the veto action IS appended to the returned tuple when veto_power_unlocked is True."""
        state = create_game(tuple(range(5)))
        chancellor_uid = state.players[1].uid
        new_board = replace(state.board, fascist_played=5)
        state = replace(
            state,
            board=new_board,
            phase=GamePhase.CHANCELLOR_ENACT,
            nominated_chancellor=chancellor_uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        actions = get_legal_actions(state, chancellor_uid)
        action_ids = [a.id for a in actions]
        self.assertIn("veto", action_ids)
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[-1].id, "veto")
        self.assertEqual(actions[-1].description, "Veto Policies")


if __name__ == "__main__":
    unittest.main()
