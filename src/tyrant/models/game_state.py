from dataclasses import dataclass, replace
from random import Random
from typing import Final, Mapping

from frozendict import frozendict

from tyrant.exceptions import InvalidMoveError, TyrantError
from tyrant.models.ballot_box import BallotBox, submit_vote
from tyrant.models.board import Board, play_tile
from tyrant.models.claim import (
    ChancellorEnactClaim,
    Claim,
    InvestigationClaim,
    PeekClaim,
    PresidentEnactClaim,
)
from tyrant.models.deck import (
    Deck,
    create_deck,
    discard_policies,
    draw_policies,
    shuffle_deck,
    top_deck,
)
from tyrant.models.discussion import Discussion, Message
from tyrant.models.election_tracker import ElectionTracker, increment_election_tracker
from tyrant.models.enums import (
    HIDDEN,
    DiscussionContext,
    GamePhase,
    Party,
    PolicyTile,
    PresidentialPower,
    Role,
    Vote,
    WinCondition,
)
from tyrant.models.event import (
    ClaimEvent,
    ElectionEvent,
    Event,
    ExecutionEvent,
    GameOverEvent,
    InvestigationEvent,
    NominationEvent,
    PolicyEnactedEvent,
    SpecialElectionEvent,
    SpeechEvent,
    VetoEvent,
)
from tyrant.models.player import Player

ROLE_DISTRIBUTION: Final[frozendict[int, tuple[int, int]]] = frozendict(
    {5: (3, 2), 6: (4, 2), 7: (4, 3), 8: (5, 3), 9: (5, 4), 10: (6, 4)}
)
POLICY_WIN_CONDITIONS: Final[frozendict[Party, WinCondition]] = frozendict(
    {
        Party.LIBERAL: WinCondition.LIBERAL_POLICIES,
        Party.FASCIST: WinCondition.FASCIST_POLICIES,
    }
)


@dataclass(frozen=True)
class GameState:
    players: tuple[Player, ...]
    board: Board
    deck: Deck
    election_tracker: ElectionTracker
    phase: GamePhase
    president_index: int
    chancellor: int | None  # chancellor uid
    ballot_box: BallotBox
    drawn_policies: tuple[PolicyTile | HIDDEN, ...]
    previous_president: int | None  # previous president uid
    previous_chancellor: int | None  # previous chancellor uid
    winner: Party | None
    special_election_president: int | None
    rng_state: tuple[int, tuple[int, ...], float | None] | HIDDEN
    veto_denied_this_term: bool = False
    investigations: frozendict[int, int] = frozendict()
    deck_shuffled_last_action: bool = False
    active_power: PresidentialPower = PresidentialPower.NONE
    current_investigation_result: Party | HIDDEN | None = None
    claims: tuple[Claim, ...] = ()
    pending_president_enact_claim: bool = False
    pending_chancellor_enact_claim: bool = False
    pending_power: PresidentialPower = PresidentialPower.NONE
    special_election_caller_index: int | None = None
    discussion_enabled: bool = False
    discussion: Discussion | None = None
    messages: tuple[Message, ...] = ()
    events: tuple[Event, ...] = ()


def create_game(
    uids: tuple[int, ...],
    seed: int | None = 42,
    roles: Mapping[int, Role] | None = None,
    shuffle_players: bool = True,
    discussion_enabled: bool = False,
) -> GameState:
    player_count = len(uids)
    if not (5 <= player_count <= 10):
        raise TyrantError(f"Player count must be between 5 and 10, got {player_count}")
    if len(uids) != len(set(uids)):
        raise TyrantError("Player UIDs must be unique")

    num_liberals, num_fascists = ROLE_DISTRIBUTION[player_count]

    rng = Random(seed)

    if roles is not None:
        if set(uids) != set(roles.keys()):
            raise TyrantError("fixed_roles must contain exactly all player UIDs")

        role_counts = {Role.LIBERAL: 0, Role.FASCIST: 0, Role.HITLER: 0}
        for r in roles.values():
            role_counts[r] = role_counts.get(r, 0) + 1

        if (
            role_counts[Role.HITLER] != 1
            or role_counts[Role.FASCIST] != num_fascists - 1
            or role_counts[Role.LIBERAL] != num_liberals
        ):
            raise TyrantError(
                "fixed_roles distribution does not match required roles for this player count"
            )

        roles_pool = [roles[uid] for uid in uids]
    else:
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

    if shuffle_players:
        rng.shuffle(players_list)

    return GameState(
        players=tuple(players_list),
        board=Board(player_count=player_count),
        deck=create_deck(rng),
        election_tracker=ElectionTracker(),
        phase=GamePhase.NOMINATION,
        president_index=0,
        chancellor=None,
        ballot_box=BallotBox(),
        drawn_policies=(),
        previous_president=None,
        previous_chancellor=None,
        winner=None,
        special_election_president=None,
        rng_state=rng.getstate(),
        veto_denied_this_term=False,
        investigations=frozendict(),
        deck_shuffled_last_action=False,
        current_investigation_result=None,
        discussion_enabled=discussion_enabled,
    )


def _end_game(state: GameState, winner: Party, condition: WinCondition) -> GameState:
    return replace(
        state,
        winner=winner,
        phase=GamePhase.GAME_OVER,
        events=state.events + (GameOverEvent(winner=winner, condition=condition),),
    )


def _advance_to_nomination(state: GameState) -> GameState:
    new_special = state.special_election_president
    new_caller = state.special_election_caller_index
    new_president_index = state.president_index

    entering_special_election = (
        state.special_election_president is not None
        and state.phase == GamePhase.PRESIDENTIAL_POWER
    )

    if entering_special_election:
        target_uid = state.special_election_president
        target_index = next(
            i for i, p in enumerate(state.players) if p.uid == target_uid
        )
        new_president_index = target_index
    else:
        new_special = None
        new_caller = None

        if state.special_election_caller_index is not None:
            new_president_index = (state.special_election_caller_index + 1) % len(
                state.players
            )
        else:
            new_president_index = (state.president_index + 1) % len(state.players)

        while not state.players[new_president_index].is_alive:
            new_president_index = (new_president_index + 1) % len(state.players)

    return replace(
        state,
        president_index=new_president_index,
        special_election_president=new_special,
        special_election_caller_index=new_caller,
        phase=GamePhase.NOMINATION,
        veto_denied_this_term=False,
        chancellor=None,
        active_power=PresidentialPower.NONE,
        current_investigation_result=None,
    )


def _begin_discussion(state: GameState, context: DiscussionContext) -> GameState:
    if not state.discussion_enabled or state.phase == GamePhase.GAME_OVER:
        return state

    player_count = len(state.players)
    seats = (
        state.players[(state.president_index + i) % player_count]
        for i in range(player_count)
    )
    return replace(
        state,
        phase=GamePhase.DISCUSSION,
        discussion=Discussion(
            context=context,
            resume_phase=state.phase,
            speaker_order=tuple(p.uid for p in seats if p.is_alive),
        ),
    )


def speak(state: GameState, uid: int, text: str | None) -> GameState:
    if state.phase != GamePhase.DISCUSSION or state.discussion is None:
        raise InvalidMoveError(f"Cannot speak in phase {state.phase}")

    discussion = state.discussion
    if uid != discussion.current_speaker:
        raise InvalidMoveError(f"It is not Player {uid}'s turn to speak")

    new_state = replace(
        state,
        messages=state.messages
        + (Message(uid=uid, text=text, context=discussion.context),),
        events=state.events
        + (SpeechEvent(uid=uid, text=text, context=discussion.context),),
        deck_shuffled_last_action=False,
    )

    next_turn = discussion.turn + 1
    if next_turn == len(discussion.speaker_order):
        return replace(new_state, phase=discussion.resume_phase, discussion=None)

    return replace(new_state, discussion=replace(discussion, turn=next_turn))


def nominate_chancellor(state: GameState, chancellor_uid: int) -> GameState:
    if state.phase != GamePhase.NOMINATION:
        raise InvalidMoveError(f"Cannot nominate chancellor in phase {state.phase}")

    president = state.players[state.president_index]
    if chancellor_uid == president.uid:
        raise InvalidMoveError("President cannot nominate themselves")

    chancellor = next((p for p in state.players if p.uid == chancellor_uid), None)
    if chancellor is None:
        raise InvalidMoveError(f"Player with UID {chancellor_uid} not found")

    if not chancellor.is_alive:
        raise InvalidMoveError("Cannot nominate a dead player")

    alive_count = sum(1 for p in state.players if p.is_alive)
    if alive_count > 5:
        if chancellor_uid in (state.previous_president, state.previous_chancellor):
            raise InvalidMoveError(
                "Target cannot be previous president or chancellor when > 5 players are alive"
            )
    else:
        if chancellor_uid == state.previous_chancellor:
            raise InvalidMoveError(
                "Target cannot be previous chancellor when <= 5 players are alive"
            )

    new_state = replace(
        state,
        chancellor=chancellor_uid,
        phase=GamePhase.VOTING,
        ballot_box=BallotBox(),
        deck_shuffled_last_action=False,
        events=state.events
        + (
            NominationEvent(president_uid=president.uid, chancellor_uid=chancellor_uid),
        ),
    )
    return _begin_discussion(new_state, DiscussionContext.AFTER_NOMINATION)


def _ensure_deck_ready(state: GameState) -> GameState:
    if len(state.deck.draw_pile) < 3:
        rng = Random()
        rng.setstate(state.rng_state)
        new_deck, _ = shuffle_deck(state.deck, rng)
        return replace(
            state,
            deck=new_deck,
            rng_state=rng.getstate(),
            deck_shuffled_last_action=True,
        )
    else:
        return replace(state, deck_shuffled_last_action=False)


def _resolve_election(state: GameState) -> GameState:
    ja_votes = sum(1 for v in state.ballot_box.votes.values() if v == Vote.JA)
    nein_votes = sum(1 for v in state.ballot_box.votes.values() if v == Vote.NEIN)

    election = ElectionEvent(
        president_uid=state.players[state.president_index].uid,
        chancellor_uid=state.chancellor,
        votes=state.ballot_box.votes,
        result=Vote.JA if ja_votes > nein_votes else Vote.NEIN,
    )
    state = replace(state, events=state.events + (election,))

    if ja_votes > nein_votes:
        chancellor_uid = state.chancellor
        chancellor = next(p for p in state.players if p.uid == chancellor_uid)

        if state.board.hitler_zone and chancellor.role == Role.HITLER:
            return _end_game(
                replace(state, deck_shuffled_last_action=False),
                Party.FASCIST,
                WinCondition.HITLER_ELECTED,
            )

        state = _ensure_deck_ready(state)
        new_deck, drawn = draw_policies(state.deck)

        return replace(
            state,
            deck=new_deck,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=drawn,
            election_tracker=ElectionTracker(failed_elections=0),
            previous_president=state.players[state.president_index].uid,
            previous_chancellor=chancellor_uid,
        )
    else:
        new_tracker, triggered_top_deck = increment_election_tracker(
            state.election_tracker
        )

        if triggered_top_deck:
            state = _ensure_deck_ready(state)
            new_deck, tile = top_deck(state.deck)
            new_board, _ = play_tile(state.board, tile)

            new_state = replace(
                state,
                election_tracker=new_tracker,
                deck=new_deck,
                board=new_board,
                previous_president=None,
                previous_chancellor=None,
                events=state.events
                + (
                    PolicyEnactedEvent(
                        policy=tile, president_uid=None, chancellor_uid=None
                    ),
                ),
            )

            if new_board.winner is not None:
                return _end_game(
                    new_state,
                    new_board.winner,
                    POLICY_WIN_CONDITIONS[new_board.winner],
                )

            return _begin_discussion(
                _advance_to_nomination(new_state),
                DiscussionContext.AFTER_FAILED_ELECTION,
            )
        else:
            new_state = replace(
                state, election_tracker=new_tracker, deck_shuffled_last_action=False
            )
            return _begin_discussion(
                _advance_to_nomination(new_state),
                DiscussionContext.AFTER_FAILED_ELECTION,
            )


def cast_vote(state: GameState, uid: int, vote: Vote) -> GameState:
    if state.phase != GamePhase.VOTING:
        raise InvalidMoveError(f"Cannot cast vote in phase {state.phase}")

    player = next((p for p in state.players if p.uid == uid), None)
    if player is None:
        raise InvalidMoveError(f"Player with UID {uid} not found")

    if not player.is_alive:
        raise InvalidMoveError("Cannot vote when dead")

    new_ballot_box = submit_vote(state.ballot_box, uid, vote)
    new_state = replace(
        state, ballot_box=new_ballot_box, deck_shuffled_last_action=False
    )

    alive_count = sum(1 for p in state.players if p.is_alive)
    if new_ballot_box.vote_count == alive_count:
        return _resolve_election(new_state)

    return new_state


def president_discard(state: GameState, discard_index: int) -> GameState:
    if state.phase != GamePhase.PRESIDENT_DISCARD:
        raise InvalidMoveError(f"Cannot discard in phase {state.phase}")

    if not (0 <= discard_index < len(state.drawn_policies)):
        raise InvalidMoveError(f"Invalid discard index: {discard_index}")

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
        deck_shuffled_last_action=False,
    )


def chancellor_enact(state: GameState, enact_index: int) -> GameState:
    if state.phase != GamePhase.CHANCELLOR_ENACT:
        raise InvalidMoveError(f"Cannot enact in phase {state.phase}")

    if not (0 <= enact_index < len(state.drawn_policies)):
        raise InvalidMoveError(f"Invalid enact index: {enact_index}")

    enacted_tile = state.drawn_policies[enact_index]
    discard_index = 1 - enact_index
    discarded_tile = state.drawn_policies[discard_index]

    new_board, power = play_tile(state.board, enacted_tile)
    new_deck = discard_policies(state.deck, discarded_tile)

    new_state = replace(
        state,
        board=new_board,
        deck=new_deck,
        drawn_policies=(),
        deck_shuffled_last_action=False,
        events=state.events
        + (
            PolicyEnactedEvent(
                policy=enacted_tile,
                president_uid=state.players[state.president_index].uid,
                chancellor_uid=state.chancellor,
            ),
        ),
    )

    if new_board.winner is not None:
        return _end_game(
            new_state, new_board.winner, POLICY_WIN_CONDITIONS[new_board.winner]
        )

    return replace(
        new_state,
        phase=GamePhase.CLAIM_POLICIES,
        pending_president_enact_claim=True,
        pending_chancellor_enact_claim=True,
        pending_power=power,
    )


def claim_enact(
    state: GameState, claim: PresidentEnactClaim | ChancellorEnactClaim
) -> GameState:
    if state.phase != GamePhase.CLAIM_POLICIES:
        raise InvalidMoveError(f"Cannot claim enact in phase {state.phase}")

    president_uid = state.players[state.president_index].uid
    chancellor_uid = state.chancellor

    new_pending_president = state.pending_president_enact_claim
    new_pending_chancellor = state.pending_chancellor_enact_claim

    if isinstance(claim, PresidentEnactClaim):
        if claim.uid != president_uid:
            raise InvalidMoveError("Only the current president can make this claim.")
        if not new_pending_president:
            raise InvalidMoveError("President has already claimed")
        new_pending_president = False
    elif isinstance(claim, ChancellorEnactClaim):
        if claim.uid != chancellor_uid:
            raise InvalidMoveError("Only the current chancellor can make this claim.")
        if not new_pending_chancellor:
            raise InvalidMoveError("Chancellor has already claimed")
        new_pending_chancellor = False
    else:
        raise InvalidMoveError("Invalid claim type")

    new_state = replace(
        state,
        claims=state.claims + (claim,),
        events=state.events
        + (
            ClaimEvent(
                claim=claim,
                president_uid=president_uid,
                chancellor_uid=chancellor_uid,
                target_uid=None,
            ),
        ),
        pending_president_enact_claim=new_pending_president,
        pending_chancellor_enact_claim=new_pending_chancellor,
        deck_shuffled_last_action=False,
    )

    if not new_pending_president and not new_pending_chancellor:
        power = new_state.pending_power
        new_state = replace(new_state, pending_power=PresidentialPower.NONE)

        if power == PresidentialPower.NONE:
            new_state = _advance_to_nomination(new_state)
        else:
            new_state = replace(
                new_state, phase=GamePhase.PRESIDENTIAL_POWER, active_power=power
            )
        return _begin_discussion(new_state, DiscussionContext.AFTER_POLICY_CLAIMS)

    return new_state


def chancellor_veto(state: GameState) -> GameState:
    if state.phase != GamePhase.CHANCELLOR_ENACT:
        raise InvalidMoveError(f"Cannot veto in phase {state.phase}")

    if not state.board.veto_power_unlocked:
        raise InvalidMoveError("Veto power is not unlocked")

    if state.veto_denied_this_term:
        raise InvalidMoveError("Veto has already been denied this term")

    return replace(
        state, phase=GamePhase.PRESIDENT_VETO_RESPONSE, deck_shuffled_last_action=False
    )


def president_veto_response(state: GameState, approve: bool) -> GameState:
    if state.phase != GamePhase.PRESIDENT_VETO_RESPONSE:
        raise InvalidMoveError(f"Cannot respond to veto in phase {state.phase}")

    if not state.board.veto_power_unlocked:
        raise InvalidMoveError("Veto power is not unlocked")

    veto = VetoEvent(
        president_uid=state.players[state.president_index].uid,
        chancellor_uid=state.chancellor,
        approved=approve,
    )
    state = replace(state, events=state.events + (veto,))

    if approve:
        new_deck = discard_policies(state.deck, *state.drawn_policies)
        state = replace(state, deck=new_deck)

        new_tracker, triggered_top_deck = increment_election_tracker(
            state.election_tracker
        )

        if triggered_top_deck:
            state = _ensure_deck_ready(state)
            new_deck, tile = top_deck(state.deck)
            new_board, _ = play_tile(state.board, tile)

            new_state = replace(
                state,
                election_tracker=new_tracker,
                deck=new_deck,
                board=new_board,
                drawn_policies=(),
                previous_president=None,
                previous_chancellor=None,
                events=state.events
                + (
                    PolicyEnactedEvent(
                        policy=tile, president_uid=None, chancellor_uid=None
                    ),
                ),
            )

            if new_board.winner is not None:
                return _end_game(
                    new_state,
                    new_board.winner,
                    POLICY_WIN_CONDITIONS[new_board.winner],
                )

        else:
            new_state = replace(
                state,
                election_tracker=new_tracker,
                drawn_policies=(),
                deck_shuffled_last_action=False,
            )

        return replace(
            new_state,
            phase=GamePhase.CLAIM_POLICIES,
            pending_president_enact_claim=True,
            pending_chancellor_enact_claim=True,
            pending_power=PresidentialPower.NONE,
        )
    else:
        return replace(
            state,
            veto_denied_this_term=True,
            phase=GamePhase.CHANCELLOR_ENACT,
            deck_shuffled_last_action=False,
        )


def investigate_loyalty(state: GameState, target_uid: int) -> GameState:
    if state.phase != GamePhase.PRESIDENTIAL_POWER:
        raise InvalidMoveError(f"Cannot investigate loyalty in phase {state.phase}")

    investigator_uid = state.players[state.president_index].uid
    if target_uid == investigator_uid:
        raise InvalidMoveError("President cannot investigate themselves")

    target = next((p for p in state.players if p.uid == target_uid), None)
    if target is None:
        raise InvalidMoveError(f"Player with UID {target_uid} not found")

    if not target.is_alive:
        raise InvalidMoveError("Dead player cannot be investigated.")

    new_investigations = frozendict(
        {**state.investigations, target_uid: investigator_uid}
    )
    return replace(
        state,
        investigations=new_investigations,
        deck_shuffled_last_action=False,
        phase=GamePhase.CLAIM_INVESTIGATION,
        current_investigation_result=target.party,
        events=state.events
        + (InvestigationEvent(president_uid=investigator_uid, target_uid=target_uid),),
    )


def claim_investigation(state: GameState, claim: InvestigationClaim) -> GameState:
    if state.phase != GamePhase.CLAIM_INVESTIGATION:
        raise InvalidMoveError(f"Cannot claim investigation in phase {state.phase}")

    president_uid = state.players[state.president_index].uid
    if claim.uid != president_uid:
        raise InvalidMoveError("Only the current president can make this claim.")

    new_state = replace(
        state,
        current_investigation_result=None,
        deck_shuffled_last_action=False,
        claims=state.claims + (claim,),
        events=state.events
        + (
            ClaimEvent(
                claim=claim,
                president_uid=president_uid,
                chancellor_uid=None,
                target_uid=next(reversed(state.investigations), None),
            ),
        ),
    )
    return _begin_discussion(
        _advance_to_nomination(new_state), DiscussionContext.AFTER_INVESTIGATION_CLAIM
    )


def call_special_election(state: GameState, target_uid: int) -> GameState:
    if state.phase != GamePhase.PRESIDENTIAL_POWER:
        raise InvalidMoveError(f"Cannot call special election in phase {state.phase}")

    president_uid = state.players[state.president_index].uid
    if target_uid == president_uid:
        raise InvalidMoveError("President cannot call special election on themselves")

    target = next((p for p in state.players if p.uid == target_uid), None)
    if target is None:
        raise InvalidMoveError(f"Player with UID {target_uid} not found")

    if not target.is_alive:
        raise InvalidMoveError("Dead player cannot be chosen for special election.")

    new_state = replace(
        state,
        special_election_president=target_uid,
        special_election_caller_index=state.president_index,
        deck_shuffled_last_action=False,
        events=state.events
        + (SpecialElectionEvent(president_uid=president_uid, target_uid=target_uid),),
    )

    return _begin_discussion(
        _advance_to_nomination(new_state), DiscussionContext.AFTER_SPECIAL_ELECTION
    )


def policy_peek(state: GameState) -> GameState:
    if state.phase != GamePhase.PRESIDENTIAL_POWER:
        raise InvalidMoveError(f"Cannot peek policies in phase {state.phase}")

    state = _ensure_deck_ready(state)
    return replace(
        state,
        drawn_policies=state.deck.peek,
        phase=GamePhase.CLAIM_POLICY_PEEK,
    )


def claim_peek(state: GameState, claim: PeekClaim) -> GameState:
    if state.phase != GamePhase.CLAIM_POLICY_PEEK:
        raise InvalidMoveError(f"Cannot claim peek in phase {state.phase}")

    president_uid = state.players[state.president_index].uid
    if claim.uid != president_uid:
        raise InvalidMoveError("Only the current president can make this claim.")

    new_state = replace(
        state,
        drawn_policies=(),
        deck_shuffled_last_action=False,
        claims=state.claims + (claim,),
        events=state.events
        + (
            ClaimEvent(
                claim=claim,
                president_uid=president_uid,
                chancellor_uid=None,
                target_uid=None,
            ),
        ),
    )

    return _begin_discussion(
        _advance_to_nomination(new_state), DiscussionContext.AFTER_PEEK_CLAIM
    )


def execute_player(state: GameState, target_uid: int) -> GameState:
    if state.phase != GamePhase.PRESIDENTIAL_POWER:
        raise InvalidMoveError(f"Cannot execute player in phase {state.phase}")

    president_uid = state.players[state.president_index].uid
    if target_uid == president_uid:
        raise InvalidMoveError("President cannot execute themselves")

    target = next((p for p in state.players if p.uid == target_uid), None)
    if target is None:
        raise InvalidMoveError(f"Player with UID {target_uid} not found")

    if not target.is_alive:
        raise InvalidMoveError("Cannot execute an already dead player")

    new_players = list(state.players)
    for i, p in enumerate(new_players):
        if p.uid == target_uid:
            new_players[i] = replace(p, is_alive=False)

    new_state = replace(
        state,
        players=tuple(new_players),
        deck_shuffled_last_action=False,
        events=state.events
        + (ExecutionEvent(president_uid=president_uid, target_uid=target_uid),),
    )

    if target.role == Role.HITLER:
        return _end_game(
            replace(new_state, active_power=PresidentialPower.NONE),
            Party.LIBERAL,
            WinCondition.HITLER_EXECUTED,
        )

    return _begin_discussion(
        _advance_to_nomination(new_state), DiscussionContext.AFTER_EXECUTION
    )


def scrub_state(state: GameState, viewer_uid: int) -> GameState:
    viewer = next((p for p in state.players if p.uid == viewer_uid), None)
    if viewer is None:
        raise TyrantError(f"Viewer with UID {viewer_uid} not found")

    new_players = []
    for p in state.players:
        if p.uid == viewer_uid:
            new_players.append(p)
            continue

        is_visible = False
        role_visible = False

        if viewer.role == Role.LIBERAL:
            pass
        elif viewer.role == Role.HITLER:
            if len(state.players) <= 6:
                if p.role in (Role.FASCIST, Role.HITLER):
                    is_visible = True
                    role_visible = True
        elif viewer.role == Role.FASCIST:
            if p.role in (Role.FASCIST, Role.HITLER):
                is_visible = True
                role_visible = True

        if state.investigations.get(p.uid) == viewer_uid:
            is_visible = True

        if is_visible:
            # party is always shown if is_visible is True
            new_players.append(replace(p, role=p.role if role_visible else HIDDEN))
        else:
            new_players.append(replace(p, party=HIDDEN, role=HIDDEN))

    scrubbed_draw = tuple(HIDDEN for _ in state.deck.draw_pile)
    scrubbed_discard = tuple(HIDDEN for _ in state.deck.discard_pile)
    new_deck = replace(
        state.deck,
        draw_pile=scrubbed_draw,
        discard_pile=scrubbed_discard,
    )

    new_drawn_policies = ()
    if state.phase in (GamePhase.PRESIDENT_DISCARD, GamePhase.CLAIM_POLICY_PEEK):
        president = state.players[state.president_index]
        if viewer_uid == president.uid:
            new_drawn_policies = state.drawn_policies
    elif state.phase == GamePhase.CHANCELLOR_ENACT:
        if viewer_uid == state.chancellor:
            new_drawn_policies = state.drawn_policies

    new_ballot_box = state.ballot_box
    if state.phase == GamePhase.VOTING:
        new_votes = {
            uid: (vote if uid == viewer_uid else HIDDEN)
            for uid, vote in state.ballot_box.votes.items()
        }
        new_ballot_box = replace(state.ballot_box, votes=frozendict(new_votes))

    new_investigation_result = state.current_investigation_result
    if state.phase == GamePhase.CLAIM_INVESTIGATION:
        president = state.players[state.president_index]
        if viewer_uid != president.uid:
            new_investigation_result = HIDDEN

    return replace(
        state,
        players=tuple(new_players),
        deck=new_deck,
        drawn_policies=new_drawn_policies,
        ballot_box=new_ballot_box,
        rng_state=HIDDEN,
        current_investigation_result=new_investigation_result,
    )
