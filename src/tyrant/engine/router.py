from tyrant.exceptions import TyrantError
from tyrant.models.action import Action
from tyrant.models.enums import GamePhase, PresidentialPower, Vote
from tyrant.models.game_state import (
    GameState,
    acknowledge_investigation,
    acknowledge_peek,
    call_special_election,
    cast_vote,
    chancellor_enact,
    chancellor_veto,
    execute_player,
    investigate_loyalty,
    nominate_chancellor,
    policy_peek,
    president_discard,
    president_veto_response,
)


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
    if player_uid != state.chancellor:
        return tuple()

    actions: list[Action] = []
    for i, policy in enumerate(state.drawn_policies):
        actions.append(
            Action(id=f"enact_{i}", description=f"Enact {policy.name.title()}")
        )

    if state.board.veto_power_unlocked:
        actions.append(Action(id="veto", description="Veto Policies"))

    return tuple(actions)


def _get_legal_actions_investigate_loyalty(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    actions: list[Action] = []
    for p in state.players:
        if p.is_alive and p.uid != player_uid and p.uid not in state.investigations:
            actions.append(
                Action(
                    id=f"investigate_{p.uid}", description=f"Investigate Player {p.uid}"
                )
            )
    return tuple(actions)


def _get_legal_actions_call_special_election(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    actions: list[Action] = []
    for p in state.players:
        if p.is_alive and p.uid != player_uid:
            actions.append(
                Action(
                    id=f"special_{p.uid}",
                    description=f"Special Elect Player {p.uid}",
                )
            )
    return tuple(actions)


def _get_legal_actions_execution(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    actions: list[Action] = []
    for p in state.players:
        if p.is_alive and p.uid != player_uid:
            actions.append(
                Action(id=f"execute_{p.uid}", description=f"Execute Player {p.uid}")
            )
    return tuple(actions)


def _get_legal_actions_presidential_power(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    president_uid = state.players[state.president_index].uid
    if president_uid != player_uid:
        return tuple()

    match state.active_power:
        case PresidentialPower.POLICY_PEEK:
            return (Action(id="peek", description="Peek Top 3 Policies"),)
        case PresidentialPower.INVESTIGATE_LOYALTY:
            return _get_legal_actions_investigate_loyalty(state, player_uid)
        case PresidentialPower.CALL_SPECIAL_ELECTION:
            return _get_legal_actions_call_special_election(state, player_uid)
        case PresidentialPower.EXECUTION:
            return _get_legal_actions_execution(state, player_uid)
        case PresidentialPower.NONE:
            raise TyrantError(
                "Entered PRESIDENTIAL_POWER phase but active_power is NONE"
            )


def _get_legal_actions_acknowledge_investigation(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    if player_uid != state.players[state.president_index].uid:
        return tuple()
    return (
        Action(
            id="acknowledge_investigation",
            description="Done Reading Party Identity of Investigated Player",
        ),
    )


def _get_legal_actions_acknowledge_peek(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    if player_uid != state.players[state.president_index].uid:
        return tuple()
    return (Action(id="acknowledge_peek", description="Done Reading Top 3 Cards"),)


def _get_legal_actions_president_veto_response(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    if player_uid != state.players[state.president_index].uid:
        return tuple()

    return (
        Action(id="accept_veto", description="Agree to Veto the Chancellor's Policies"),
        Action(
            id="decline_veto", description="Decline to Veto the Chancellor's Policies"
        ),
    )


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
        case GamePhase.INVESTIGATION:
            return _get_legal_actions_acknowledge_investigation(state, player_uid)
        case GamePhase.POLICY_PEEK:
            return _get_legal_actions_acknowledge_peek(state, player_uid)
        case GamePhase.PRESIDENT_VETO_RESPONSE:
            return _get_legal_actions_president_veto_response(state, player_uid)
        case _:  # no actions available during SETUP and GAME_OVER
            return tuple()


def apply_action(state: GameState, action: Action, player_uid: int) -> GameState:
    parts = action.id.split("_")

    match parts:
        case ["nominate", target_str]:
            chancellor_uid = int(target_str)
            return nominate_chancellor(state, chancellor_uid)
        case ["vote", vote_type]:
            vote = Vote.JA if vote_type == "ja" else Vote.NEIN
            return cast_vote(state, player_uid, vote)
        case ["discard", index_str]:
            discard_index = int(index_str)
            return president_discard(state, discard_index)
        case ["enact", index_str]:
            enact_index = int(index_str)
            return chancellor_enact(state, enact_index)
        case ["veto"]:
            return chancellor_veto(state)
        case ["investigate", target_str]:
            target_uid = int(target_str)
            return investigate_loyalty(state, target_uid)
        case ["special", target_str]:
            target_uid = int(target_str)
            return call_special_election(state, target_uid)
        case ["execute", target_str]:
            target_uid = int(target_str)
            return execute_player(state, target_uid)
        case ["peek"]:
            return policy_peek(state)
        case ["acknowledge", "peek"]:
            return acknowledge_peek(state)
        case ["acknowledge", "investigation"]:
            return acknowledge_investigation(state)
        case [veto_str, "veto"]:
            approve = veto_str == "accept"
            return president_veto_response(state, approve)
        case _:
            raise TyrantError(f"Unrecognized action ID format: {action.id}")
