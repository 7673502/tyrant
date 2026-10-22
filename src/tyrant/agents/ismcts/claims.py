from tyrant.models.action import (
    Action,
    ClaimChancellorEnactAction,
    ClaimInvestigationAction,
    ClaimPolicyPeekAction,
    ClaimPresidentEnactAction,
)
from tyrant.models.enums import GamePhase, Party, PolicyTile
from tyrant.models.event import PolicyEnactedEvent, VetoEvent
from tyrant.models.game_state import GameState
from tyrant.models.knowledge import (
    ChancellorReceiveKnowledge,
    PresidentDiscardKnowledge,
    PresidentDrawKnowledge,
)


def claim_action(
    state: GameState, uid: int, valid_actions: tuple[Action, ...]
) -> Action:
    """Returns the claim a simple heuristic makes about what the player saw.

    Liberals always tell the truth. A fascist tells the truth unless it would expose a fascist choice: a president who discarded a liberal policy while holding a fascist one claims to have discarded a fascist policy, a chancellor who enacted a fascist policy while holding a liberal one claims two fascist policies, and a fascist investigator calls a fascist teammate liberal.

    Args:
        state: The game state, scrubbed for the player.
        uid: UID of the player making the claim.
        valid_actions: The claims the player may make now.

    Returns:
        One of `valid_actions`.
    """
    fascist = next(p.party for p in state.players if p.uid == uid) is Party.FASCIST
    match state.phase:
        case GamePhase.CLAIM_INVESTIGATION:
            party = Party.LIBERAL if fascist else state.current_investigation_result
            return next(
                a
                for a in valid_actions
                if isinstance(a, ClaimInvestigationAction) and a.claim_party == party
            )
        case GamePhase.CLAIM_POLICY_PEEK:
            return next(
                a
                for a in valid_actions
                if isinstance(a, ClaimPolicyPeekAction)
                and a.claim_policies == state.drawn_policies
            )

    if isinstance(valid_actions[0], ClaimPresidentEnactAction):
        drawn = next(
            k.policies
            for k in reversed(state.knowledge)
            if isinstance(k, PresidentDrawKnowledge)
        )
        discard = next(
            k
            for k in reversed(state.knowledge)
            if isinstance(k, PresidentDiscardKnowledge)
        )
        discarded = discard.discarded
        if fascist and discarded == PolicyTile.LIBERAL and PolicyTile.FASCIST in drawn:
            drawn = discard.passed + (PolicyTile.FASCIST,)
            discarded = PolicyTile.FASCIST
        return next(
            a
            for a in valid_actions
            if isinstance(a, ClaimPresidentEnactAction)
            and a.claim_policies == tuple(sorted(drawn))
            and a.claim_discarded == discarded
        )

    received = next(
        k.policies
        for k in reversed(state.knowledge)
        if isinstance(k, ChancellorReceiveKnowledge)
    )
    enacted = _enacted_policy(state)
    if fascist and enacted == PolicyTile.FASCIST and PolicyTile.LIBERAL in received:
        received = (PolicyTile.FASCIST, PolicyTile.FASCIST)
    return next(
        a
        for a in valid_actions
        if isinstance(a, ClaimChancellorEnactAction)
        and a.claim_policies == tuple(sorted(received))
    )


def _enacted_policy(state: GameState) -> PolicyTile | None:
    """Returns the policy the current government enacted, or `None` if it vetoed."""
    for event in reversed(state.events):
        match event:
            case PolicyEnactedEvent() if not event.top_deck:
                return event.policy
            case VetoEvent(approved=True):
                return None
