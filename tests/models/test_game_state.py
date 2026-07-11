import unittest
from dataclasses import fields, is_dataclass, replace
from random import Random

from frozendict import frozendict

from tyrant.exceptions import InvalidMoveError, TyrantError
from tyrant.models.ballot_box import BallotBox, submit_vote
from tyrant.models.board import Board
from tyrant.models.claim import PeekClaim
from tyrant.models.deck import create_deck
from tyrant.models.election_tracker import ElectionTracker
from tyrant.models.enums import (
    HIDDEN,
    GamePhase,
    Party,
    PolicyTile,
    PresidentialPower,
    Role,
    Vote,
)
from tyrant.models.game_state import (
    GameState,
    _advance_to_nomination,
    _ensure_deck_ready,
    _resolve_election,
    acknowledge_investigation,
    call_special_election,
    cast_vote,
    chancellor_enact,
    chancellor_veto,
    claim_peek,
    create_game,
    execute_player,
    investigate_loyalty,
    nominate_chancellor,
    policy_peek,
    president_discard,
    president_veto_response,
    scrub_state,
)
from tyrant.models.player import Player


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
            chancellor=None,
            ballot_box=BallotBox(),
            drawn_policies=(),
            previous_president=None,
            previous_chancellor=None,
            winner=None,
            special_election_president=None,
            rng_state=Random(0).getstate(),
            veto_denied_this_term=False,
            investigations=frozendict(),
        )

        self.assert_state_immutable(state)


class TestCreateGame(BaseGameStateTest):
    def setUp(self):
        self.rng = Random(42)

    def test_create_game_immutability(self):
        """Verifies that create_game returns an immutable GameState."""
        state = create_game((0, 1, 2, 3, 4), 42)
        self.assert_state_immutable(state)

    def test_create_game_correctness(self):
        """Verifies that create_game returns a fully new and properly initialized state."""
        for count in range(5, 11):
            with self.subTest(player_count=count):
                uids = tuple(i for i in range(count))

                state = create_game(uids, 42)

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

                with self.assertRaises(TyrantError):
                    create_game(uids, 42)

    def test_create_game_invalid_player_uids(self):
        """Verifies that an error is raised when player uids are not unique."""
        uids = (1, 1, 2, 3, 4, 4)

        with self.assertRaises(TyrantError):
            create_game(uids, 42)


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
            chancellor=2,
            ballot_box=BallotBox(),
            drawn_policies=(),
            previous_president=1,
            previous_chancellor=None,
            winner=None,
            special_election_president=None,
            rng_state=Random(0).getstate(),
            veto_denied_this_term=True,
            investigations=frozendict(),
        )

        new_state = _advance_to_nomination(original_state)

        self.assert_pure_transition(original_state, new_state)
        self.assertEqual(original_state.president_index, 0)
        self.assertEqual(original_state.phase, GamePhase.VOTING)

        self.assertEqual(new_state.president_index, 1)
        self.assertEqual(new_state.phase, GamePhase.NOMINATION)
        self.assertIsNone(new_state.chancellor)
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
            chancellor=2,
            ballot_box=BallotBox(),
            drawn_policies=(),
            previous_president=1,
            previous_chancellor=None,
            winner=None,
            special_election_president=None,
            rng_state=Random(0).getstate(),
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
            chancellor=None,
            ballot_box=BallotBox(),
            drawn_policies=(),
            previous_president=None,
            previous_chancellor=None,
            winner=None,
            special_election_president=None,
            rng_state=Random(0).getstate(),
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
            chancellor=None,
            ballot_box=BallotBox(),
            drawn_policies=(),
            previous_president=1,
            previous_chancellor=None,
            winner=None,
            special_election_president=3,
            rng_state=Random(0).getstate(),
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
            chancellor=None,
            ballot_box=BallotBox(),
            drawn_policies=(),
            previous_president=3,
            previous_chancellor=None,
            winner=None,
            special_election_president=3,
            rng_state=Random(0).getstate(),
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
        state = create_game((1, 2, 3, 4, 5), 42)
        # president_index is 0, so uid is state.players[0].uid
        target_uid = state.players[1].uid
        new_state = nominate_chancellor(state, target_uid)
        self.assert_pure_transition(state, new_state)

    def test_nominate_chancellor(self):
        """Verifies that GameState gets updated correctly with the new chancellor and GamePhase."""
        state = create_game((1, 2, 3, 4, 5), 42)
        target_uid = state.players[1].uid
        new_state = nominate_chancellor(state, target_uid)

        self.assertEqual(new_state.chancellor, target_uid)
        self.assertEqual(new_state.phase, GamePhase.VOTING)

    def test_nominate_chancellor_wrong_game_phase(self):
        """Verifies that error is raised if the passed GameState has a phase other than NOMINATION."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.VOTING)

        target_uid = state.players[1].uid
        with self.assertRaises(InvalidMoveError):
            nominate_chancellor(state, target_uid)

    def test_nominate_chancellor_leq_5(self):
        """Verifies that the target chancellor cannot be the previous chancellor but can be the previous president."""
        for count in (5,):
            with self.subTest(player_count=count):
                uids = tuple(range(1, count + 1))
                state = create_game(uids, 42)

                prev_chanc = state.players[1].uid
                prev_pres = state.players[2].uid

                state = replace(
                    state,
                    president_index=0,
                    previous_chancellor=prev_chanc,
                    previous_president=prev_pres,
                )

                with self.assertRaises(InvalidMoveError):
                    nominate_chancellor(state, prev_chanc)

                new_state = nominate_chancellor(state, prev_pres)
                self.assertEqual(new_state.chancellor, prev_pres)

    def test_nominate_chancellor_geq_6(self):
        """Verifies that the target chancellor cannot be the previous chancellor or president."""
        for count in range(6, 11):
            with self.subTest(player_count=count):
                uids = tuple(range(1, count + 1))
                state = create_game(uids, 42)

                prev_chanc = state.players[1].uid
                prev_pres = state.players[2].uid

                state = replace(
                    state,
                    president_index=0,
                    previous_chancellor=prev_chanc,
                    previous_president=prev_pres,
                )

                with self.assertRaises(InvalidMoveError):
                    nominate_chancellor(state, prev_chanc)

                with self.assertRaises(InvalidMoveError):
                    nominate_chancellor(state, prev_pres)

    def test_nominate_chancellor_leq_5_alive(self):
        """Verifies that when <= 5 players are alive, previous chancellor cannot be elected but previous president can."""
        for count in range(6, 11):
            with self.subTest(player_count=count):
                uids = tuple(range(1, count + 1))
                state = create_game(uids, 42)

                dead_players = state.players[5:]

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

                with self.assertRaises(InvalidMoveError):
                    nominate_chancellor(state, prev_chanc)

                new_state = nominate_chancellor(state, prev_pres)
                self.assertEqual(new_state.chancellor, prev_pres)

    def test_nominate_chancellor_dead(self):
        """Verifies that the passed chancellor is alive."""
        state = create_game((1, 2, 3, 4, 5), 42)
        new_players = list(state.players)
        new_players[1] = replace(new_players[1], is_alive=False)
        state = replace(state, players=tuple(new_players))

        dead_uid = state.players[1].uid
        with self.assertRaises(InvalidMoveError):
            nominate_chancellor(state, dead_uid)

    def test_nominate_self(self):
        """Verifies that the current president cannot nominate themselves."""
        state = create_game((1, 2, 3, 4, 5), 42)
        pres_uid = state.players[state.president_index].uid
        with self.assertRaises(InvalidMoveError):
            nominate_chancellor(state, pres_uid)

    def test_nominate_invalid_uid(self):
        """Verifies that the chancellor UID is valid."""
        state = create_game((1, 2, 3, 4, 5), 42)
        with self.assertRaises(InvalidMoveError):
            nominate_chancellor(state, 6)


class TestCastVote(BaseGameStateTest):
    def setUp(self):
        self.rng = Random(42)

    def test_cast_vote_immutability(self):
        """Verifies that cast_vote returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.VOTING)

        uid = state.players[0].uid
        new_state = cast_vote(state, uid, Vote.JA)

        self.assert_pure_transition(state, new_state)

    def test_cast_vote(self):
        """Verifies that the ballot box is updated correctly for each vote."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.VOTING)

        uid1 = state.players[0].uid
        uid2 = state.players[1].uid

        state = cast_vote(state, uid1, Vote.JA)
        self.assertEqual(state.ballot_box.votes[uid1], Vote.JA)
        self.assertEqual(state.ballot_box.vote_count, 1)

        state = cast_vote(state, uid2, Vote.NEIN)
        self.assertEqual(state.ballot_box.votes[uid1], Vote.JA)
        self.assertEqual(state.ballot_box.votes[uid2], Vote.NEIN)
        self.assertEqual(state.ballot_box.vote_count, 2)

    def test_cast_vote_change(self):
        """Verifies that a player can vote one way and then change their vote."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.VOTING)

        uid = state.players[0].uid

        state = cast_vote(state, uid, Vote.JA)
        self.assertEqual(state.ballot_box.votes[uid], Vote.JA)
        self.assertEqual(state.ballot_box.vote_count, 1)

        state = cast_vote(state, uid, Vote.NEIN)
        self.assertEqual(state.ballot_box.votes[uid], Vote.NEIN)
        self.assertEqual(state.ballot_box.vote_count, 1)

    def test_cast_vote_invalid_uid(self):
        """Verifies that an invalid player uid cannot contribute a vote."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.VOTING)

        with self.assertRaises(InvalidMoveError):
            cast_vote(state, 999, Vote.JA)

    def test_cast_vote_dead(self):
        """Verifies that a dead player cannot vote."""
        state = create_game((1, 2, 3, 4, 5), 42)

        new_players = list(state.players)
        new_players[0] = replace(new_players[0], is_alive=False)
        state = replace(state, players=tuple(new_players), phase=GamePhase.VOTING)

        dead_uid = state.players[0].uid
        with self.assertRaises(InvalidMoveError):
            cast_vote(state, dead_uid, Vote.JA)

    def test_cast_vote_wrong_game_phase(self):
        """Verifies that error is raised if the passed GameState has a phase other than VOTING."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.NOMINATION)

        with self.assertRaises(InvalidMoveError):
            cast_vote(state, 1, Vote.JA)


class TestResolveElection(BaseGameStateTest):
    def setUp(self):
        self.rng = Random(42)

    def _get_voted_state(self, jas=3, neins=2, hitler_zone=False):
        state = create_game((1, 2, 3, 4, 5), 42)
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
        new_state = _resolve_election(state)
        self.assert_pure_transition(state, new_state)

    def test__resolve_election_successful_vote(self):
        """Verifies that a successful election updates the phase and previous government correctly."""
        state = self._get_voted_state(3, 2)
        new_state = _resolve_election(state)

        self.assertEqual(new_state.phase, GamePhase.PRESIDENT_DISCARD)
        self.assertEqual(len(new_state.drawn_policies), 3)
        self.assertEqual(
            new_state.previous_president, state.players[state.president_index].uid
        )
        self.assertEqual(new_state.previous_chancellor, state.chancellor)

    def test__resolve_election_successful_vote_after_failure(self):
        """Verifies that a successful election resets the failed elections tracker."""
        state = self._get_voted_state(3, 2)
        state = replace(
            state, election_tracker=replace(state.election_tracker, failed_elections=2)
        )

        new_state = _resolve_election(state)
        self.assertEqual(new_state.election_tracker.failed_elections, 0)

    def test__resolve_election_failed_vote(self):
        """Verifies that a majority NEIN vote increments the failed elections tracker and advances to nomination."""
        state = self._get_voted_state(2, 3)
        new_state = _resolve_election(state)

        self.assertEqual(new_state.election_tracker.failed_elections, 1)
        self.assertEqual(new_state.phase, GamePhase.NOMINATION)

    def test__resolve_election_tied_vote(self):
        """Verifies that a tied vote increments the failed elections tracker and advances to nomination."""
        # We need a tie, let's use 6 players
        state = create_game((1, 2, 3, 4, 5, 6), 42)
        state = nominate_chancellor(state, state.players[1].uid)

        new_ballot = state.ballot_box
        votes = [Vote.JA] * 3 + [Vote.NEIN] * 3
        for i, v in enumerate(votes):
            new_ballot = submit_vote(new_ballot, state.players[i].uid, v)
        state = replace(state, ballot_box=new_ballot)

        new_state = _resolve_election(state)

        self.assertEqual(new_state.election_tracker.failed_elections, 1)
        self.assertEqual(new_state.phase, GamePhase.NOMINATION)

    def test__resolve_election_hitler_zone(self):
        """Verifies that fascists win instantly if Hitler is elected during the Hitler zone."""
        state = create_game((1, 2, 3, 4, 5), 42)
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

        new_state = _resolve_election(state)
        self.assertEqual(new_state.winner, Party.FASCIST)
        self.assertEqual(new_state.phase, GamePhase.GAME_OVER)

    def test__resolve_election_not_hitler_zone(self):
        """Verifies that the game progresses if Hitler is elected before the Hitler zone."""
        state = create_game((1, 2, 3, 4, 5), 42)
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

        new_state = _resolve_election(state)
        self.assertIsNone(new_state.winner)
        self.assertEqual(new_state.phase, GamePhase.PRESIDENT_DISCARD)

    def test__resolve_election_top_deck(self):
        """Verifies that three failed votes in a row result in a top deck and reset government."""
        state = self._get_voted_state(2, 3)
        state = replace(
            state, election_tracker=replace(state.election_tracker, failed_elections=2)
        )

        new_state = _resolve_election(state)

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

        new_state = _resolve_election(state)
        expected_winner = (
            Party.LIBERAL if top_tile == PolicyTile.LIBERAL else Party.FASCIST
        )

        self.assertIsNotNone(new_state.winner)
        self.assertEqual(new_state.winner, expected_winner)
        self.assertEqual(new_state.phase, GamePhase.GAME_OVER)


class TestPresidentDiscard(BaseGameStateTest):
    def test_president_discard_immutability(self):
        """Verifies that president_discard returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        new_state = president_discard(state, 1)
        self.assert_pure_transition(state, new_state)

    def test_president_discard(self):
        """Verifies that discard and draw piles are updated, game phase advanced, and drawn policies updated."""
        state = create_game((1, 2, 3, 4, 5), 42)
        initial_discard_pile_size = len(state.deck.discard_pile)
        drawn = (PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST)
        state = replace(state, phase=GamePhase.PRESIDENT_DISCARD, drawn_policies=drawn)

        new_state = president_discard(state, 1)

        self.assertEqual(
            len(new_state.deck.discard_pile), initial_discard_pile_size + 1
        )
        self.assertEqual(new_state.deck.discard_pile[-1], PolicyTile.LIBERAL)
        self.assertEqual(
            new_state.drawn_policies, (PolicyTile.FASCIST, PolicyTile.FASCIST)
        )
        self.assertEqual(new_state.phase, GamePhase.CHANCELLOR_ENACT)

    def test_president_discard_wrong_game_phase(self):
        """Verifies that an error is raised if the game phase is not PRESIDENT_DISCARD."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.NOMINATION,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        with self.assertRaises(InvalidMoveError):
            president_discard(state, 1)

    def test_president_discard_improper_index(self):
        """Verifies that invalid index raises InvalidMoveError."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )

        invalid_indices = [-1, -3, 3]
        for index in invalid_indices:
            with self.subTest(discard_index=index):
                with self.assertRaises(InvalidMoveError):
                    president_discard(state, index)

        state_empty = replace(state, drawn_policies=())
        with self.subTest(discard_index=0):
            with self.assertRaises(InvalidMoveError):
                president_discard(state_empty, 0)


class TestChancellorEnact(BaseGameStateTest):
    def test_chancellor_enact_immutability(self):
        """Verifies that chancellor_enact returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        new_state = chancellor_enact(state, 1)
        self.assert_pure_transition(state, new_state)

    def test_chancellor_enact_liberal(self):
        """Verifies that phase advances properly and discard/draw piles are updated."""
        state = create_game((1, 2, 3, 4, 5), 42)
        initial_discard = len(state.deck.discard_pile)
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        new_state = chancellor_enact(state, 1)

        self.assertEqual(new_state.phase, GamePhase.NOMINATION)
        self.assertEqual(len(new_state.deck.discard_pile), initial_discard + 1)
        self.assertEqual(new_state.deck.discard_pile[-1], PolicyTile.FASCIST)
        self.assertEqual(new_state.board.liberal_played, 1)

    def test_chancellor_enact_liberal_win(self):
        """Verifies that game is over and liberal team won if the 5th liberal tile is enacted."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
            board=replace(state.board, liberal_played=4),
        )
        new_state = chancellor_enact(state, 1)

        self.assertEqual(new_state.phase, GamePhase.GAME_OVER)
        self.assertEqual(new_state.winner, Party.LIBERAL)

    def test_chancellor_enact_fascist(self):
        """Verifies that 1st fascist tile for 5-8 players has no power and advances to nomination."""
        for count in range(5, 9):
            with self.subTest(player_count=count):
                state = create_game(tuple(range(1, count + 1)), 42)
                state = replace(
                    state,
                    phase=GamePhase.CHANCELLOR_ENACT,
                    drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
                )
                new_state = chancellor_enact(state, 0)

                self.assertEqual(new_state.phase, GamePhase.NOMINATION)
                self.assertEqual(new_state.board.fascist_played, 1)

    def test_chancellor_enact_fascist_win(self):
        """Verifies that game is over and fascist team won if the 6th fascist tile is enacted."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
            board=replace(state.board, fascist_played=5),
        )
        new_state = chancellor_enact(state, 0)

        self.assertEqual(new_state.phase, GamePhase.GAME_OVER)
        self.assertEqual(new_state.winner, Party.FASCIST)

    def test_chancellor_enact_presidential_power(self):
        """Verifies sequence of powers for 9-10 players."""
        for count in (9, 10):
            with self.subTest(player_count=count):
                state = create_game(tuple(range(1, count + 1)), 42)

                for played in range(5):
                    test_state = replace(
                        state,
                        phase=GamePhase.CHANCELLOR_ENACT,
                        drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
                        board=replace(state.board, fascist_played=played),
                    )
                    new_state = chancellor_enact(test_state, 0)
                    self.assertEqual(new_state.phase, GamePhase.PRESIDENTIAL_POWER)

    def test_chancellor_enact_wrong_phase(self):
        """Verifies error raised if function is called during wrong phase."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.NOMINATION,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        with self.assertRaises(InvalidMoveError):
            chancellor_enact(state, 0)

    def test_chancellor_enact_invalid_index(self):
        """Verifies error raised if passed index is out of bounds."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        for index in [-1, 2]:
            with self.subTest(enact_index=index):
                with self.assertRaises(InvalidMoveError):
                    chancellor_enact(state, index)


class TestChancellorVeto(BaseGameStateTest):
    def test_chancellor_veto_immutability(self):
        """Verifies that chancellor_veto returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            board=replace(state.board, fascist_played=5),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        new_state = chancellor_veto(state)
        self.assert_pure_transition(state, new_state)

    def test_chancellor_veto(self):
        """Verifies that chancellor_veto updates the game phase properly."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            board=replace(state.board, fascist_played=5),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        new_state = chancellor_veto(state)
        self.assertEqual(new_state.phase, GamePhase.PRESIDENT_VETO_RESPONSE)

    def test_chancellor_veto_invalid_phase(self):
        """Verifies that an error is raised if the game phase is not CHANCELLOR_ENACT."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.NOMINATION,
            board=replace(state.board, fascist_played=5),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        with self.assertRaises(InvalidMoveError):
            chancellor_veto(state)

    def test_chancellor_veto_power_locked(self):
        """Verifies that an error is raised if veto power is locked (less than 5 fascist tiles)."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            board=replace(state.board, fascist_played=4),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        with self.assertRaises(InvalidMoveError):
            chancellor_veto(state)

    def test_chancellor_double_veto(self):
        """Verifies that if a veto already occurred this term, it cannot be vetoed again."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            board=replace(state.board, fascist_played=5),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
            veto_denied_this_term=True,
        )
        with self.assertRaises(InvalidMoveError):
            chancellor_veto(state)


class TestPresidentVetoResponse(BaseGameStateTest):
    def test_president_veto_response_immutability(self):
        """Verifies that president_veto_response returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_VETO_RESPONSE,
            board=replace(state.board, fascist_played=5),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        new_state = president_veto_response(state, approve=True)
        self.assert_pure_transition(state, new_state)

    def test_president_veto_response_approved(self):
        """Verifies that approved veto discards policies and increments tracker."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_VETO_RESPONSE,
            board=replace(state.board, fascist_played=5),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.FASCIST, PolicyTile.LIBERAL),
            election_tracker=ElectionTracker(failed_elections=1),
            veto_denied_this_term=False,
        )
        initial_discard_count = len(state.deck.discard_pile)
        new_state = president_veto_response(state, approve=True)

        self.assertEqual(new_state.phase, GamePhase.NOMINATION)
        self.assertFalse(new_state.veto_denied_this_term)
        self.assertEqual(new_state.election_tracker.failed_elections, 2)
        self.assertEqual(len(new_state.drawn_policies), 0)
        self.assertEqual(len(new_state.deck.discard_pile), initial_discard_count + 3)

    def test_president_veto_response_denied(self):
        """Verifies that denied veto returns to enact phase and sets denied flag."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_VETO_RESPONSE,
            board=replace(state.board, fascist_played=5),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
            veto_denied_this_term=False,
        )
        initial_discard_count = len(state.deck.discard_pile)
        new_state = president_veto_response(state, approve=False)

        self.assertEqual(new_state.phase, GamePhase.CHANCELLOR_ENACT)
        self.assertTrue(new_state.veto_denied_this_term)
        self.assertEqual(len(new_state.drawn_policies), 2)
        self.assertEqual(len(new_state.deck.discard_pile), initial_discard_count)

    def test_president_veto_response_invalid_phase(self):
        """Verifies that an error is raised if the game phase is not PRESIDENT_VETO_RESPONSE."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.NOMINATION,
            board=replace(state.board, fascist_played=5),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        with self.assertRaises(InvalidMoveError):
            president_veto_response(state, approve=True)

    def test_president_veto_response_veto_locked(self):
        """Verifies that an error is raised if veto power is locked (less than 5 fascist tiles)."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_VETO_RESPONSE,
            board=replace(state.board, fascist_played=4),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        with self.assertRaises(InvalidMoveError):
            president_veto_response(state, approve=True)

    def test_president_veto_response_approved_triggers_top_deck(self):
        """Verifies that an approved veto that increments the tracker to 3 triggers a top-deck policy."""
        state = create_game((1, 2, 3, 4, 5), 42)
        new_draw_pile = (PolicyTile.FASCIST,) * 5 + (PolicyTile.LIBERAL,)
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_VETO_RESPONSE,
            board=replace(state.board, fascist_played=5, liberal_played=0),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
            election_tracker=ElectionTracker(failed_elections=2),
            deck=replace(state.deck, draw_pile=new_draw_pile),
            previous_president=1,
            previous_chancellor=2,
            veto_denied_this_term=False,
        )
        new_state = president_veto_response(state, approve=True)

        self.assertEqual(new_state.phase, GamePhase.NOMINATION)
        self.assertEqual(new_state.election_tracker.failed_elections, 0)
        self.assertEqual(new_state.board.liberal_played, 1)
        self.assertEqual(new_state.board.fascist_played, 5)
        self.assertIsNone(new_state.previous_president)
        self.assertIsNone(new_state.previous_chancellor)
        self.assertEqual(len(new_state.drawn_policies), 0)

    def test_president_veto_response_approved_top_deck_win(self):
        """Verifies that if the top-decked policy triggered by a veto wins the game, the phase goes to GAME_OVER."""
        state = create_game((1, 2, 3, 4, 5), 42)
        new_draw_pile = (PolicyTile.LIBERAL,) * 5 + (PolicyTile.FASCIST,)
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_VETO_RESPONSE,
            board=replace(state.board, fascist_played=5, liberal_played=0),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
            election_tracker=ElectionTracker(failed_elections=2),
            deck=replace(state.deck, draw_pile=new_draw_pile),
            veto_denied_this_term=False,
        )
        new_state = president_veto_response(state, approve=True)

        self.assertEqual(new_state.phase, GamePhase.GAME_OVER)
        self.assertEqual(new_state.winner, Party.FASCIST)
        self.assertEqual(new_state.board.fascist_played, 6)
        self.assertEqual(new_state.election_tracker.failed_elections, 0)


class TestInvestigateLoyalty(BaseGameStateTest):
    def test_investigate_loyalty_immutability(self):
        """Verifies that investigate_loyalty returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        target_uid = state.players[1].uid
        new_state = investigate_loyalty(state, target_uid)

        self.assert_pure_transition(state, new_state)

    def test_investigate_loyalty_liberal(self):
        """Verifies that investigating a liberal reveals their party and updates the map and phase."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        president_uid = state.players[state.president_index].uid
        liberal = next(
            p
            for p in state.players
            if p.role == Role.LIBERAL and p.uid != president_uid
        )

        new_state = investigate_loyalty(state, liberal.uid)

        self.assertEqual(new_state.current_investigation_result, Party.LIBERAL)
        self.assertEqual(new_state.investigations[liberal.uid], president_uid)
        self.assertEqual(new_state.phase, GamePhase.CLAIM_INVESTIGATION)

    def test_investigate_loyalty_fascists(self):
        """Verifies that investigating a fascist (non-Hitler) reveals their party and updates map and phase."""
        state = create_game((1, 2, 3, 4, 5, 6), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        president_uid = state.players[state.president_index].uid
        fascist = next(
            (
                p
                for p in state.players
                if p.role == Role.FASCIST and p.uid != president_uid
            ),
            None,
        )

        if not fascist:
            state = _advance_to_nomination(state)
            state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)
            president_uid = state.players[state.president_index].uid
            fascist = next(
                p
                for p in state.players
                if p.role == Role.FASCIST and p.uid != president_uid
            )

        new_state = investigate_loyalty(state, fascist.uid)

        self.assertEqual(new_state.current_investigation_result, Party.FASCIST)
        self.assertEqual(new_state.investigations[fascist.uid], president_uid)
        self.assertEqual(new_state.phase, GamePhase.CLAIM_INVESTIGATION)

    def test_investigate_loyalty_hitler(self):
        """Verifies that investigating Hitler reveals fascist party and updates map and phase."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        hitler = next(p for p in state.players if p.role == Role.HITLER)

        if hitler.uid == state.players[state.president_index].uid:
            state = _advance_to_nomination(state)
            state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        president_uid = state.players[state.president_index].uid
        new_state = investigate_loyalty(state, hitler.uid)

        self.assertEqual(new_state.current_investigation_result, Party.FASCIST)
        self.assertEqual(new_state.investigations[hitler.uid], president_uid)
        self.assertEqual(new_state.phase, GamePhase.CLAIM_INVESTIGATION)

    def test_investigate_loyalty_self_investigation(self):
        """Verifies that the president cannot investigate themselves."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        president_uid = state.players[state.president_index].uid

        with self.assertRaises(InvalidMoveError):
            investigate_loyalty(state, president_uid)

    def test_investigate_loyalty_invalid_uid(self):
        """Verifies that an error is raised if the target UID does not exist."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        with self.assertRaises(InvalidMoveError):
            investigate_loyalty(state, 999)

    def test_investigate_loyalty_invalid_phase(self):
        """Verifies that an error is raised if the phase is not PRESIDENTIAL_POWER."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.NOMINATION)

        target_uid = state.players[1].uid
        with self.assertRaises(InvalidMoveError):
            investigate_loyalty(state, target_uid)

    def test_investigate_loyalty_dead(self):
        """Verifies that an error is raised if the investigated player is dead."""
        state = create_game((1, 2, 3, 4, 5), 42)
        new_players = list(state.players)
        new_players[1] = replace(new_players[1], is_alive=False)
        state = replace(
            state, phase=GamePhase.PRESIDENTIAL_POWER, players=tuple(new_players)
        )

        target_uid = state.players[1].uid
        with self.assertRaises(InvalidMoveError):
            investigate_loyalty(state, target_uid)


class TestAcknowledgeInvestigation(BaseGameStateTest):
    def test_acknowledge_investigation_immutability(self):
        """Verifies that acknowledge_investigation returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.CLAIM_INVESTIGATION,
            current_investigation_result=Party.LIBERAL,
        )
        new_state = acknowledge_investigation(state)
        self.assert_pure_transition(state, new_state)

    def test_acknowledge_investigation(self):
        """Verifies that acknowledging an investigation clears the result and advances the phase."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.CLAIM_INVESTIGATION,
            current_investigation_result=Party.LIBERAL,
        )

        new_state = acknowledge_investigation(state)
        self.assertEqual(new_state.phase, GamePhase.NOMINATION)
        self.assertIsNone(new_state.current_investigation_result)

    def test_acknowledge_investigation_wrong_phase(self):
        """Verifies that an error is raised if the phase is not INVESTIGATION."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        with self.assertRaises(InvalidMoveError):
            acknowledge_investigation(state)


class TestCallSpecialElection(BaseGameStateTest):
    def test_special_election_immutability(self):
        """Verifies that call_special_election returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        target_uid = state.players[1].uid
        new_state = call_special_election(state, target_uid)

        self.assert_pure_transition(state, new_state)

    def test_special_election(self):
        """Verifies that special election updates the president and then returns to normal rotation."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER, president_index=0)

        target_uid = state.players[3].uid

        new_state = call_special_election(state, target_uid)

        # Check special election president is set and rotation advances to target
        self.assertEqual(new_state.special_election_president, target_uid)
        self.assertEqual(new_state.president_index, 0)
        self.assertEqual(new_state.phase, GamePhase.NOMINATION)

        # Now advance to next nomination and ensure rotation returns to normal order
        # Specifically, the president after the special election should be the one following the caller (index 1)
        new_state_after_special = _advance_to_nomination(new_state)

        self.assertIsNone(new_state_after_special.special_election_president)
        self.assertEqual(new_state_after_special.president_index, 1)

    def test_special_election_next_president(self):
        """Verifies that a player can be chosen for special election even if they are the next president in normal rotation."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER, president_index=0)

        target_uid = state.players[1].uid

        new_state = call_special_election(state, target_uid)

        self.assertEqual(new_state.special_election_president, target_uid)
        self.assertEqual(new_state.president_index, 0)
        self.assertEqual(new_state.phase, GamePhase.NOMINATION)

        new_state_after_special = _advance_to_nomination(new_state)

        self.assertIsNone(new_state_after_special.special_election_president)
        self.assertEqual(new_state_after_special.president_index, 1)

    def test_special_election_self(self):
        """Verifies that the current president cannot investigate themselves."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        president_uid = state.players[state.president_index].uid

        with self.assertRaises(InvalidMoveError):
            _ = call_special_election(state, president_uid)

    def test_special_election_invalid_uid(self):
        """Verifies that an error is raised if the target UID does not exist."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        with self.assertRaises(InvalidMoveError):
            _ = call_special_election(state, 999)

    def test_special_election_wrong_phase(self):
        """Verifies that an error is raised if the phase is not PRESIDENTIAL_POWER."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.NOMINATION)

        target_uid = state.players[1].uid
        with self.assertRaises(InvalidMoveError):
            _ = call_special_election(state, target_uid)

    def test_special_election_dead(self):
        """Asserts that InvalidMoveError is raised if the target player is dead."""
        state = create_game((1, 2, 3, 4, 5), 42)
        new_players = list(state.players)
        new_players[1] = replace(new_players[1], is_alive=False)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER, players=new_players)

        target_uid = state.players[1].uid
        with self.assertRaises(InvalidMoveError):
            _ = call_special_election(state, target_uid)

    def test_special_election_next_president_dead(self):
        """Ensures that rotation skips a dead player and resumes correctly at the next alive player when the special election term ends."""
        state = create_game((1, 2, 3, 4, 5), 42)

        # Kill the player who would be next in normal rotation (index 1)
        new_players = list(state.players)
        new_players[1] = replace(new_players[1], is_alive=False)
        state = replace(
            state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            president_index=0,
            players=new_players,
        )

        target_uid = state.players[3].uid

        # Call special election
        new_state = call_special_election(state, target_uid)

        # End special election
        new_state_after_special = _advance_to_nomination(new_state)

        # The rotation should skip index 1 and go to index 2
        self.assertIsNone(new_state_after_special.special_election_president)
        self.assertEqual(new_state_after_special.president_index, 2)


class TestPolicyPeek(BaseGameStateTest):
    def test_policy_peek_immutability(self):
        """Verifies that policy_peek returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)
        new_state = policy_peek(state)
        self.assert_pure_transition(state, new_state)

    def test_claim_peek_immutability(self):
        """Verifies that claim_peek returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.CLAIM_POLICY_PEEK,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        claim = PeekClaim(
            uid=state.players[state.president_index].uid,
            policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        new_state = claim_peek(state, claim)
        self.assert_pure_transition(state, new_state)

    def test_policy_peek(self):
        """Verifies that policy_peek correctly updates drawn_policies with the top 3 cards without modifying the deck."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        expected_cards = (
            state.deck.draw_pile[-1],
            state.deck.draw_pile[-2],
            state.deck.draw_pile[-3],
        )
        original_deck = state.deck

        new_state = policy_peek(state)

        self.assertEqual(new_state.drawn_policies, expected_cards)
        self.assertEqual(new_state.deck, original_deck)
        self.assertEqual(new_state.phase, GamePhase.CLAIM_POLICY_PEEK)

    def test_policy_peek_wrong_phase(self):
        """Verifies that an error is raised if policy_peek is called in the wrong phase."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.NOMINATION)

        with self.assertRaises(InvalidMoveError):
            _ = policy_peek(state)

    def test_claim_peek(self):
        """Verifies that claim_peek clears drawn_policies and advances rotation."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(
            state,
            phase=GamePhase.CLAIM_POLICY_PEEK,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
            president_index=0,
        )

        claim = PeekClaim(
            uid=state.players[state.president_index].uid,
            policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        new_state = claim_peek(state, claim)

        self.assertEqual(new_state.drawn_policies, ())
        self.assertEqual(new_state.phase, GamePhase.NOMINATION)
        self.assertEqual(new_state.president_index, 1)

    def test_claim_peek_next_president_dead(self):
        """Ensures that rotation skips a dead player and resumes correctly at the next alive player when the peek ends."""
        state = create_game((1, 2, 3, 4, 5), 42)
        new_players = list(state.players)
        new_players[1] = replace(new_players[1], is_alive=False)
        state = replace(
            state,
            phase=GamePhase.CLAIM_POLICY_PEEK,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
            president_index=0,
            players=tuple(new_players),
        )

        claim = PeekClaim(
            uid=state.players[state.president_index].uid,
            policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        new_state = claim_peek(state, claim)
        self.assertEqual(new_state.president_index, 2)
        self.assertEqual(new_state.phase, GamePhase.NOMINATION)

    def test_claim_peek_wrong_phase(self):
        """Verifies that an error is raised if claim_peek is called in the wrong phase."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.NOMINATION)
        claim = PeekClaim(
            uid=state.players[state.president_index].uid,
            policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )

        with self.assertRaises(InvalidMoveError):
            _ = claim_peek(state, claim)


class TestExecutePlayer(BaseGameStateTest):
    def test_execute_player_immutability(self):
        """Verifies that execute_player returns a new instance without mutating the input state."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)
        target_uid = state.players[1].uid
        new_state = execute_player(state, target_uid)
        self.assert_pure_transition(state, new_state)

    def test_execute_player(self):
        """Verifies that execute_player works as expected."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        target_uid = state.players[1].uid
        if state.players[1].role == Role.HITLER:
            target_uid = state.players[2].uid

        original_deck = state.deck
        new_state = execute_player(state, target_uid)

        target_player = next(p for p in new_state.players if p.uid == target_uid)
        self.assertFalse(target_player.is_alive)

        self.assertEqual(new_state.deck.draw_pile, original_deck.draw_pile)
        self.assertEqual(new_state.deck.discard_pile, original_deck.discard_pile)

        self.assertEqual(new_state.phase, GamePhase.NOMINATION)

    def test_execute_player_wrong_phase(self):
        """Verifies that an error is raised if function is called with wrong GameState phase."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.NOMINATION)

        target_uid = state.players[1].uid
        with self.assertRaises(InvalidMoveError):
            _ = execute_player(state, target_uid)

    def test_execute_player_next_president_dead(self):
        """Verifies that once the game goes to the next nomination phase, a dead player is skipped."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER, president_index=0)

        target_uid = state.players[1].uid

        if state.players[1].role == Role.HITLER:
            state = create_game((1, 2, 3, 4, 5), 43)
            state = replace(
                state, phase=GamePhase.PRESIDENTIAL_POWER, president_index=0
            )
            target_uid = state.players[1].uid

        new_state = execute_player(state, target_uid)

        self.assertEqual(new_state.president_index, 2)

    def test_execute_player_hitler_dies(self):
        """Verifies that if hitler is executed, the liberals win and game phase is updated to game over."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        hitler_uid = next(p.uid for p in state.players if p.role == Role.HITLER)

        if state.players[state.president_index].uid == hitler_uid:
            state = replace(state, president_index=(state.president_index + 1) % 5)

        new_state = execute_player(state, hitler_uid)

        self.assertEqual(new_state.winner, Party.LIBERAL)
        self.assertEqual(new_state.phase, GamePhase.GAME_OVER)

    def test_execute_player_self_execution(self):
        """Verifies that an error is raised so player cannot attempt to execute themselves."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        president_uid = state.players[state.president_index].uid
        with self.assertRaises(InvalidMoveError):
            _ = execute_player(state, president_uid)

    def test_execute_player_invalid_uid(self):
        """Verifies that an error is raised if function is called with non-existent UID."""
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, phase=GamePhase.PRESIDENTIAL_POWER)

        with self.assertRaises(InvalidMoveError):
            _ = execute_player(state, 999)

    def test_execute_player_already_dead(self):
        """Verifies that a player who is already dead cannot be executed."""
        state = create_game((1, 2, 3, 4, 5), 42)

        target_uid = state.players[1].uid
        new_players = list(state.players)
        new_players[1] = replace(new_players[1], is_alive=False)

        state = replace(
            state, phase=GamePhase.PRESIDENTIAL_POWER, players=tuple(new_players)
        )

        with self.assertRaises(InvalidMoveError):
            _ = execute_player(state, target_uid)


class TestEnsureDeckReady(BaseGameStateTest):
    def test__ensure_deck_ready_no_shuffle(self):
        """Ensures correctness after no shuffle is required when function is called."""
        state = create_game((1, 2, 3, 4, 5), 42)
        new_state = _ensure_deck_ready(state)
        self.assertFalse(new_state.deck_shuffled_last_action)
        self.assertEqual(len(new_state.deck.draw_pile), 17)

    def test__ensure_deck_ready_yes_shuffle(self):
        """Ensures correctness when shuffle is required after function is called."""
        state = create_game((1, 2, 3, 4, 5), 42)
        discarded = (PolicyTile.LIBERAL,) * 5 + (PolicyTile.FASCIST,) * 5
        deck = replace(
            state.deck,
            draw_pile=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
            discard_pile=discarded,
        )
        state = replace(state, deck=deck)
        new_state = _ensure_deck_ready(state)
        self.assertTrue(new_state.deck_shuffled_last_action)
        self.assertEqual(len(new_state.deck.draw_pile), 12)
        self.assertEqual(len(new_state.deck.discard_pile), 0)

    def test__ensure_deck_ready_reshuffle_immutability(self):
        """Tests that after a reshuffle, passes immutability criteria outlined in design document."""
        state = create_game((1, 2, 3, 4, 5), 42)
        deck = replace(
            state.deck,
            draw_pile=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
            discard_pile=(PolicyTile.LIBERAL,),
        )
        state = replace(state, deck=deck)
        new_state = _ensure_deck_ready(state)
        self.assert_pure_transition(state, new_state)

    def test__ensure_deck_ready_no_reshuffle_immutability(self):
        """Tests that after no reshuffle occurs after calling _ensure_deck_ready, passes immutability criteria outlined in design document."""
        state = create_game((1, 2, 3, 4, 5), 42)
        new_state = _ensure_deck_ready(state)
        self.assert_pure_transition(state, new_state)

    def test__ensure_deck_ready_before_drawing_3(self):
        """Before president draws 3, ensure reshuffle occurs (set up so <3 cards after the draw)."""
        state = create_game((1, 2, 3, 4, 5), 42)
        deck = replace(
            state.deck,
            draw_pile=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
            discard_pile=(PolicyTile.LIBERAL,),
        )
        state = replace(state, deck=deck)
        state = nominate_chancellor(state, state.players[1].uid)
        new_ballot = state.ballot_box
        for i in range(5):
            new_ballot = submit_vote(new_ballot, state.players[i].uid, Vote.JA)
        state = replace(state, ballot_box=new_ballot)

        new_state = _resolve_election(state)
        self.assertTrue(new_state.deck_shuffled_last_action)
        self.assertEqual(len(new_state.deck.draw_pile), 0)

    def test__ensure_deck_ready_before_policy_peek(self):
        """Before president peeks 3, ensure reshuffle occurs (set up so <3 cards in the draw pile)."""
        state = create_game((1, 2, 3, 4, 5), 42)
        deck = replace(
            state.deck,
            draw_pile=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
            discard_pile=(PolicyTile.LIBERAL,),
        )
        state = replace(state, deck=deck, phase=GamePhase.PRESIDENTIAL_POWER)
        new_state = policy_peek(state)
        self.assertTrue(new_state.deck_shuffled_last_action)
        self.assertEqual(len(new_state.drawn_policies), 3)
        self.assertEqual(len(new_state.deck.draw_pile), 3)

    def test__ensure_deck_ready_before_top_deck(self):
        """Before a top deck occurs, ensure reshuffle occurs (set up so <3 cards in the draw pile)."""
        state = create_game((1, 2, 3, 4, 5), 42)
        deck = replace(
            state.deck,
            draw_pile=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
            discard_pile=(PolicyTile.LIBERAL,),
        )
        state = replace(
            state,
            deck=deck,
            election_tracker=replace(state.election_tracker, failed_elections=2),
        )
        state = nominate_chancellor(state, state.players[1].uid)
        new_ballot = state.ballot_box
        for i in range(5):
            new_ballot = submit_vote(new_ballot, state.players[i].uid, Vote.NEIN)
        state = replace(state, ballot_box=new_ballot)

        new_state = _resolve_election(state)
        self.assertTrue(new_state.deck_shuffled_last_action)
        self.assertEqual(len(new_state.deck.draw_pile), 2)

    def test__ensure_deck_ready_before_veto_top_deck(self):
        """Before a top deck occurs after a veto, ensure reshuffle occurs (set up so <3 cards in the draw pile)."""
        state = create_game((1, 2, 3, 4, 5), 42)
        deck = replace(
            state.deck,
            draw_pile=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
            discard_pile=(PolicyTile.LIBERAL,),
        )
        state = replace(
            state,
            deck=deck,
            phase=GamePhase.PRESIDENT_VETO_RESPONSE,
            board=replace(state.board, fascist_played=5),
            election_tracker=replace(state.election_tracker, failed_elections=2),
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.FASCIST),
        )
        new_state = president_veto_response(state, True)
        self.assertTrue(new_state.deck_shuffled_last_action)
        self.assertEqual(len(new_state.deck.draw_pile), 4)

    def test__ensure_deck_ready_transition_functions(self):
        """Ensures every transition function that does not make use of _ensure_deck_ready resets the flag to False."""
        # This checks a representative set to make sure they reset the flag if it was True.
        state = create_game((1, 2, 3, 4, 5), 42)
        state = replace(state, deck_shuffled_last_action=True)

        state_nom = replace(state, phase=GamePhase.NOMINATION)
        new_state = nominate_chancellor(state_nom, state_nom.players[1].uid)
        self.assertFalse(new_state.deck_shuffled_last_action)

        state_voting = replace(state, phase=GamePhase.VOTING)
        new_state = cast_vote(state_voting, state_voting.players[0].uid, Vote.JA)
        self.assertFalse(new_state.deck_shuffled_last_action)


class TestScrubState(BaseGameStateTest):
    def test_scrub_state_immutability(self):
        """Test scrub_state preserves immutability and does not mutate the original state."""
        state = create_game(tuple(range(1, 8)), seed=42)
        viewer_uid = state.players[0].uid

        new_state = scrub_state(state, viewer_uid)

        self.assert_pure_transition(state, new_state)

    def test_scrub_state_liberal(self):
        """Ensure liberal player cannot see roles of anyone else."""
        for player_count in range(5, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(1, player_count + 1)), seed=42)
                liberal = next(p for p in state.players if p.role == Role.LIBERAL)

                scrubbed = scrub_state(state, liberal.uid)

                for p in scrubbed.players:
                    if p.uid == liberal.uid:
                        self.assertEqual(p.role, Role.LIBERAL)
                        self.assertEqual(p.party, Party.LIBERAL)
                    else:
                        self.assertIs(p.role, HIDDEN)
                        self.assertIs(p.party, HIDDEN)

    def test_scrub_state_fascist(self):
        """Ensure fascist (non-hitler) player can see every other fascist's (including hitler) role."""
        for player_count in range(5, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(1, player_count + 1)), seed=42)
                fascist = next(p for p in state.players if p.role == Role.FASCIST)

                scrubbed = scrub_state(state, fascist.uid)

                for p in scrubbed.players:
                    orig = next(
                        orig_p for orig_p in state.players if orig_p.uid == p.uid
                    )
                    if orig.role in (Role.FASCIST, Role.HITLER):
                        self.assertEqual(p.role, orig.role)
                        self.assertEqual(p.party, Party.FASCIST)
                    elif p.uid == fascist.uid:
                        # Should not happen since we handled it, but just in case
                        self.assertEqual(p.role, Role.FASCIST)
                    else:
                        self.assertIs(p.role, HIDDEN)
                        self.assertIs(p.party, HIDDEN)

    def test_scrub_state_hitler_5_6_player(self):
        """Ensure hitler can see everyone other fascist's role in 5-6 player games."""
        for player_count in (5, 6):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(1, player_count + 1)), seed=42)
                hitler = next(p for p in state.players if p.role == Role.HITLER)

                scrubbed = scrub_state(state, hitler.uid)

                for p in scrubbed.players:
                    orig = next(
                        orig_p for orig_p in state.players if orig_p.uid == p.uid
                    )
                    if orig.role in (Role.FASCIST, Role.HITLER):
                        self.assertEqual(p.role, orig.role)
                        self.assertEqual(p.party, Party.FASCIST)
                    else:
                        self.assertIs(p.role, HIDDEN)
                        self.assertIs(p.party, HIDDEN)

    def test_scrub_state_hitler_7_to_10_player(self):
        """Ensure hitler cannot see anyone's roles in 7-10 player games."""
        for player_count in range(7, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(1, player_count + 1)), seed=42)
                hitler = next(p for p in state.players if p.role == Role.HITLER)

                scrubbed = scrub_state(state, hitler.uid)

                for p in scrubbed.players:
                    if p.uid == hitler.uid:
                        self.assertEqual(p.role, Role.HITLER)
                        self.assertEqual(p.party, Party.FASCIST)
                    else:
                        self.assertIs(p.role, HIDDEN)
                        self.assertIs(p.party, HIDDEN)

    def test_scrub_state_not_president(self):
        """Ensure after the president has discarded, that a player who is not the president cannot see what has been drawn/discarded."""
        state = create_game(tuple(range(1, 8)), seed=42)
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        not_president = state.players[(state.president_index + 1) % len(state.players)]

        scrubbed = scrub_state(state, not_president.uid)

        self.assertEqual(scrubbed.drawn_policies, ())

    def test_scrub_state_chancellor(self):
        """Ensure after the president has discarded, the chancellor has no way of knowing what the discarded card was."""
        state = create_game(tuple(range(1, 8)), seed=42)
        chancellor_uid = state.players[
            (state.president_index + 1) % len(state.players)
        ].uid
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            chancellor=chancellor_uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )

        scrubbed = scrub_state(state, chancellor_uid)

        self.assertEqual(scrubbed.drawn_policies, ())

    def test_scrub_state_voting(self):
        """Ensure during the voting phase that other players cannot see other players' votes."""
        state = create_game(tuple(range(1, 8)), seed=42)
        uid1 = state.players[0].uid
        uid2 = state.players[1].uid

        box = replace(
            state.ballot_box, votes=frozendict({uid1: Vote.JA, uid2: Vote.NEIN})
        )
        state = replace(state, phase=GamePhase.VOTING, ballot_box=box)

        scrubbed = scrub_state(state, uid1)

        self.assertEqual(len(scrubbed.ballot_box.votes), 2)
        self.assertEqual(scrubbed.ballot_box.votes[uid1], Vote.JA)
        self.assertIs(scrubbed.ballot_box.votes[uid2], HIDDEN)

    def test_scrub_state_investigator(self):
        """Ensure if a player has investigated someone that player can see that in their scrubbed state."""
        state = create_game(tuple(range(1, 8)), seed=42)
        investigator = state.players[0]
        target = state.players[1]

        state = replace(
            state, investigations=frozendict({target.uid: investigator.uid})
        )

        scrubbed = scrub_state(state, investigator.uid)

        target_scrubbed = next(p for p in scrubbed.players if p.uid == target.uid)
        self.assertEqual(target_scrubbed.party, target.party)
        # Role remains hidden from investigation
        self.assertIs(target_scrubbed.role, HIDDEN)

    def test_scrub_state_not_investigator(self):
        """Ensure if an investigation has occurred, any player who did not investigate cannot see the result."""
        state = create_game(tuple(range(1, 8)), seed=42)
        investigator = next(p for p in state.players if p.role == Role.LIBERAL)
        # Give investigator a target that isn't themselves and isn't the bystander
        bystander = next(
            p
            for p in state.players
            if p.role == Role.LIBERAL and p.uid != investigator.uid
        )
        target = next(
            p for p in state.players if p.uid not in (investigator.uid, bystander.uid)
        )

        state = replace(
            state, investigations=frozendict({target.uid: investigator.uid})
        )

        scrubbed = scrub_state(state, bystander.uid)

        target_scrubbed = next(p for p in scrubbed.players if p.uid == target.uid)
        self.assertIs(target_scrubbed.party, HIDDEN)
        self.assertIs(target_scrubbed.role, HIDDEN)

    def test_scrub_state_draw_pile(self):
        """Ensure that the draw pile cannot be viewed by any player in the scrubbed state."""
        state = create_game(tuple(range(1, 8)), seed=42)
        uid = state.players[0].uid

        scrubbed = scrub_state(state, uid)

        self.assertEqual(len(scrubbed.deck.draw_pile), len(state.deck.draw_pile))
        self.assertTrue(all(tile is HIDDEN for tile in scrubbed.deck.draw_pile))

    def test_scrub_state_discard_pile(self):
        """Ensure that the discard pile cannot be viewed by any player in the scrubbed state."""
        state = create_game(tuple(range(1, 8)), seed=42)
        uid = state.players[0].uid

        # Add something to discard pile
        deck = replace(
            state.deck, discard_pile=(PolicyTile.FASCIST, PolicyTile.LIBERAL)
        )
        state = replace(state, deck=deck)

        scrubbed = scrub_state(state, uid)

        self.assertEqual(len(scrubbed.deck.discard_pile), len(state.deck.discard_pile))
        self.assertTrue(all(tile is HIDDEN for tile in scrubbed.deck.discard_pile))

    def test_scrub_state_policy_peek_president(self):
        """Ensure that the president can see the drawn policies during a policy peek."""
        state = create_game(tuple(range(1, 8)), seed=42)
        president = state.players[state.president_index]
        policies = (PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST)
        state = replace(
            state, phase=GamePhase.CLAIM_POLICY_PEEK, drawn_policies=policies
        )

        scrubbed = scrub_state(state, president.uid)

        self.assertEqual(scrubbed.drawn_policies, policies)

    def test_scrub_state_policy_peek_not_president(self):
        """Ensure a player that is not the president can not see the drawn policies during a policy peek."""
        state = create_game(tuple(range(1, 8)), seed=42)
        not_president = state.players[(state.president_index + 1) % len(state.players)]
        policies = (PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST)
        state = replace(
            state, phase=GamePhase.CLAIM_POLICY_PEEK, drawn_policies=policies
        )

        scrubbed = scrub_state(state, not_president.uid)

        self.assertEqual(scrubbed.drawn_policies, ())

    def test_scrub_state_drawn_policies_visibility(self):
        """During PRESIDENT_DISCARD and POLICY_PEEK, only President sees drawn_policies. During CHANCELLOR_ENACT, only Chancellor sees."""
        state = create_game(tuple(range(1, 8)), seed=42)
        president = state.players[state.president_index]
        chancellor_uid = state.players[
            (state.president_index + 1) % len(state.players)
        ].uid
        bystander_uid = state.players[
            (state.president_index + 2) % len(state.players)
        ].uid
        policies_3 = (PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST)
        policies_2 = (PolicyTile.FASCIST, PolicyTile.LIBERAL)

        # PRESIDENT_DISCARD
        state_pd = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            chancellor=chancellor_uid,
            drawn_policies=policies_3,
        )
        self.assertEqual(
            scrub_state(state_pd, president.uid).drawn_policies, policies_3
        )
        self.assertEqual(scrub_state(state_pd, chancellor_uid).drawn_policies, ())
        self.assertEqual(scrub_state(state_pd, bystander_uid).drawn_policies, ())

        # POLICY_PEEK
        state_pp = replace(
            state,
            phase=GamePhase.CLAIM_POLICY_PEEK,
            chancellor=chancellor_uid,
            drawn_policies=policies_3,
        )
        self.assertEqual(
            scrub_state(state_pp, president.uid).drawn_policies, policies_3
        )
        self.assertEqual(scrub_state(state_pp, chancellor_uid).drawn_policies, ())
        self.assertEqual(scrub_state(state_pp, bystander_uid).drawn_policies, ())

        # CHANCELLOR_ENACT
        state_ce = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            chancellor=chancellor_uid,
            drawn_policies=policies_2,
        )
        self.assertEqual(
            scrub_state(state_ce, chancellor_uid).drawn_policies, policies_2
        )
        self.assertEqual(scrub_state(state_ce, president.uid).drawn_policies, ())
        self.assertEqual(scrub_state(state_ce, bystander_uid).drawn_policies, ())

    def test_scrub_state_rng_state(self):
        """Ensure that the rng_state is scrubbed to prevent predicting future draws."""
        state = create_game(tuple(range(1, 8)), seed=42)
        uid = state.players[0].uid

        scrubbed = scrub_state(state, uid)

        self.assertIs(scrubbed.rng_state, HIDDEN)


class TestPowerCleanup(BaseGameStateTest):
    def test_acknowledge_investigation_power_cleanup(self):
        """Verifies that acknowledge_investigation resets active_power to NONE."""
        state = create_game(tuple(range(1, 8)), seed=42)
        state = replace(
            state,
            phase=GamePhase.CLAIM_INVESTIGATION,
            active_power=PresidentialPower.INVESTIGATE_LOYALTY,
        )
        new_state = acknowledge_investigation(state)
        self.assertEqual(new_state.active_power, PresidentialPower.NONE)

    def test_call_special_election_power_cleanup(self):
        """Verifies that call_special_election resets active_power to NONE."""
        state = create_game(tuple(range(1, 8)), seed=42)
        state = replace(
            state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.CALL_SPECIAL_ELECTION,
        )
        target_uid = state.players[(state.president_index + 1) % len(state.players)].uid
        new_state = call_special_election(state, target_uid)
        self.assertEqual(new_state.active_power, PresidentialPower.NONE)

    def test_claim_peek_power_cleanup(self):
        """Verifies that claim_peek resets active_power to NONE."""
        state = create_game(tuple(range(1, 8)), seed=42)
        state = replace(
            state,
            phase=GamePhase.CLAIM_POLICY_PEEK,
            active_power=PresidentialPower.POLICY_PEEK,
        )
        claim = PeekClaim(
            uid=state.players[state.president_index].uid,
            policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        new_state = claim_peek(state, claim)
        self.assertEqual(new_state.active_power, PresidentialPower.NONE)

    def test_execute_player_power_cleanup(self):
        """Verifies that execute_player resets active_power to NONE."""
        state = create_game(tuple(range(1, 8)), seed=42)
        state = replace(
            state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.EXECUTION,
        )
        target_uid = state.players[(state.president_index + 1) % len(state.players)].uid
        new_state = execute_player(state, target_uid)
        self.assertEqual(new_state.active_power, PresidentialPower.NONE)


if __name__ == "__main__":
    unittest.main()
