import unittest
from random import Random
from dataclasses import is_dataclass, fields, replace

from tyrant.models.enums import GamePhase, Party, Role, Vote, PolicyTile
from tyrant.models.player import Player
from tyrant.models.board import Board
from tyrant.models.deck import create_deck
from tyrant.models.election_tracker import ElectionTracker
from tyrant.models.ballot_box import BallotBox, submit_vote
from tyrant.models.game_state import (
    GameState,
    create_game,
    _advance_to_nomination,
    nominate_chancellor,
    cast_vote,
    _resolve_election,
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
        """Verifies that an error is raised when creating a game with an invalid player count."""
        for count in [4, 11]:
            with self.subTest(player_count=count):
                uids = tuple(i for i in range(4))

                with self.assertRaises(ValueError):
                    create_game(uids, self.rng)

    def test_create_game_invalid_player_uids(self):
        """Verifies that an error is raised when player uids are not unique."""
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
        state = create_game((1, 2, 3, 4, 5), self.rng)
        state = replace(state, phase=GamePhase.VOTING)

        target_uid = state.players[1].uid
        with self.assertRaises(ValueError):
            nominate_chancellor(state, target_uid)

    def test_nominate_chancellor_leq_6(self):
        """Verifies that the target chancellor cannot be the previous chancellor but can be the previous president."""
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


class TestCastVote(BaseGameStateTest):
    def setUp(self):
        self.rng = Random(42)

    def test_cast_vote_immutability(self):
        """Verifies that cast_vote returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), self.rng)
        state = replace(state, phase=GamePhase.VOTING)

        uid = state.players[0].uid
        new_state = cast_vote(state, uid, Vote.JA, self.rng)

        self.assert_pure_transition(state, new_state)

    def test_cast_vote(self):
        """Verifies that the ballot box is updated correctly for each vote."""
        state = create_game((1, 2, 3, 4, 5), self.rng)
        state = replace(state, phase=GamePhase.VOTING)

        uid1 = state.players[0].uid
        uid2 = state.players[1].uid

        state = cast_vote(state, uid1, Vote.JA, self.rng)
        self.assertEqual(state.ballot_box.votes[uid1], Vote.JA)
        self.assertEqual(state.ballot_box.vote_count, 1)

        state = cast_vote(state, uid2, Vote.NEIN, self.rng)
        self.assertEqual(state.ballot_box.votes[uid1], Vote.JA)
        self.assertEqual(state.ballot_box.votes[uid2], Vote.NEIN)
        self.assertEqual(state.ballot_box.vote_count, 2)

    def test_cast_vote_change(self):
        """Verifies that a player can vote one way and then change their vote."""
        state = create_game((1, 2, 3, 4, 5), self.rng)
        state = replace(state, phase=GamePhase.VOTING)

        uid = state.players[0].uid

        state = cast_vote(state, uid, Vote.JA, self.rng)
        self.assertEqual(state.ballot_box.votes[uid], Vote.JA)
        self.assertEqual(state.ballot_box.vote_count, 1)

        state = cast_vote(state, uid, Vote.NEIN, self.rng)
        self.assertEqual(state.ballot_box.votes[uid], Vote.NEIN)
        self.assertEqual(state.ballot_box.vote_count, 1)

    def test_cast_vote_invalid_uid(self):
        """Verifies that an invalid player uid cannot contribute a vote."""
        state = create_game((1, 2, 3, 4, 5), self.rng)
        state = replace(state, phase=GamePhase.VOTING)

        with self.assertRaises(ValueError):
            cast_vote(state, 999, Vote.JA, self.rng)

    def test_cast_vote_dead(self):
        """Verifies that a dead player cannot vote."""
        state = create_game((1, 2, 3, 4, 5), self.rng)

        new_players = list(state.players)
        new_players[0] = replace(new_players[0], is_alive=False)
        state = replace(state, players=tuple(new_players), phase=GamePhase.VOTING)

        dead_uid = state.players[0].uid
        with self.assertRaises(ValueError):
            cast_vote(state, dead_uid, Vote.JA, self.rng)

    def test_cast_vote_wrong_game_phase(self):
        """Verifies that error is raised if the passed GameState has a phase other than VOTING."""
        state = create_game((1, 2, 3, 4, 5), self.rng)
        state = replace(state, phase=GamePhase.NOMINATION)

        with self.assertRaises(ValueError):
            cast_vote(state, 1, Vote.JA, self.rng)


class TestResolveElection(BaseGameStateTest):
    def setUp(self):
        self.rng = Random(42)

    def _get_voted_state(self, jas=3, neins=2, hitler_zone=False):
        state = create_game((1, 2, 3, 4, 5), self.rng)
        if hitler_zone:
            state = replace(state, board=replace(state.board, fascist_played=3))

        target_chancellor_uid = None
        for p in state.players:
            if p.uid != state.players[state.president_index].uid:
                target_chancellor_uid = p.uid
                break

        state = nominate_chancellor(state, target_chancellor_uid)

        new_ballot = state.ballot_box
        votes = [Vote.JA] * jas + [Vote.NEIN] * neins
        for i, v in enumerate(votes):
            new_ballot = submit_vote(new_ballot, state.players[i].uid, v)

        return replace(state, ballot_box=new_ballot)

    def test__resolve_election_immutability(self):
        """Verifies that _resolve_election returns a new instance without mutating the input state."""
        state = self._get_voted_state(3, 2)
        new_state = _resolve_election(state, self.rng)
        self.assert_pure_transition(state, new_state)

    def test__resolve_election_successful_vote(self):
        """Verifies that a successful election updates the phase and previous government correctly."""
        state = self._get_voted_state(3, 2)
        new_state = _resolve_election(state, self.rng)

        self.assertEqual(new_state.phase, GamePhase.PRESIDENT_DISCARD)
        self.assertEqual(len(new_state.drawn_policies), 3)
        self.assertEqual(
            new_state.previous_president, state.players[state.president_index].uid
        )
        self.assertEqual(new_state.previous_chancellor, state.nominated_chancellor)

    def test__resolve_election_successful_vote_after_failure(self):
        """Verifies that a successful election resets the failed elections tracker."""
        state = self._get_voted_state(3, 2)
        state = replace(
            state, election_tracker=replace(state.election_tracker, failed_elections=2)
        )

        new_state = _resolve_election(state, self.rng)
        self.assertEqual(new_state.election_tracker.failed_elections, 0)

    def test__resolve_election_failed_vote(self):
        """Verifies that a majority NEIN vote increments the failed elections tracker and advances to nomination."""
        state = self._get_voted_state(2, 3)
        new_state = _resolve_election(state, self.rng)

        self.assertEqual(new_state.election_tracker.failed_elections, 1)
        self.assertEqual(new_state.phase, GamePhase.NOMINATION)

    def test__resolve_election_tied_vote(self):
        """Verifies that a tied vote increments the failed elections tracker and advances to nomination."""
        # We need a tie, let's use 6 players
        state = create_game((1, 2, 3, 4, 5, 6), self.rng)
        state = nominate_chancellor(state, state.players[1].uid)

        new_ballot = state.ballot_box
        votes = [Vote.JA] * 3 + [Vote.NEIN] * 3
        for i, v in enumerate(votes):
            new_ballot = submit_vote(new_ballot, state.players[i].uid, v)
        state = replace(state, ballot_box=new_ballot)

        new_state = _resolve_election(state, self.rng)

        self.assertEqual(new_state.election_tracker.failed_elections, 1)
        self.assertEqual(new_state.phase, GamePhase.NOMINATION)

    def test__resolve_election_hitler_zone(self):
        """Verifies that fascists win instantly if Hitler is elected during the Hitler zone."""
        state = create_game((1, 2, 3, 4, 5), self.rng)
        state = replace(state, board=replace(state.board, fascist_played=3))

        hitler_uid = next(p.uid for p in state.players if p.role == Role.HITLER)

        # Ensure hitler is not president
        if state.players[state.president_index].uid == hitler_uid:
            state = _advance_to_nomination(state)

        state = nominate_chancellor(state, hitler_uid)

        new_ballot = state.ballot_box
        votes = [Vote.JA] * 5
        for i, v in enumerate(votes):
            new_ballot = submit_vote(new_ballot, state.players[i].uid, v)
        state = replace(state, ballot_box=new_ballot)

        new_state = _resolve_election(state, self.rng)
        self.assertEqual(new_state.winner, Party.FASCIST)
        self.assertEqual(new_state.phase, GamePhase.GAME_OVER)

    def test__resolve_election_not_hitler_zone(self):
        """Verifies that the game progresses if Hitler is elected before the Hitler zone."""
        state = create_game((1, 2, 3, 4, 5), self.rng)
        state = replace(
            state, board=replace(state.board, fascist_played=2)
        )  # Not yet hitler zone

        hitler_uid = next(p.uid for p in state.players if p.role == Role.HITLER)

        if state.players[state.president_index].uid == hitler_uid:
            state = _advance_to_nomination(state)

        state = nominate_chancellor(state, hitler_uid)

        new_ballot = state.ballot_box
        votes = [Vote.JA] * 5
        for i, v in enumerate(votes):
            new_ballot = submit_vote(new_ballot, state.players[i].uid, v)
        state = replace(state, ballot_box=new_ballot)

        new_state = _resolve_election(state, self.rng)
        self.assertIsNone(new_state.winner)
        self.assertEqual(new_state.phase, GamePhase.PRESIDENT_DISCARD)

    def test__resolve_election_top_deck(self):
        """Verifies that three failed votes in a row result in a top deck and reset government."""
        state = self._get_voted_state(2, 3)
        state = replace(
            state, election_tracker=replace(state.election_tracker, failed_elections=2)
        )

        new_state = _resolve_election(state, self.rng)

        self.assertEqual(new_state.election_tracker.failed_elections, 0)
        self.assertEqual(new_state.phase, GamePhase.NOMINATION)
        self.assertIsNone(new_state.previous_president)
        self.assertIsNone(new_state.previous_chancellor)

        # A tile should have been played
        total_played = new_state.board.liberal_played + new_state.board.fascist_played
        self.assertEqual(total_played, 1)

    def test__resolve_election_top_deck_win(self):
        """Verifies that a top deck can end the game if it reaches the required policy count."""
        state = self._get_voted_state(2, 3)
        state = replace(
            state, election_tracker=replace(state.election_tracker, failed_elections=2)
        )

        top_tile = state.deck.draw_pile[-1]

        if top_tile == PolicyTile.LIBERAL:
            state = replace(state, board=replace(state.board, liberal_played=4))
        else:
            state = replace(state, board=replace(state.board, fascist_played=5))

        new_state = _resolve_election(state, self.rng)
        expected_winner = (
            Party.LIBERAL if top_tile == PolicyTile.LIBERAL else Party.FASCIST
        )

        self.assertIsNotNone(new_state.winner)
        self.assertEqual(new_state.winner, expected_winner)
        self.assertEqual(new_state.phase, GamePhase.GAME_OVER)


if __name__ == "__main__":
    unittest.main()
