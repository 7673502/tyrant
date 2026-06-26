from dataclasses import dataclass, replace
from random import Random
from typing import Final

from tyrant.models.enums import GamePhase, Party, Role, PolicyTile
from tyrant.models.player import Player
from tyrant.models.board import Board
from tyrant.models.deck import Deck, create_deck
from tyrant.models.election_tracker import ElectionTracker
from tyrant.models.ballot_box import BallotBox

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
    veto_denied_this_term: bool = False
    investigations: frozendict[int, int] = frozendict()


def create_game(uids: tuple[int, ...], rng: Random) -> GameState:
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
