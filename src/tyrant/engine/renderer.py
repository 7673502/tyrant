import re
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

from frozendict import frozendict

from tyrant.exceptions import TyrantError
from tyrant.models.board import (
    FASCIST_TILES_TO_WIN,
    FASCIST_TRACKS,
    LIBERAL_TILES_TO_WIN,
)
from tyrant.models.election_tracker import FAILURES_UNTIL_TOP_DECK
from tyrant.models.enums import HIDDEN, GamePhase
from tyrant.models.game_state import GameState

UNKNOWN = "unknown"
PRESIDENT_PHASES = (
    GamePhase.NOMINATION,
    GamePhase.PRESIDENT_DISCARD,
    GamePhase.PRESIDENTIAL_POWER,
    GamePhase.CLAIM_INVESTIGATION,
    GamePhase.CLAIM_POLICY_PEEK,
    GamePhase.PRESIDENT_VETO_RESPONSE,
)


def _type_name(value: Any, suffix: str) -> str:
    name = type(value).__name__.removesuffix(suffix)
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _to_json(value: Any, suffix: str = "") -> Any:
    if value is HIDDEN:
        return UNKNOWN
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_to_json(v) for v in value]
    if isinstance(value, frozendict):
        return {str(k): _to_json(v) for k, v in value.items()}
    if is_dataclass(value):
        return {"type": _type_name(value, suffix)} | {
            f.name: _to_json(getattr(value, f.name), "Claim") for f in fields(value)
        }
    return value


def _awaiting(state: GameState) -> list[int]:
    president_uid = state.players[state.president_index].uid
    if state.phase in PRESIDENT_PHASES:
        return [president_uid]
    match state.phase:
        case GamePhase.CHANCELLOR_ENACT:
            return [state.chancellor]
        case GamePhase.VOTING:
            return [
                p.uid
                for p in state.players
                if p.is_alive and p.uid not in state.ballot_box.votes
            ]
        case GamePhase.DISCUSSION:
            return [state.discussion.current_speaker]
        case GamePhase.CLAIM_POLICIES:
            pending = (
                (president_uid, state.pending_president_enact_claim),
                (state.chancellor, state.pending_chancellor_enact_claim),
            )
            return [uid for uid, is_pending in pending if is_pending]
        case _:
            return []


def render_dict(state: GameState, viewer_uid: int) -> dict:
    """Returns a JSON-serializable view of a scrubbed state for the given viewer."""
    viewer = next((p for p in state.players if p.uid == viewer_uid), None)
    if viewer is None:
        raise TyrantError(f"Viewer with UID {viewer_uid} not found")

    return {
        "viewer": {
            "uid": viewer.uid,
            "role": _to_json(viewer.role),
            "party": _to_json(viewer.party),
            "alive": viewer.is_alive,
            "teammates": [
                {"uid": p.uid, "role": _to_json(p.role)}
                for p in state.players
                if p.uid != viewer_uid and p.role is not HIDDEN
            ],
        },
        "players": [
            {
                "uid": p.uid,
                "party": _to_json(p.party),
                "role": _to_json(p.role),
                "alive": p.is_alive,
            }
            for p in state.players
        ],
        "board": {
            "liberal_policies": state.board.liberal_played,
            "liberal_policies_to_win": LIBERAL_TILES_TO_WIN,
            "fascist_policies": state.board.fascist_played,
            "fascist_policies_to_win": FASCIST_TILES_TO_WIN,
            "fascist_track": _to_json(FASCIST_TRACKS[state.board.player_count]),
            "election_tracker": state.election_tracker.failed_elections,
            "failures_until_top_deck": FAILURES_UNTIL_TOP_DECK,
            "hitler_zone": state.board.hitler_zone,
            "veto_unlocked": state.board.veto_power_unlocked,
            "draw_pile": len(state.deck.draw_pile),
            "discard_pile": len(state.deck.discard_pile),
        },
        "government": {
            "president": state.players[state.president_index].uid,
            "chancellor": state.chancellor,
            "previous_president": state.previous_president,
            "previous_chancellor": state.previous_chancellor,
        },
        "turn": {
            "phase": _to_json(state.phase),
            "awaiting": _awaiting(state),
            "active_power": _to_json(state.active_power),
            "hand": _to_json(state.drawn_policies),
            "winner": _to_json(state.winner),
        },
        "timeline": [_to_json(e, "Event") for e in state.events],
        "knowledge": [_to_json(k, "Knowledge") for k in state.knowledge],
    }
