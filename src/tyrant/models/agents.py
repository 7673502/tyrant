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
    if not any(p.uid == player_uid for p in state.players):
        raise TyrantError(f"Player with UID {player_uid} not found")

    president = state.players[state.president_index]
    if player_uid != president.uid:
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


def get_legal_actions(state: GameState, player_uid: int) -> tuple[Action, ...]:
    # TODO
    match state.phase:
        case GamePhase.NOMINATION:
            return _get_legal_actions_nomination(state, player_uid)
        case GamePhase.VOTING:
            pass
        case GamePhase.PRESIDENT_DISCARD:
            pass
        case GamePhase.CHANCELLOR_ENACT:
            pass
        case GamePhase.PRESIDENTIAL_POWER:
            pass
        case GamePhase.POLICY_PEEK:
            pass
        case GamePhase.PRESIDENT_VETO_RESPONSE:
            pass
        case _:  # no actions available during SETUP and GAME_OVER
            return tuple()
    raise NotImplementedError()
