import itertools
from typing import Final

from tyrant.exceptions import TyrantError
from tyrant.models.action import (
    Action,
    CallSpecialElectionAction,
    ChancellorEnactAction,
    ChancellorVetoAction,
    ClaimChancellorEnactAction,
    ClaimInvestigationAction,
    ClaimPolicyPeekAction,
    ClaimPresidentEnactAction,
    ExecutionAction,
    InvestigateLoyaltyAction,
    NominateAction,
    PolicyPeekAction,
    PresidentDiscardAction,
    PresidentVetoResponseAction,
    VoteAction,
)
from tyrant.models.claim import (
    ChancellorEnactClaim,
    InvestigationClaim,
    PeekClaim,
    PresidentEnactClaim,
)
from tyrant.models.enums import GamePhase, Party, PolicyTile, PresidentialPower, Vote
from tyrant.models.game_state import (
    GameState,
    call_special_election,
    cast_vote,
    chancellor_enact,
    chancellor_veto,
    claim_enact,
    claim_investigation,
    claim_peek,
    execute_player,
    investigate_loyalty,
    nominate_chancellor,
    policy_peek,
    president_discard,
    president_veto_response,
)

TILE_MAP: Final = {"L": PolicyTile.LIBERAL, "F": PolicyTile.FASCIST}


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
            NominateAction(description=f"Nominate Player {p.uid}", target_uid=p.uid)
        )

    return tuple(actions)


def _get_legal_actions_voting(state: GameState, player_uid: int) -> tuple[Action, ...]:
    if player_uid in state.ballot_box.votes:
        return tuple()

    return (
        VoteAction(description="Vote JA", vote=Vote.JA),
        VoteAction(description="Vote NEIN", vote=Vote.NEIN),
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
            PresidentDiscardAction(
                description=f"Discard {policy.name.title()}", target_index=i
            )
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
            ChancellorEnactAction(
                description=f"Enact {policy.name.title()}", target_index=i
            )
        )

    if state.board.veto_power_unlocked and not state.veto_denied_this_term:
        actions.append(ChancellorVetoAction(description="Veto Policies"))

    return tuple(actions)


def _get_legal_actions_investigate_loyalty(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    actions: list[Action] = []
    for p in state.players:
        if p.is_alive and p.uid != player_uid and p.uid not in state.investigations:
            actions.append(
                InvestigateLoyaltyAction(
                    description=f"Investigate Player {p.uid}", target_uid=p.uid
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
                CallSpecialElectionAction(
                    description=f"Special Elect Player {p.uid}", target_uid=p.uid
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
                ExecutionAction(description=f"Execute Player {p.uid}", target_uid=p.uid)
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
            return (PolicyPeekAction(description="Peek Top 3 Policies"),)
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


def _get_legal_actions_claim_investigation(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    if player_uid != state.players[state.president_index].uid:
        return tuple()
    actions: list[Action] = []
    for party in ("Liberal", "Fascist"):
        party_enum = Party.LIBERAL if party == "Liberal" else Party.FASCIST
        actions.append(
            ClaimInvestigationAction(
                description=f"Claim that the investigated player is a {party}",
                claim_party=party_enum,
            )
        )
    actions.append(
        ClaimInvestigationAction(
            description="Decline to share the investigated player's party loyalty",
            claim_party=None,
        )
    )

    return tuple(actions)


def _get_legal_actions_claim_peek(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    if player_uid != state.players[state.president_index].uid:
        return tuple()

    actions: list[Action] = []
    for claim in itertools.product(("Liberal", "Fascist"), repeat=3):
        policies = tuple(TILE_MAP[char[0]] for char in claim)
        action = ClaimPolicyPeekAction(
            description=f"For the peeked top 3 policies, claim that the top is {claim[0]}, middle is {claim[1]}, bottom is {claim[2]}",
            claim_policies=policies,
        )
        actions.append(action)
    actions.append(
        ClaimPolicyPeekAction(
            description="Decline to share the contents of the peeked top 3 cards",
            claim_policies=None,
        )
    )

    return tuple(actions)


def _get_legal_actions_enact_claims(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    actions: list[Action] = []

    president_uid = state.players[state.president_index].uid
    if player_uid == president_uid and state.pending_president_enact_claim:
        for claim in itertools.combinations_with_replacement(("Liberal", "Fascist"), 3):
            policies = tuple(TILE_MAP[char[0]] for char in claim)
            action = ClaimPresidentEnactAction(
                description=f"Claim that the 3 drawn policies were: {claim[0]}, {claim[1]}, {claim[2]}",
                claim_policies=policies,
            )
            actions.append(action)
        actions.append(
            ClaimPresidentEnactAction(
                description="Decline to share the drawn policies", claim_policies=None
            )
        )

    chancellor_uid = state.chancellor
    if player_uid == chancellor_uid and state.pending_chancellor_enact_claim:
        for claim in itertools.combinations_with_replacement(("Liberal", "Fascist"), 2):
            policies = tuple(TILE_MAP[char[0]] for char in claim)
            action = ClaimChancellorEnactAction(
                description=f"Claim that the 2 received policies were: {claim[0]}, {claim[1]}",
                claim_policies=policies,
            )
            actions.append(action)
        actions.append(
            ClaimChancellorEnactAction(
                description="Decline to share the received policies",
                claim_policies=None,
            )
        )

    return tuple(actions)


def _get_legal_actions_president_veto_response(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    if player_uid != state.players[state.president_index].uid:
        return tuple()

    return (
        PresidentVetoResponseAction(
            description="Agree to Veto the Chancellor's Policies", approve=True
        ),
        PresidentVetoResponseAction(
            description="Decline to Veto the Chancellor's Policies", approve=False
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
        case GamePhase.CLAIM_INVESTIGATION:
            return _get_legal_actions_claim_investigation(state, player_uid)
        case GamePhase.CLAIM_POLICY_PEEK:
            return _get_legal_actions_claim_peek(state, player_uid)
        case GamePhase.CLAIM_POLICIES:
            return _get_legal_actions_enact_claims(state, player_uid)
        case GamePhase.PRESIDENT_VETO_RESPONSE:
            return _get_legal_actions_president_veto_response(state, player_uid)
        case _:  # no actions available during SETUP and GAME_OVER
            return tuple()


def apply_action(state: GameState, action: Action, player_uid: int) -> GameState:
    match action:
        case NominateAction(target_uid=uid):
            return nominate_chancellor(state, uid)
        case VoteAction(vote=vote):
            return cast_vote(state, player_uid, vote)
        case PresidentDiscardAction(target_index=index):
            return president_discard(state, index)
        case ChancellorEnactAction(target_index=index):
            return chancellor_enact(state, index)
        case ChancellorVetoAction():
            return chancellor_veto(state)
        case InvestigateLoyaltyAction(target_uid=uid):
            return investigate_loyalty(state, uid)
        case CallSpecialElectionAction(target_uid=uid):
            return call_special_election(state, uid)
        case ExecutionAction(target_uid=uid):
            return execute_player(state, uid)
        case PolicyPeekAction():
            return policy_peek(state)
        case ClaimPolicyPeekAction(claim_policies=policies):
            claim = PeekClaim(uid=player_uid, policies=policies)
            return claim_peek(state, claim)
        case ClaimPresidentEnactAction(claim_policies=policies):
            claim = PresidentEnactClaim(uid=player_uid, policies=policies)
            return claim_enact(state, claim)
        case ClaimChancellorEnactAction(claim_policies=policies):
            claim = ChancellorEnactClaim(uid=player_uid, policies=policies)
            return claim_enact(state, claim)
        case ClaimInvestigationAction(claim_party=party):
            claim = InvestigationClaim(uid=player_uid, party=party)
            return claim_investigation(state, claim)
        case PresidentVetoResponseAction(approve=approve):
            return president_veto_response(state, approve)
        case _:
            raise TyrantError(f"Unrecognized action type: {type(action).__name__}")
