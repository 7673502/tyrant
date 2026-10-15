import json
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
from tyrant.models.game_state import GameState, scrub_state

UNKNOWN = "unknown"
DISCUSSIONS_SHOWN = 2
PRESIDENT_PHASES = (
    GamePhase.NOMINATION,
    GamePhase.PRESIDENT_DISCARD,
    GamePhase.PRESIDENTIAL_POWER,
    GamePhase.CLAIM_INVESTIGATION,
    GamePhase.CLAIM_POLICY_PEEK,
    GamePhase.PRESIDENT_VETO_RESPONSE,
)


def _type_name(value: Any, suffix: str) -> str:
    """Returns the value's class name in snake case, without the given suffix."""
    name = type(value).__name__.removesuffix(suffix)
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def to_json(value: Any, suffix: str = "") -> Any:
    """Converts a model value to plain JSON values.

    Args:
        value: An enum, tuple, frozendict, dataclass, `HIDDEN` or plain value.
        suffix: Suffix removed from a dataclass's class name to form its `type` field.

    Returns:
        The value as plain dicts, lists, strings, numbers, booleans and `None`.
    """
    if value is HIDDEN:
        return UNKNOWN
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [to_json(v) for v in value]
    if isinstance(value, frozendict):
        return {str(k): to_json(v) for k, v in value.items()}
    if is_dataclass(value):
        return {"type": _type_name(value, suffix)} | {
            f.name: to_json(getattr(value, f.name), "Claim") for f in fields(value)
        }
    return value


def _awaiting(state: GameState) -> list[int]:
    """Returns the UIDs of the players the game is waiting on."""
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
    """Returns a JSON-serializable view of the state, scrubbed for the given viewer.

    Args:
        state: The game state to render; it is scrubbed for the viewer first.
        viewer_uid: UID of the player who will see the view.

    Returns:
        A dict with `viewer`, `players`, `board`, `government`, `turn`, `timeline` and `knowledge` sections.

    Raises:
        TyrantError: If the viewer is not in the game.
    """
    state = scrub_state(state, viewer_uid)
    viewer = next((p for p in state.players if p.uid == viewer_uid), None)
    if viewer is None:
        raise TyrantError(f"Viewer with UID {viewer_uid} not found")

    return {
        "viewer": {
            "uid": viewer.uid,
            "role": to_json(viewer.role),
            "party": to_json(viewer.party),
            "alive": viewer.is_alive,
            "teammates": [
                {"uid": p.uid, "role": to_json(p.role)}
                for p in state.players
                if p.uid != viewer_uid and p.role is not HIDDEN
            ],
        },
        "players": [
            {
                "uid": p.uid,
                "party": to_json(p.party),
                "role": to_json(p.role),
                "alive": p.is_alive,
            }
            for p in state.players
        ],
        "board": {
            "liberal_policies": state.board.liberal_played,
            "liberal_policies_to_win": LIBERAL_TILES_TO_WIN,
            "fascist_policies": state.board.fascist_played,
            "fascist_policies_to_win": FASCIST_TILES_TO_WIN,
            "fascist_track": to_json(FASCIST_TRACKS[state.board.player_count]),
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
            "phase": to_json(state.phase),
            "awaiting": _awaiting(state),
            "active_power": to_json(state.active_power),
            "hand": to_json(state.drawn_policies),
            "winner": to_json(state.winner),
            "discussion": None
            if state.discussion is None
            else {
                "context": to_json(state.discussion.context),
                "round": state.discussion.current_round,
                "rounds": state.discussion.rounds,
            },
        },
        "timeline": [to_json(e, "Event") for e in state.events],
        "knowledge": [to_json(k, "Knowledge") for k in state.knowledge],
    }


def _player(uid: int | None) -> str:
    """Returns a player's display name, or `none`."""
    return "none" if uid is None else f"Player {uid}"


def _player_list(uids: list[int]) -> str:
    """Returns a comma-separated list of player names, or `none`."""
    return ", ".join(_player(uid) for uid in uids) or "none"


def _yes_no(value: bool) -> str:
    """Returns `yes` or `no`."""
    return "yes" if value else "no"


def _claim_line(entry: dict) -> str:
    """Returns the timeline sentence for a claim event."""
    claim = entry["claim"]
    who = _player(claim["uid"])
    match claim["type"]:
        case "president_enact":
            if claim["policies"] is None:
                return f"President {who} declined to share the 3 drawn policies."
            if claim["discarded"] is None:
                return (
                    f"President {who} claimed drawing {', '.join(claim['policies'])}."
                )
            return (
                f"President {who} claimed drawing {', '.join(claim['policies'])} "
                f"and discarding {claim['discarded']}."
            )
        case "chancellor_enact":
            if claim["policies"] is None:
                return f"Chancellor {who} declined to share the 2 received policies."
            return f"Chancellor {who} claimed receiving {', '.join(claim['policies'])}."
        case "peek":
            if claim["policies"] is None:
                return f"President {who} declined to share the peeked policies."
            return (
                f"President {who} claimed the top 3 policies are, from the top, "
                f"{', '.join(claim['policies'])}."
            )
        case _:
            target = _player(entry["target_uid"])
            if claim["party"] is None:
                return f"President {who} declined to share {target}'s party."
            return f"President {who} claimed {target} is {claim['party']}."


def _timeline_line(entry: dict) -> str:
    """Returns the timeline sentence for an event."""
    match entry["type"]:
        case "nomination":
            return (
                f"President {_player(entry['president_uid'])} nominated "
                f"{_player(entry['chancellor_uid'])} for chancellor."
            )
        case "election":
            votes = entry["votes"]
            ja = [int(uid) for uid, vote in votes.items() if vote == "ja"]
            nein = [int(uid) for uid, vote in votes.items() if vote == "nein"]
            outcome = "passed" if entry["result"] == "ja" else "failed"
            return (
                f"Election of President {_player(entry['president_uid'])} and "
                f"Chancellor {_player(entry['chancellor_uid'])} {outcome} "
                f"(ja: {_player_list(ja)}; nein: {_player_list(nein)})."
            )
        case "policy_enacted":
            if entry["president_uid"] is None:
                return f"A {entry['policy']} policy was top-decked."
            return (
                f"President {_player(entry['president_uid'])} and Chancellor "
                f"{_player(entry['chancellor_uid'])} enacted a {entry['policy']} policy."
            )
        case "veto":
            response = "approved" if entry["approved"] else "denied"
            return (
                f"Chancellor {_player(entry['chancellor_uid'])} proposed a veto and "
                f"President {_player(entry['president_uid'])} {response} it."
            )
        case "claim":
            return _claim_line(entry)
        case "investigation":
            return (
                f"President {_player(entry['president_uid'])} investigated "
                f"{_player(entry['target_uid'])}."
            )
        case "special_election":
            return (
                f"President {_player(entry['president_uid'])} called a special "
                f"election for {_player(entry['target_uid'])}."
            )
        case "execution":
            return (
                f"President {_player(entry['president_uid'])} executed "
                f"{_player(entry['target_uid'])}."
            )
        case "speech":
            if entry["text"] is None:
                return f"{_player(entry['uid'])} passed."
            return f"{_player(entry['uid'])} said: {json.dumps(entry['text'], ensure_ascii=False)}"
        case _:
            return f"Game over: {entry['winner']} win by {entry['condition']}."


def _claim_conflict(first: dict, second: dict) -> str | None:
    """Returns a sentence pointing out a conflict between a government's two policy claims, or `None`."""
    if first["type"] != "claim" or second["type"] != "claim":
        return None
    claims = {e["claim"]["type"]: e for e in (first, second)}
    if claims.keys() != {"president_enact", "chancellor_enact"}:
        return None
    if (first["president_uid"], first["chancellor_uid"]) != (
        second["president_uid"],
        second["chancellor_uid"],
    ):
        return None
    president = claims["president_enact"]["claim"]
    chancellor = claims["chancellor_enact"]["claim"]
    if president["discarded"] is None or chancellor["policies"] is None:
        return None
    passed = list(president["policies"])
    passed.remove(president["discarded"])
    if sorted(passed) == sorted(chancellor["policies"]):
        return None
    return (
        f"These claims conflict: President {_player(president['uid'])} claims passing "
        f"{', '.join(passed)}, but Chancellor {_player(chancellor['uid'])} claims "
        f"receiving {', '.join(chancellor['policies'])}."
    )


def _timeline_lines(timeline: list[dict]) -> list[str]:
    """Returns the timeline sentences, collapsing speeches from all but the last few discussions."""
    starts = [
        i
        for i, entry in enumerate(timeline)
        if entry["type"] == "speech" and (i == 0 or timeline[i - 1]["type"] != "speech")
    ]
    cutoff = starts[-DISCUSSIONS_SHOWN] if len(starts) > DISCUSSIONS_SHOWN else 0
    lines = []
    for i, entry in enumerate(timeline):
        if entry["type"] != "speech" or i >= cutoff:
            line = _timeline_line(entry)
            conflict = _claim_conflict(timeline[i - 1], entry) if i > 0 else None
            lines.append(line if conflict is None else f"{line} {conflict}")
        elif i in starts:
            lines.append(f"Earlier discussion ({entry['context']}) omitted.")
    return lines


def _knowledge_line(entry: dict) -> str:
    """Returns the sentence for one piece of private knowledge."""
    match entry["type"]:
        case "president_draw":
            return (
                f"As president with Chancellor {_player(entry['chancellor_uid'])}, "
                f"you drew {', '.join(entry['policies'])}."
            )
        case "president_discard":
            return (
                f"As president with Chancellor {_player(entry['chancellor_uid'])}, "
                f"you discarded {entry['discarded']}, passed {', '.join(entry['passed'])}."
            )
        case "chancellor_receive":
            return (
                f"As chancellor under President {_player(entry['president_uid'])}, "
                f"you received {', '.join(entry['policies'])}."
            )
        case "peek":
            return (
                "You peeked at the top 3 policies, from the top: "
                f"{', '.join(entry['policies'])}."
            )
        case _:
            return (
                f"You investigated {_player(entry['target_uid'])}: "
                f"{entry['party']} party."
            )


def _knowledge_lines(knowledge: list[dict]) -> list[str]:
    """Returns the knowledge sentences, joining each discard onto the draw before it."""
    lines = []
    for i, entry in enumerate(knowledge):
        if (
            entry["type"] == "president_discard"
            and i > 0
            and knowledge[i - 1]["type"] == "president_draw"
        ):
            lines[-1] = (
                f"{lines[-1].removesuffix('.')}, discarded {entry['discarded']}, "
                f"passed {', '.join(entry['passed'])}."
            )
        else:
            lines.append(_knowledge_line(entry))
    return lines


def render_text(state: GameState, viewer_uid: int) -> str:
    """Returns a prompt-ready Markdown view of the state, scrubbed for the given viewer.

    Args:
        state: The game state to render; it is scrubbed for the viewer first.
        viewer_uid: UID of the player who will see the view.

    Returns:
        Markdown with sections for the viewer, the players, private knowledge, the timeline, the board, the government and the current turn.

    Raises:
        TyrantError: If the viewer is not in the game.
    """
    view = render_dict(state, viewer_uid)
    viewer, board, government, turn = (
        view["viewer"],
        view["board"],
        view["government"],
        view["turn"],
    )

    teammates = ", ".join(
        f"{_player(t['uid'])} ({t['role']})" for t in viewer["teammates"]
    )
    lines = [
        f"# Secret Hitler: {_player(viewer['uid'])}'s view",
        "",
        "## You",
        f"- {_player(viewer['uid'])}",
        f"- Role: {viewer['role']}",
        f"- Party: {viewer['party']}",
        f"- Status: {'alive' if viewer['alive'] else 'dead'}",
        f"- Known teammates: {teammates or 'none'}",
        "",
        "## Players",
        "In seat order:",
    ]
    lines += [
        f"- {_player(p['uid'])}{' (you)' if p['uid'] == viewer['uid'] else ''}: "
        f"party {p['party']}, role {p['role']}, {'alive' if p['alive'] else 'dead'}"
        for p in view["players"]
    ]
    lines += ["", "## Private Knowledge"]
    lines += [f"- {line}" for line in _knowledge_lines(view["knowledge"])] or [
        "- None."
    ]

    lines += ["", "## Timeline"]
    lines += [
        f"{i}. {line}"
        for i, line in enumerate(_timeline_lines(view["timeline"]), start=1)
    ] or ["No events yet."]

    lines += [
        "",
        "## Board",
        f"- Liberal policies: {board['liberal_policies']}/{board['liberal_policies_to_win']}",
        f"- Fascist policies: {board['fascist_policies']}/{board['fascist_policies_to_win']}",
        f"- Fascist track: {', '.join(board['fascist_track'])}",
        f"- Election tracker: {board['election_tracker']}/{board['failures_until_top_deck']}",
        f"- Hitler zone: {_yes_no(board['hitler_zone'])}",
        f"- Veto unlocked: {_yes_no(board['veto_unlocked'])}",
        f"- Draw pile: {board['draw_pile']}, discard pile: {board['discard_pile']}",
        "",
        "## Government",
        f"- President: {_player(government['president'])}",
        f"- Chancellor: {_player(government['chancellor'])}",
        f"- Previous president: {_player(government['previous_president'])}",
        f"- Previous chancellor: {_player(government['previous_chancellor'])}",
        "",
        "## Current Turn",
        f"- Phase: {turn['phase']}",
        f"- Waiting on: {_player_list(turn['awaiting'])}",
    ]
    if turn["discussion"] is not None:
        lines.append(f"- Discussion topic: {turn['discussion']['context']}")
        lines.append(
            f"- Discussion round: {turn['discussion']['round']} of {turn['discussion']['rounds']}"
        )
    if turn["active_power"] != "none":
        lines.append(f"- Active power: {turn['active_power']}")
    if turn["hand"]:
        lines.append(f"- Your hand: {', '.join(turn['hand'])}")
    if turn["winner"] is not None:
        lines.append(f"- Winner: {turn['winner']}")

    return "\n".join(lines) + "\n"
