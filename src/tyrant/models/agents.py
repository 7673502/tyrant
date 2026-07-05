from dataclasses import dataclass
from typing import Protocol

from tyrant.exceptions import TyrantError
from tyrant.models.enums import GamePhase
from tyrant.models.game_state import GameState


@dataclass(frozen=True)
class Action:
    id: str
    description: str


class Agent(Protocol):
    player_uid: int

    def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> str: ...


def _get_legal_actions_nomination(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    president_uid = state.players[state.president_index].uid
    if player_uid != president_uid:
        return tuple()

    actions: list[Action] = []
    alive_count = sum(1 for p in state.players if p.is_alive)

    for p in state.players:
        if not p.is_alive:
            continue
        if p.uid == player_uid:
            continue
        if alive_count > 5 and p.uid == state.previous_president:
            continue
        if p.uid == state.previous_chancellor:
            continue

        actions.append(
            Action(id=f"nominate_{p.uid}", description=f"Nominate Player {p.uid}")
        )

    return tuple(actions)


def _get_legal_actions_voting(state: GameState, player_uid: int) -> tuple[Action, ...]:
    if player_uid in state.ballot_box.votes:
        return tuple()

    return (
        Action(id="vote_ja", description="Vote JA"),
        Action(id="vote_nein", description="Vote NEIN"),
    )


def _get_legal_actions_president_discard(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    president_uid = state.players[state.president_index].uid
    if player_uid != president_uid:
        return tuple()

    actions: list[Action] = []
    for i, policy in enumerate(state.drawn_policies):
        actions.append(
            Action(id=f"discard_{i}", description=f"Discard {policy.name.title()}")
        )

    return tuple(actions)


def _get_legal_actions_chancellor_enact(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    if player_uid != state.nominated_chancellor:
        return tuple()

    actions: list[Action] = []
    for i, policy in enumerate(state.drawn_policies):
        actions.append(
            Action(id=f"enact_{i}", description=f"Enact {policy.name.title()}")
        )

    if state.board.veto_power_unlocked:
        actions.append(Action(id="veto", description="Veto Policies"))

    return tuple(actions)


def _get_legal_actions_presidential_power(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    return tuple()  # TODO


def _get_legal_actions_policy_peek(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    return tuple()  # TODO


def _get_legal_actions_president_veto_response(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    return tuple()  # TODO


def get_legal_actions(state: GameState, player_uid: int) -> tuple[Action, ...]:
    player = next((p for p in state.players if p.uid == player_uid), None)
    if player is None:
        raise TyrantError(f"Player with UID {player_uid} not found")
    if not player.is_alive:
        return tuple()

    match state.phase:
        case GamePhase.NOMINATION:
            return _get_legal_actions_nomination(state, player_uid)
        case GamePhase.VOTING:
            return _get_legal_actions_voting(state, player_uid)
        case GamePhase.PRESIDENT_DISCARD:
            return _get_legal_actions_president_discard(state, player_uid)
        case GamePhase.CHANCELLOR_ENACT:
            return _get_legal_actions_chancellor_enact(state, player_uid)
        case GamePhase.PRESIDENTIAL_POWER:
            return _get_legal_actions_presidential_power(state, player_uid)
        case GamePhase.POLICY_PEEK:
            return _get_legal_actions_policy_peek(state, player_uid)
        case GamePhase.PRESIDENT_VETO_RESPONSE:
            return _get_legal_actions_president_veto_response(state, player_uid)
        case _:  # no actions available during SETUP and GAME_OVER
            return tuple()
