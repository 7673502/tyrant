from dataclasses import dataclass, replace
from random import Random
from typing import Final

from tyrant.models.ballot_box import BallotBox, submit_vote
from tyrant.models.board import Board, play_tile
from tyrant.models.deck import (
    Deck,
    create_deck,
    discard_policies,
    draw_policies,
    shuffle_deck,
    top_deck,
)
from tyrant.models.election_tracker import ElectionTracker, increment_election_tracker
from tyrant.models.enums import (
    GamePhase,
    Party,
    PolicyTile,
    PresidentialPower,
    Role,
    Vote,
)
from tyrant.models.player import Player

ROLE_DISTRIBUTION: Final[frozendict[int, tuple[int, int]]] = frozendict(
    {5: (3, 2), 6: (4, 2), 7: (4, 3), 8: (5, 3), 9: (5, 4), 10: (6, 4)}
)


@dataclass(frozen=True)
class GameState:
    players: tuple[Player, ...]
    board: Board
    deck: Deck
    election_tracker: ElectionTracker
    phase: GamePhase
    president_index: int
    nominated_chancellor: int | None
    ballot_box: BallotBox
    drawn_policies: tuple[PolicyTile, ...]
    previous_president: int | None
    previous_chancellor: int | None
    winner: Party | None
    special_election_president: int | None
    rng_state: tuple[int, tuple[int, ...], float | None]
    veto_denied_this_term: bool = False
    investigations: frozendict[int, int] = frozendict()


def create_game(uids: tuple[int, ...], seed: int = 42) -> GameState:
    player_count = len(uids)
    if not (5 <= player_count <= 10):
        raise ValueError(f"Player count must be between 5 and 10, got {player_count}")
    if len(uids) != len(set(uids)):
        raise ValueError("Player UIDs must be unique")

    num_liberals, num_fascists = ROLE_DISTRIBUTION[player_count]

    roles_pool = (
        [Role.HITLER]
        + [Role.FASCIST] * (num_fascists - 1)
        + [Role.LIBERAL] * num_liberals
    )
    rng = Random(seed)
    rng.shuffle(roles_pool)

    players_list = []
    for uid, role in zip(uids, roles_pool):
        party = Party.FASCIST if role in (Role.FASCIST, Role.HITLER) else Party.LIBERAL
        players_list.append(Player(uid=uid, party=party, role=role))

    rng.shuffle(players_list)

    return GameState(
        players=tuple(players_list),
        board=Board(player_count=player_count),
        deck=create_deck(rng),
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
        rng_state=rng.getstate(),
        veto_denied_this_term=False,
        investigations=frozendict(),
    )


def _advance_to_nomination(state: GameState) -> GameState:
    new_special = state.special_election_president
    new_president_index = state.president_index

    entering_special_election = (
        state.special_election_president is not None
        and state.phase == GamePhase.PRESIDENTIAL_POWER
    )

    if entering_special_election:
        pass
    else:
        new_special = None
        new_president_index = (state.president_index + 1) % len(state.players)

        while not state.players[new_president_index].is_alive:
            new_president_index = (new_president_index + 1) % len(state.players)

    return replace(
        state,
        president_index=new_president_index,
        special_election_president=new_special,
        phase=GamePhase.NOMINATION,
        ballot_box=BallotBox(),
        veto_denied_this_term=False,
        nominated_chancellor=None,
    )


def nominate_chancellor(state: GameState, chancellor_uid: int) -> GameState:
    if state.phase != GamePhase.NOMINATION:
        raise ValueError(f"Cannot nominate chancellor in phase {state.phase}")

    president = state.players[state.president_index]
    if chancellor_uid == president.uid:
        raise ValueError("President cannot nominate themselves")

    chancellor = next((p for p in state.players if p.uid == chancellor_uid), None)
    if chancellor is None:
        raise ValueError(f"Player with UID {chancellor_uid} not found")

    if not chancellor.is_alive:
        raise ValueError("Cannot nominate a dead player")

    alive_count = sum(1 for p in state.players if p.is_alive)
    if alive_count > 6:
        if chancellor_uid in (state.previous_president, state.previous_chancellor):
            raise ValueError(
                "Target cannot be previous president or chancellor when > 6 players are alive"
            )
    else:
        if chancellor_uid == state.previous_chancellor:
            raise ValueError(
                "Target cannot be previous chancellor when <= 6 players are alive"
            )

    return replace(state, nominated_chancellor=chancellor_uid, phase=GamePhase.VOTING)


def _resolve_election(state: GameState) -> GameState:
    rng = Random()
    rng.setstate(state.rng_state)

    ja_votes = sum(1 for v in state.ballot_box.votes.values() if v == Vote.JA)
    nein_votes = sum(1 for v in state.ballot_box.votes.values() if v == Vote.NEIN)

    if ja_votes > nein_votes:
        chancellor_uid = state.nominated_chancellor
        chancellor = next(p for p in state.players if p.uid == chancellor_uid)

        if state.board.hitler_zone and chancellor.role == Role.HITLER:
            return replace(
                state,
                winner=Party.FASCIST,
                phase=GamePhase.GAME_OVER,
                rng_state=rng.getstate(),
            )

        new_deck, drawn = draw_policies(state.deck)

        return replace(
            state,
            deck=new_deck,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=drawn,
            election_tracker=ElectionTracker(failed_elections=0),
            previous_president=state.players[state.president_index].uid,
            previous_chancellor=chancellor_uid,
            rng_state=rng.getstate(),
        )
    else:
        new_tracker, triggered_top_deck = increment_election_tracker(
            state.election_tracker
        )

        if triggered_top_deck:
            new_deck, tile = top_deck(state.deck)
            new_board, _ = play_tile(state.board, tile)

            new_deck, _ = shuffle_deck(new_deck, rng)

            new_state = replace(
                state,
                election_tracker=new_tracker,
                deck=new_deck,
                board=new_board,
                previous_president=None,
                previous_chancellor=None,
                rng_state=rng.getstate(),
            )

            if new_board.winner is not None:
                return replace(
                    new_state, winner=new_board.winner, phase=GamePhase.GAME_OVER
                )

            return _advance_to_nomination(new_state)
        else:
            new_state = replace(
                state, election_tracker=new_tracker, rng_state=rng.getstate()
            )
            return _advance_to_nomination(new_state)


def cast_vote(state: GameState, uid: int, vote: Vote) -> GameState:
    if state.phase != GamePhase.VOTING:
        raise ValueError(f"Cannot cast vote in phase {state.phase}")

    player = next((p for p in state.players if p.uid == uid), None)
    if player is None:
        raise ValueError(f"Player with UID {uid} not found")

    if not player.is_alive:
        raise ValueError("Cannot vote when dead")

    new_ballot_box = submit_vote(state.ballot_box, uid, vote)
    new_state = replace(state, ballot_box=new_ballot_box)

    alive_count = sum(1 for p in state.players if p.is_alive)
    if new_ballot_box.vote_count == alive_count:
        return _resolve_election(new_state)

    return new_state


def president_discard(state: GameState, discard_index: int) -> GameState:
    if state.phase != GamePhase.PRESIDENT_DISCARD:
        raise ValueError(f"Cannot discard in phase {state.phase}")

    if not (0 <= discard_index < len(state.drawn_policies)):
        raise ValueError(f"Invalid discard index: {discard_index}")

    discarded_tile = state.drawn_policies[discard_index]
    remaining_policies = tuple(
        p for i, p in enumerate(state.drawn_policies) if i != discard_index
    )

    new_deck = discard_policies(state.deck, discarded_tile)

    return replace(
        state,
        deck=new_deck,
        drawn_policies=remaining_policies,
        phase=GamePhase.CHANCELLOR_ENACT,
    )


def chancellor_enact(state: GameState, enact_index: int) -> GameState:
    if state.phase != GamePhase.CHANCELLOR_ENACT:
        raise ValueError(f"Cannot enact in phase {state.phase}")

    if not (0 <= enact_index < len(state.drawn_policies)):
        raise ValueError(f"Invalid enact index: {enact_index}")

    enacted_tile = state.drawn_policies[enact_index]
    discard_index = 1 - enact_index
    discarded_tile = state.drawn_policies[discard_index]

    new_board, power = play_tile(state.board, enacted_tile)
    new_deck = discard_policies(state.deck, discarded_tile)

    rng = Random()
    rng.setstate(state.rng_state)
    new_deck, _ = shuffle_deck(new_deck, rng)

    new_state = replace(
        state,
        board=new_board,
        deck=new_deck,
        drawn_policies=(),
        rng_state=rng.getstate(),
    )

    if new_board.winner is not None:
        return replace(new_state, phase=GamePhase.GAME_OVER, winner=new_board.winner)

    if enacted_tile == PolicyTile.LIBERAL or power == PresidentialPower.NONE:
        return _advance_to_nomination(new_state)
    else:
        return replace(new_state, phase=GamePhase.PRESIDENTIAL_POWER)


def chancellor_veto(state: GameState) -> GameState:
    if state.phase != GamePhase.CHANCELLOR_ENACT:
        raise ValueError(f"Cannot veto in phase {state.phase}")

    if not state.board.veto_power_unlocked:
        raise ValueError("Veto power is not unlocked")

    if state.veto_denied_this_term:
        raise ValueError("Veto has already been denied this term")

    return replace(state, phase=GamePhase.PRESIDENT_VETO_RESPONSE)
