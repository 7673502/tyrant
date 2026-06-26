import unittest
from random import Random
from dataclasses import is_dataclass, fields

from tyrant.models.enums import GamePhase, Party, Role
from tyrant.models.player import Player
from tyrant.models.board import Board
from tyrant.models.deck import create_deck
from tyrant.models.election_tracker import ElectionTracker
from tyrant.models.ballot_box import BallotBox
from tyrant.models.game_state import (
    GameState,
    create_game,
    _advance_to_nomination,
    nominate_chancellor,
)


class BaseGameStateTest(unittest.TestCase):
    def assert_state_immutable(self, state: GameState):
        for field in fields(state):
            with self.assertRaises(Exception):
                setattr(state, field.name, None)

    def assert_pure_transition(self, old_state: GameState, new_state: GameState):
        self.assertIsNot(old_state, new_state)
        self.assert_state_immutable(old_state)
        self.assert_state_immutable(new_state)


class TestGameState(BaseGameStateTest):
    def test_game_state_immutability(self):
        """Verifies that GameState is a frozen dataclass and its fields are immutable."""
        self.assertTrue(is_dataclass(GameState), "GameState must be a dataclass.")
        self.assertTrue(
            GameState.__dataclass_params__.frozen, "GameState must be frozen."
        )

        state = GameState(
            players=(),
            board=Board(player_count=5),
            deck=create_deck(Random(0)),
            election_tracker=ElectionTracker(),
            phase=GamePhase.NOMINATION,
            president_index=0,
            nominated_chancellor=None,
            ballot_box=BallotBox(),
            drawn_policies=(),
            previous_president=None,
            previous_chancellor=None,
            winner=None,
            special_election_president=None,
            veto_denied_this_term=False,
            investigations=frozendict(),
        )

        self.assert_state_immutable(state)


class TestCreateGame(BaseGameStateTest):
    def setUp(self):
        self.rng = Random(42)

    def test_create_game_immutability(self):
        """Verifies that create_game returns an immutable GameState."""
        state = create_game((0, 1, 2, 3, 4), self.rng)
        self.assert_state_immutable(state)

    def test_create_game_correctness(self):
        """Verifies that create_game returns a fully new and properly initialized state."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                uids = tuple(i for i in range(count))

                state = create_game(uids, self.rng)

                self.assertIsInstance(state, GameState)
                self.assertEqual(state.phase, GamePhase.NOMINATION)
                self.assertEqual(len(state.players), count)
                self.assertEqual(state.president_index, 0)

                hitlers = sum(1 for p in state.players if p.role == Role.HITLER)

                self.assertEqual(hitlers, 1)

    def test_create_game_invalid_player_count(self):
        for count in [4, 11]:
            with self.subTest(player_count=count):
                uids = tuple(i for i in range(4))

                with self.assertRaises(ValueError):
                    create_game(uids, self.rng)

    def test_create_game_invalid_player_uids(self):
        uids = (1, 1, 2, 3, 4, 4)

        with self.assertRaises(ValueError):
            create_game(uids, self.rng)


class TestAdvanceToNomination(BaseGameStateTest):
    def test__advance_to_nomination_immutability(self):
        """Verifies that _advance_to_nomination returns a new instance without mutating the input state."""
        players = (
            Player(uid=1, party=Party.LIBERAL, role=Role.LIBERAL),
            Player(uid=2, party=Party.LIBERAL, role=Role.LIBERAL),
            Player(uid=3, party=Party.LIBERAL, role=Role.LIBERAL),
        )
        original_state = GameState(
            players=players,
            board=Board(player_count=5),
            deck=create_deck(Random(0)),
            election_tracker=ElectionTracker(),
            phase=GamePhase.VOTING,
            president_index=0,
            nominated_chancellor=2,
            ballot_box=BallotBox(),
            drawn_policies=(),
            previous_president=1,
            previous_chancellor=None,
            winner=None,
            special_election_president=None,
            veto_denied_this_term=True,
            investigations=frozendict(),
        )

        new_state = _advance_to_nomination(original_state)

        self.assert_pure_transition(original_state, new_state)
        self.assertEqual(original_state.president_index, 0)
        self.assertEqual(original_state.phase, GamePhase.VOTING)

        self.assertEqual(new_state.president_index, 1)
        self.assertEqual(new_state.phase, GamePhase.NOMINATION)
        self.assertIsNone(new_state.nominated_chancellor)
        self.assertFalse(new_state.veto_denied_this_term)

    def test_advance_wrap_around(self):
        """Verifies that _advance_to_nomination goes to index 0 after reaching the end of the list."""
        players = (
            Player(uid=1, party=Party.LIBERAL, role=Role.LIBERAL),
            Player(uid=2, party=Party.LIBERAL, role=Role.LIBERAL),
            Player(uid=3, party=Party.LIBERAL, role=Role.LIBERAL),
        )
        original_state = GameState(
            players=players,
            board=Board(player_count=5),
            deck=create_deck(Random(0)),
            election_tracker=ElectionTracker(),
            phase=GamePhase.VOTING,
            president_index=0,
            nominated_chancellor=2,
            ballot_box=BallotBox(),
            drawn_policies=(),
            previous_president=1,
            previous_chancellor=None,
            winner=None,
            special_election_president=None,
            veto_denied_this_term=True,
            investigations=frozendict(),
        )

        new_state = _advance_to_nomination(original_state)
        self.assertEqual(new_state.president_index, 1)
        new_state = _advance_to_nomination(new_state)
        self.assertEqual(new_state.president_index, 2)
        new_state = _advance_to_nomination(new_state)
        self.assertEqual(new_state.president_index, 0)

    def test_advance_skips_dead_players(self):
        """Verifies that _advance_to_nomination skips dead players when finding the next president."""
        players = (
            Player(uid=1, party=Party.LIBERAL, role=Role.LIBERAL),
            Player(uid=2, party=Party.LIBERAL, role=Role.LIBERAL, is_alive=False),
            Player(uid=3, party=Party.LIBERAL, role=Role.LIBERAL),
        )
        state = GameState(
            players=players,
            board=Board(player_count=5),
            deck=create_deck(Random(0)),
            election_tracker=ElectionTracker(),
            phase=GamePhase.VOTING,
            president_index=0,
            nominated_chancellor=None,
            ballot_box=BallotBox(),
            drawn_policies=(),
            previous_president=None,
            previous_chancellor=None,
            winner=None,
            special_election_president=None,
            veto_denied_this_term=False,
            investigations=frozendict(),
        )

        new_state = _advance_to_nomination(state)
        self.assertEqual(new_state.president_index, 2)

    def test_advance_handles_special_election_start(self):
        """Verifies that starting a special election does not advance rotation."""
        players = (
            Player(uid=1, party=Party.LIBERAL, role=Role.LIBERAL),
            Player(uid=2, party=Party.LIBERAL, role=Role.LIBERAL),
            Player(uid=3, party=Party.LIBERAL, role=Role.LIBERAL),
        )
        state = GameState(
            players=players,
            board=Board(player_count=5),
            deck=create_deck(Random(0)),
            election_tracker=ElectionTracker(),
            phase=GamePhase.PRESIDENTIAL_POWER,
            president_index=0,
            nominated_chancellor=None,
            ballot_box=BallotBox(),
            drawn_policies=(),
            previous_president=1,
            previous_chancellor=None,
            winner=None,
            special_election_president=3,
            veto_denied_this_term=False,
            investigations=frozendict(),
        )

        new_state = _advance_to_nomination(state)
        self.assertEqual(new_state.president_index, 0)
        self.assertEqual(new_state.special_election_president, 3)

    def test_advance_handles_special_election_end(self):
        """Verifies that ending a special election correctly clears it and advances normal rotation."""
        players = (
            Player(uid=1, party=Party.LIBERAL, role=Role.LIBERAL),
            Player(uid=2, party=Party.LIBERAL, role=Role.LIBERAL),
            Player(uid=3, party=Party.LIBERAL, role=Role.LIBERAL),
        )
        state = GameState(
            players=players,
            board=Board(player_count=5),
            deck=create_deck(Random(0)),
            election_tracker=ElectionTracker(),
            phase=GamePhase.CHANCELLOR_ENACT,
            president_index=0,
            nominated_chancellor=None,
            ballot_box=BallotBox(),
            drawn_policies=(),
            previous_president=3,
            previous_chancellor=None,
            winner=None,
            special_election_president=3,
            veto_denied_this_term=False,
            investigations=frozendict(),
        )

        new_state = _advance_to_nomination(state)
        self.assertEqual(new_state.president_index, 1)
        self.assertIsNone(new_state.special_election_president)


class TestNominateChancellor(BaseGameStateTest):
    def setUp(self):
        self.rng = Random(42)

    def test_nominate_chancellor_immutability(self):
        """Verifies that nominate_chancellor returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), self.rng)
        # president_index is 0, so uid is state.players[0].uid
        target_uid = state.players[1].uid
        new_state = nominate_chancellor(state, target_uid)
        self.assert_pure_transition(state, new_state)

    def test_nominate_chancellor(self):
        """Verifies that GameState gets updated correctly with the new chancellor and GamePhase."""
        state = create_game((1, 2, 3, 4, 5), self.rng)
        target_uid = state.players[1].uid
        new_state = nominate_chancellor(state, target_uid)

        self.assertEqual(new_state.nominated_chancellor, target_uid)
        self.assertEqual(new_state.phase, GamePhase.VOTING)

    def test_nominate_chancellor_wrong_game_phase(self):
        """Verifies that error is raised if the passed GameState has a phase other than NOMINATION."""
        from dataclasses import replace

        state = create_game((1, 2, 3, 4, 5), self.rng)
        state = replace(state, phase=GamePhase.VOTING)

        target_uid = state.players[1].uid
        with self.assertRaises(ValueError):
            nominate_chancellor(state, target_uid)

    def test_nominate_chancellor_leq_6(self):
        """Verifies that the target chancellor cannot be the previous chancellor but can be the previous president."""
        from dataclasses import replace

        for count in (5, 6):
            with self.subTest(player_count=count):
                uids = tuple(range(1, count + 1))
                state = create_game(uids, self.rng)

                prev_chanc = state.players[1].uid
                prev_pres = state.players[2].uid

                state = replace(
                    state,
                    president_index=0,
                    previous_chancellor=prev_chanc,
                    previous_president=prev_pres,
                )

                with self.assertRaises(ValueError):
                    nominate_chancellor(state, prev_chanc)

                new_state = nominate_chancellor(state, prev_pres)
                self.assertEqual(new_state.nominated_chancellor, prev_pres)

    def test_nominate_chancellor_geq_7(self):
        """Verifies that the target chancellor cannot be the previous chancellor or president."""
        from dataclasses import replace

        for count in range(7, 11):
            with self.subTest(player_count=count):
                uids = tuple(range(1, count + 1))
                state = create_game(uids, self.rng)

                prev_chanc = state.players[1].uid
                prev_pres = state.players[2].uid

                state = replace(
                    state,
                    president_index=0,
                    previous_chancellor=prev_chanc,
                    previous_president=prev_pres,
                )

                with self.assertRaises(ValueError):
                    nominate_chancellor(state, prev_chanc)

                with self.assertRaises(ValueError):
                    nominate_chancellor(state, prev_pres)

    def test_nominate_chancellor_leq_6_alive(self):
        """Verifies that when <= 6 players are alive, previous chancellor cannot be elected but previous president can."""
        from dataclasses import replace

        for count in range(7, 11):
            with self.subTest(player_count=count):
                uids = tuple(range(1, count + 1))
                state = create_game(uids, self.rng)

                dead_players = state.players[6:]

                new_players = []
                for p in state.players:
                    if p in dead_players:
                        new_players.append(replace(p, is_alive=False))
                    else:
                        new_players.append(p)

                prev_chanc = new_players[1].uid
                prev_pres = new_players[2].uid

                state = replace(
                    state,
                    players=tuple(new_players),
                    president_index=0,
                    previous_chancellor=prev_chanc,
                    previous_president=prev_pres,
                )

                with self.assertRaises(ValueError):
                    nominate_chancellor(state, prev_chanc)

                new_state = nominate_chancellor(state, prev_pres)
                self.assertEqual(new_state.nominated_chancellor, prev_pres)

    def test_nominate_chancellor_dead(self):
        """Verifies that the passed chancellor is alive."""
        from dataclasses import replace

        state = create_game((1, 2, 3, 4, 5), self.rng)
        new_players = list(state.players)
        new_players[1] = replace(new_players[1], is_alive=False)
        state = replace(state, players=tuple(new_players))

        dead_uid = state.players[1].uid
        with self.assertRaises(ValueError):
            nominate_chancellor(state, dead_uid)

    def test_nominate_self(self):
        """Verifies that the current president cannot nominate themselves."""
        state = create_game((1, 2, 3, 4, 5), self.rng)
        pres_uid = state.players[state.president_index].uid
        with self.assertRaises(ValueError):
            nominate_chancellor(state, pres_uid)

    def test_nominate_invalid_uid(self):
        """Verifies that the chancellor UID is valid."""
        state = create_game((1, 2, 3, 4, 5), self.rng)
        with self.assertRaises(ValueError):
            nominate_chancellor(state, 6)


if __name__ == "__main__":
    unittest.main()
