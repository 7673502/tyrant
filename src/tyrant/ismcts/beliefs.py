from itertools import combinations
from typing import Final

from frozendict import frozendict

from tyrant.models.board import HITLER_ZONE_COUNT
from tyrant.models.claim import ChancellorEnactClaim, PresidentEnactClaim
from tyrant.models.enums import HIDDEN, Party, PolicyTile, Role, Vote
from tyrant.models.event import (
    ClaimEvent,
    ElectionEvent,
    Event,
    ExecutionEvent,
    NominationEvent,
    PolicyEnactedEvent,
)
from tyrant.models.game_state import ROLE_DISTRIBUTION, GameState
from tyrant.models.knowledge import InvestigationKnowledge

FASCIST_GOVERNMENT_FASCIST_POLICY: Final = 0.9
"""Chance that a government with a fascist in it enacts a fascist policy."""

LIBERAL_GOVERNMENT_FASCIST_POLICY: Final = 0.25
"""Chance that an all-liberal government enacts a fascist policy."""

ALL_LIBERAL_CLAIM_CONFLICT: Final = 0.3
"""Chance that an all-liberal government makes conflicting policy claims."""

FASCIST_JA_FASCIST_GOVERNMENT: Final = 0.75
"""Chance that a fascist votes ja on a government with a fascist in it."""

FASCIST_JA_LIBERAL_GOVERNMENT: Final = 0.6
"""Chance that a fascist votes ja on an all-liberal government."""

LIBERAL_JA: Final = 0.6
"""Chance that a liberal votes ja on any government."""


def party_of(role: Role) -> Party:
    """Returns the party a role belongs to.

    Args:
        role: The role.

    Returns:
        `Party.FASCIST` for a fascist or Hitler, otherwise `Party.LIBERAL`.
    """
    return Party.FASCIST if role in (Role.FASCIST, Role.HITLER) else Party.LIBERAL


def role_assignments(
    state: GameState, viewer_uid: int
) -> tuple[frozendict[int, Role], ...]:
    """Lists every role deal that fits what the viewer knows for certain.

    A deal fits if it keeps every role and party the scrubbed state shows, every party the viewer investigated, and keeps Hitler away from players who were elected chancellor in the Hitler zone or executed.

    Args:
        state: The game state, scrubbed for the viewer.
        viewer_uid: UID of the viewer.

    Returns:
        Each fitting deal, mapping every player's UID to a role in seat order.
    """
    uids = tuple(p.uid for p in state.players)
    _, num_fascists = ROLE_DISTRIBUTION[len(uids)]
    roles = {p.uid: p.role for p in state.players if p.role is not HIDDEN}
    parties = {p.uid: p.party for p in state.players if p.party is not HIDDEN}
    for k in state.knowledge:
        if isinstance(k, InvestigationKnowledge) and k.uid == viewer_uid:
            parties[k.target_uid] = k.party
    not_hitler = _not_hitler(state.events)

    deals = []
    for hitler in uids:
        if hitler in not_hitler:
            continue
        others = tuple(uid for uid in uids if uid != hitler)
        for fascists in combinations(others, num_fascists - 1):
            deal = frozendict(
                {uid: Role.LIBERAL for uid in uids}
                | {uid: Role.FASCIST for uid in fascists}
                | {hitler: Role.HITLER}
            )
            if all(deal[uid] == role for uid, role in roles.items()) and all(
                party_of(deal[uid]) == party for uid, party in parties.items()
            ):
                deals.append(deal)
    return tuple(deals)


def _not_hitler(events: tuple[Event, ...]) -> frozenset[int]:
    """Returns the UIDs of players elected chancellor in the Hitler zone or executed, none of whom can be Hitler."""
    fascist_policies = 0
    uids = set()
    for event in events:
        match event:
            case PolicyEnactedEvent(policy=PolicyTile.FASCIST):
                fascist_policies += 1
            case ElectionEvent(result=Vote.JA) if fascist_policies >= HITLER_ZONE_COUNT:
                uids.add(event.chancellor_uid)
            case ExecutionEvent(target_uid=uid):
                uids.add(uid)
    return frozenset(uids)


def role_weights(
    state: GameState, assignments: tuple[frozendict[int, Role], ...]
) -> tuple[float, ...]:
    """Weighs each role deal by how well it explains the public events.

    Args:
        state: The game state, scrubbed for the viewer.
        assignments: The deals to weigh, as returned by `role_assignments`.

    Returns:
        One unnormalized weight per deal, in the same order.
    """
    return tuple(_likelihood(state.events, deal) for deal in assignments)


def _likelihood(events: tuple[Event, ...], deal: frozendict[int, Role]) -> float:
    """Returns the product of one rough likelihood per government, vote and enacted policy under the deal."""
    fascist = {uid for uid, role in deal.items() if party_of(role) is Party.FASCIST}
    weight = 1.0
    claims: dict[type, ClaimEvent] = {}
    for event in events:
        match event:
            case NominationEvent():
                weight *= _claims_likelihood(claims, fascist)
                claims = {}
            case ElectionEvent():
                has_fascist = bool(
                    {event.president_uid, event.chancellor_uid} & fascist
                )
                for uid, vote in event.votes.items():
                    if uid not in fascist:
                        ja = LIBERAL_JA
                    elif has_fascist:
                        ja = FASCIST_JA_FASCIST_GOVERNMENT
                    else:
                        ja = FASCIST_JA_LIBERAL_GOVERNMENT
                    weight *= ja if vote == Vote.JA else 1 - ja
            case PolicyEnactedEvent() if not event.top_deck:
                if {event.president_uid, event.chancellor_uid} & fascist:
                    chance = FASCIST_GOVERNMENT_FASCIST_POLICY
                else:
                    chance = LIBERAL_GOVERNMENT_FASCIST_POLICY
                weight *= chance if event.policy == PolicyTile.FASCIST else 1 - chance
            case ClaimEvent(claim=PresidentEnactClaim() | ChancellorEnactClaim()):
                claims[type(event.claim)] = event
    return weight * _claims_likelihood(claims, fascist)


def _claims_likelihood(claims: dict[type, ClaimEvent], fascist: set[int]) -> float:
    """Returns the likelihood of one government's latest policy claims, which is low when an all-liberal government contradicts itself."""
    president = claims.get(PresidentEnactClaim)
    chancellor = claims.get(ChancellorEnactClaim)
    if president is None or chancellor is None:
        return 1.0
    if president.claim.policies is None or chancellor.claim.policies is None:
        return 1.0
    passed = list(president.claim.policies)
    passed.remove(president.claim.discarded)
    if sorted(passed) == sorted(chancellor.claim.policies):
        return 1.0
    if {president.president_uid, president.chancellor_uid} & fascist:
        return 1.0
    return ALL_LIBERAL_CLAIM_CONFLICT
