import itertools
from typing import Final

from tyrant.engine.renderer import format_hand
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
    CorrectClaimAction,
    ExecutionAction,
    InvestigateLoyaltyAction,
    NominateAction,
    PassAction,
    PolicyPeekAction,
    PresidentDiscardAction,
    PresidentVetoResponseAction,
    SpeakAction,
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
    correct_claim,
    correctable_claim,
    execute_player,
    investigate_loyalty,
    nominate_chancellor,
    policy_peek,
    president_discard,
    president_veto_response,
    speak,
    term_limited,
)
from tyrant.models.knowledge import (
    ChancellorReceiveKnowledge,
    PresidentDiscardKnowledge,
)

TILES: Final = (PolicyTile.FASCIST, PolicyTile.LIBERAL)


def _get_legal_actions_nomination(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    """Returns the president's nominations, leaving out dead and term-limited players."""
    president_uid = state.players[state.president_index].uid
    if player_uid != president_uid:
        return tuple()

    actions: list[Action] = []
    limited = term_limited(state)

    for p in state.players:
        if not p.is_alive:
            continue
        if p.uid == player_uid:
            continue
        if p.uid in limited:
            continue

        actions.append(
            NominateAction(description=f"Nominate Player {p.uid}", target_uid=p.uid)
        )

    return tuple(actions)


def _get_legal_actions_discussion(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    """Returns a speak and a pass action for the current speaker, then any claim corrections they may make."""
    if state.discussion is None or player_uid != state.discussion.current_speaker:
        return tuple()

    return (
        SpeakAction(description="Say something new to the table"),
        PassAction(
            description="Stay silent (choose this if you would repeat an earlier point)"
        ),
    ) + _get_legal_actions_corrections(state, player_uid)


def _get_legal_actions_corrections(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    """Returns every other non-decline policy claim the player may correct their latest claim to, the truthful one first."""
    event = correctable_claim(state, player_uid)
    if event is None:
        return tuple()

    claim = event.claim
    if isinstance(claim, PresidentEnactClaim):
        truth = _president_truth(state, player_uid)
        return tuple(
            CorrectClaimAction(
                description=_correction_description(
                    _president_claim(policies, discarded),
                    (policies, discarded) == truth,
                ),
                claim=PresidentEnactClaim(
                    uid=player_uid, policies=policies, discarded=discarded
                ),
            )
            for policies, discarded in _president_claims(truth)
            if (policies, discarded) != (claim.policies, claim.discarded)
        )

    truth = _chancellor_truth(state, player_uid)
    return tuple(
        CorrectClaimAction(
            description=_correction_description(
                f"you received {format_hand(policies)}", policies == truth
            ),
            claim=ChancellorEnactClaim(uid=player_uid, policies=policies),
        )
        for policies in _chancellor_claims(truth)
        if policies != claim.policies
    )


def _get_legal_actions_voting(state: GameState, player_uid: int) -> tuple[Action, ...]:
    """Returns a ja and a nein vote for a player who has not voted yet."""
    if player_uid in state.ballot_box.votes:
        return tuple()

    return (
        VoteAction(description="Vote JA", vote=Vote.JA),
        VoteAction(description="Vote NEIN", vote=Vote.NEIN),
    )


def _get_legal_actions_president_discard(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    """Returns one discard action per drawn policy for the president."""
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
    """Returns one enact action per received policy for the chancellor, plus a veto when allowed."""
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
    """Returns one investigation per other living player who has not been investigated."""
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
    """Returns one special election per other living player."""
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
    """Returns one execution per other living player."""
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
    """Returns the president's actions for the active presidential power."""
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


def _claim_description(claim: str, is_truth: bool) -> str:
    """Returns an option's description, labelled as the truth or as a lie."""
    return f"Tell the truth: {claim}." if is_truth else f"Lie: claim {claim}."


def _correction_description(claim: str, is_truth: bool) -> str:
    """Returns a correction option's description, labelled as the truth or as a lie."""
    return f"Correct your claim ({'truth' if is_truth else 'lie'}): {claim}."


def _president_truth(
    state: GameState, player_uid: int
) -> tuple[tuple[PolicyTile, ...], PolicyTile] | None:
    """Returns the policies the player last drew as president, in canonical order, and the one they discarded."""
    return next(
        (
            (tuple(sorted((k.discarded, *k.passed))), k.discarded)
            for k in reversed(state.knowledge)
            if isinstance(k, PresidentDiscardKnowledge) and k.uid == player_uid
        ),
        None,
    )


def _chancellor_truth(
    state: GameState, player_uid: int
) -> tuple[PolicyTile, ...] | None:
    """Returns the policies the player last received as chancellor, in canonical order."""
    return next(
        (
            tuple(sorted(k.policies))
            for k in reversed(state.knowledge)
            if isinstance(k, ChancellorReceiveKnowledge) and k.uid == player_uid
        ),
        None,
    )


def _president_claims(
    truth: tuple[tuple[PolicyTile, ...], PolicyTile] | None,
) -> list[tuple[tuple[PolicyTile, ...], PolicyTile]]:
    """Returns every non-decline president claim as drawn policies and a discard, the truthful one first."""
    claims = [
        (policies, discarded)
        for policies in itertools.combinations_with_replacement(TILES, 3)
        for discarded in dict.fromkeys(policies)
    ]
    return sorted(claims, key=lambda c: c != truth)


def _chancellor_claims(
    truth: tuple[PolicyTile, ...] | None,
) -> list[tuple[PolicyTile, ...]]:
    """Returns every non-decline chancellor claim, the truthful one first."""
    claims = itertools.combinations_with_replacement(TILES, 2)
    return sorted(claims, key=lambda c: c != truth)


def _president_claim(
    policies: tuple[PolicyTile, PolicyTile, PolicyTile], discarded: PolicyTile
) -> str:
    """Returns what a president's enact claim says, including the two policies it implies were passed."""
    passed = list(policies)
    passed.remove(discarded)
    return (
        f"you drew {format_hand(policies)} and discarded {discarded}, "
        f"so you passed {format_hand(passed)}"
    )


def _get_legal_actions_claim_investigation(
    state: GameState, player_uid: int
) -> tuple[Action, ...]:
    """Returns the president's truthful party claim about an investigation first, then the lie, then a decline."""
    if player_uid != state.players[state.president_index].uid:
        return tuple()
    truth = state.current_investigation_result
    actions: list[Action] = []
    for party in sorted((Party.LIBERAL, Party.FASCIST), key=lambda p: p != truth):
        actions.append(
            ClaimInvestigationAction(
                description=_claim_description(
                    f"the investigated player is a {party.title()}", party == truth
                ),
                claim_party=party,
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
    """Returns every ordered peek claim for the president, the truthful one first, plus a decline."""
    if player_uid != state.players[state.president_index].uid:
        return tuple()

    truth = state.drawn_policies
    claims = itertools.product((PolicyTile.LIBERAL, PolicyTile.FASCIST), repeat=3)
    actions: list[Action] = []
    for policies in sorted(claims, key=lambda c: c != truth):
        actions.append(
            ClaimPolicyPeekAction(
                description=_claim_description(
                    f"the top 3 policies are, from the top, {', '.join(policies)}",
                    policies == truth,
                ),
                claim_policies=policies,
            )
        )
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
    """Returns the pending policy claims for the president or chancellor, the truthful one first and a decline last."""
    actions: list[Action] = []

    president_uid = state.players[state.president_index].uid
    if player_uid == president_uid and state.pending_president_enact_claim:
        truth = _president_truth(state, player_uid)
        for policies, discarded in _president_claims(truth):
            actions.append(
                ClaimPresidentEnactAction(
                    description=_claim_description(
                        _president_claim(policies, discarded),
                        (policies, discarded) == truth,
                    ),
                    claim_policies=policies,
                    claim_discarded=discarded,
                )
            )
        actions.append(
            ClaimPresidentEnactAction(
                description="Decline to share the drawn policies", claim_policies=None
            )
        )

    chancellor_uid = state.chancellor
    if player_uid == chancellor_uid and state.pending_chancellor_enact_claim:
        truth = _chancellor_truth(state, player_uid)
        for policies in _chancellor_claims(truth):
            actions.append(
                ClaimChancellorEnactAction(
                    description=_claim_description(
                        f"you received {format_hand(policies)}", policies == truth
                    ),
                    claim_policies=policies,
                )
            )
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
    """Returns the president's approve and refuse responses to a veto proposal."""
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
    """Lists the actions a player may take now.

    Args:
        state: The current game state.
        player_uid: UID of the player.

    Returns:
        The legal actions, or an empty tuple if the player is dead or not due to act.

    Raises:
        TyrantError: If the player is not in the game.
    """
    player = next((p for p in state.players if p.uid == player_uid), None)
    if player is None:
        raise TyrantError(f"Player with UID {player_uid} not found")
    if not player.is_alive:
        return tuple()

    match state.phase:
        case GamePhase.NOMINATION:
            return _get_legal_actions_nomination(state, player_uid)
        case GamePhase.DISCUSSION:
            return _get_legal_actions_discussion(state, player_uid)
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
    """Applies a player's action to the game.

    Args:
        state: The full game state.
        action: The action to apply, usually one returned by `get_legal_actions`.
        player_uid: UID of the acting player.

    Returns:
        The new game state.

    Raises:
        InvalidMoveError: If the action is not legal in this state.
        TyrantError: If the action type is not recognized.
    """
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
        case ClaimPresidentEnactAction(
            claim_policies=policies, claim_discarded=discarded
        ):
            claim = PresidentEnactClaim(
                uid=player_uid, policies=policies, discarded=discarded
            )
            return claim_enact(state, claim)
        case ClaimChancellorEnactAction(claim_policies=policies):
            claim = ChancellorEnactClaim(uid=player_uid, policies=policies)
            return claim_enact(state, claim)
        case ClaimInvestigationAction(claim_party=party):
            claim = InvestigationClaim(uid=player_uid, party=party)
            return claim_investigation(state, claim)
        case PresidentVetoResponseAction(approve=approve):
            return president_veto_response(state, approve)
        case SpeakAction(message=message):
            return speak(state, player_uid, message)
        case PassAction():
            return speak(state, player_uid, None)
        case CorrectClaimAction(claim=claim):
            return correct_claim(state, player_uid, claim)
        case _:
            raise TyrantError(f"Unrecognized action type: {type(action).__name__}")
