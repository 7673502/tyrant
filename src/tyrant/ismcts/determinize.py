from dataclasses import replace
from random import Random
from typing import Final

from frozendict import frozendict

from tyrant.ismcts.beliefs import party_of
from tyrant.models.ballot_box import BallotBox
from tyrant.models.claim import PeekClaim
from tyrant.models.deck import NUM_FASCIST_POLICIES, NUM_LIBERAL_POLICIES, Deck
from tyrant.models.enums import HIDDEN, GamePhase, PolicyTile, Role, Vote
from tyrant.models.event import (
    ClaimEvent,
    DeckShuffledEvent,
    ElectionEvent,
    PolicyEnactedEvent,
    VetoEvent,
)
from tyrant.models.game_state import GameState
from tyrant.models.knowledge import (
    ChancellorReceiveKnowledge,
    PeekKnowledge,
    PresidentDrawKnowledge,
)

HAND_SIZES: Final = frozendict(
    {
        GamePhase.PRESIDENT_DISCARD: 3,
        GamePhase.CHANCELLOR_ENACT: 2,
        GamePhase.PRESIDENT_VETO_RESPONSE: 2,
    }
)
"""The number of policies in the government's hand in each phase that has one."""


def determinize(
    state: GameState, viewer_uid: int, roles: frozendict[int, Role], rng: Random
) -> GameState:
    """Fills in everything a scrubbed state hides, giving one complete game the viewer cannot tell apart from the real one.

    The deck is dealt from the policies not on the board, keeping the viewer's hand, the policies the viewer saw discarded since the last shuffle, and the top of the draw pile while the viewer's latest peek still holds. Hidden votes are random and the shuffle state is fresh. Discussions are turned off.

    Args:
        state: The game state, scrubbed for the viewer.
        viewer_uid: UID of the viewer.
        roles: A deal that fits the viewer's knowledge, mapping each UID to a role.
        rng: Random generator for the hidden policies, votes and shuffle state.

    Returns:
        A new, complete game state.
    """
    hand, discards, top = _known_policies(state, viewer_uid)
    unknown = [PolicyTile.LIBERAL] * (
        NUM_LIBERAL_POLICIES - state.board.liberal_played
    ) + [PolicyTile.FASCIST] * (NUM_FASCIST_POLICIES - state.board.fascist_played)
    for tile in hand + discards + top:
        unknown.remove(tile)
    rng.shuffle(unknown)

    if not hand:
        hand = tuple(unknown.pop() for _ in range(HAND_SIZES.get(state.phase, 0)))
    discard_pile = discards + tuple(
        unknown.pop() for _ in range(len(state.deck.discard_pile) - len(discards))
    )
    deck = Deck(
        draw_pile=tuple(unknown) + tuple(reversed(top)), discard_pile=discard_pile
    )

    investigation_result = state.current_investigation_result
    if investigation_result is HIDDEN:
        investigation_result = party_of(roles[next(reversed(state.investigations))])

    return replace(
        state,
        players=tuple(
            replace(p, role=roles[p.uid], party=party_of(roles[p.uid]))
            for p in state.players
        ),
        deck=deck,
        drawn_policies=deck.peek
        if state.phase == GamePhase.CLAIM_POLICY_PEEK
        else hand,
        ballot_box=BallotBox(
            votes=frozendict(
                {
                    uid: rng.choice((Vote.JA, Vote.NEIN)) if vote is HIDDEN else vote
                    for uid, vote in state.ballot_box.votes.items()
                }
            )
        ),
        current_investigation_result=investigation_result,
        rng_state=Random(rng.random()).getstate(),
        discussion_enabled=False,
    )


def _known_policies(
    state: GameState, viewer_uid: int
) -> tuple[tuple[PolicyTile, ...], tuple[PolicyTile, ...], tuple[PolicyTile, ...]]:
    """Returns the viewer's hand, the policies the viewer knows are in the discard pile, and the top of the draw pile from the top down, each empty when unknown."""
    president_hands = iter(
        k.policies for k in state.knowledge if isinstance(k, PresidentDrawKnowledge)
    )
    chancellor_hands = iter(
        k.policies for k in state.knowledge if isinstance(k, ChancellorReceiveKnowledge)
    )
    peeks = iter(k.policies for k in state.knowledge if isinstance(k, PeekKnowledge))

    discards: list[PolicyTile] = []
    top: tuple[PolicyTile, ...] = ()
    seen: list[PolicyTile] | None = None
    for event in state.events:
        match event:
            case DeckShuffledEvent():
                discards = []
            case ElectionEvent(result=Vote.JA):
                top = ()
                seen = None
                if event.president_uid == viewer_uid:
                    seen = list(next(president_hands))
                elif event.chancellor_uid == viewer_uid:
                    received = next(chancellor_hands, None)
                    seen = None if received is None else list(received)
            case PolicyEnactedEvent() if event.top_deck:
                top = ()
            case PolicyEnactedEvent() if seen is not None:
                seen.remove(event.policy)
                discards += seen
                seen = None
            case VetoEvent(approved=True) if seen is not None:
                discards += seen
                seen = None
            case ClaimEvent(claim=PeekClaim()) if event.president_uid == viewer_uid:
                top = next(peeks)

    hand: tuple[PolicyTile, ...] = ()
    president_uid = state.players[state.president_index].uid
    match state.phase:
        case GamePhase.PRESIDENT_DISCARD if viewer_uid == president_uid:
            hand = state.drawn_policies
        case GamePhase.CHANCELLOR_ENACT | GamePhase.PRESIDENT_VETO_RESPONSE:
            if viewer_uid == president_uid:
                hand = state.knowledge[-1].passed
                discards.append(state.knowledge[-1].discarded)
            elif viewer_uid == state.chancellor:
                hand = state.knowledge[-1].policies
        case GamePhase.CLAIM_POLICY_PEEK if viewer_uid == president_uid:
            top = state.drawn_policies
    return hand, tuple(discards), top
