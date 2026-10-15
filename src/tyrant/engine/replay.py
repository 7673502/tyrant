import gzip
import json
from pathlib import Path
from typing import Final

from tyrant.engine.game_runner import AGENT_FILLED_FIELDS
from tyrant.engine.renderer import to_json
from tyrant.engine.router import apply_action
from tyrant.models.action import Action
from tyrant.models.board import FASCIST_TRACKS
from tyrant.models.event import GameOverEvent
from tyrant.models.game_state import GameState
from tyrant.models.replay import Replay

REPLAY_VERSION: Final = 2


def _action(action: Action) -> dict:
    """Returns the action as JSON, leaving out the fields an agent may fill in."""
    return {
        key: value
        for key, value in to_json(action, "Action").items()
        if key not in AGENT_FILLED_FIELDS
    }


def _snapshot(state: GameState) -> dict:
    """Returns the public board snapshot stored with each replay step."""
    return {
        "phase": to_json(state.phase),
        "president": state.players[state.president_index].uid,
        "chancellor": state.chancellor,
        "previous_president": state.previous_president,
        "previous_chancellor": state.previous_chancellor,
        "alive": [p.uid for p in state.players if p.is_alive],
        "liberal_policies": state.board.liberal_played,
        "fascist_policies": state.board.fascist_played,
        "election_tracker": state.election_tracker.failed_elections,
        "draw_pile": len(state.deck.draw_pile),
        "discard_pile": len(state.deck.discard_pile),
        "hand": to_json(state.drawn_policies),
        "votes": to_json(state.ballot_box.votes),
        "active_power": to_json(state.active_power),
        "discussion": None
        if state.discussion is None
        else {
            "context": to_json(state.discussion.context),
            "round": state.discussion.current_round,
            "rounds": state.discussion.rounds,
            "speaker": state.discussion.current_speaker,
        },
    }


def _result(state: GameState) -> dict | None:
    """Returns the winner and win condition, or `None` if the game has not ended."""
    game_over = next(
        (e for e in reversed(state.events) if isinstance(e, GameOverEvent)), None
    )
    if game_over is None:
        return None
    return {
        "winner": to_json(game_over.winner),
        "condition": to_json(game_over.condition),
    }


def replay_dict(replay: Replay) -> dict:
    """Returns a JSON-serializable replay with a full board snapshot after every step.

    Args:
        replay: The replay to convert.

    Returns:
        Plain JSON values holding the settings, every player's hidden role, the initial snapshot, one entry per step and the result.
    """
    initial = replay.initial_state
    state = initial
    steps = []
    for index, step in enumerate(replay.steps):
        next_state = apply_action(state, step.action, step.uid)
        steps.append(
            {
                "index": index,
                "uid": step.uid,
                "action": _action(step.action),
                "fallback": step.fallback,
                "events": [
                    to_json(e, "Event") for e in next_state.events[len(state.events) :]
                ],
                "knowledge": [
                    to_json(k, "Knowledge")
                    for k in next_state.knowledge[len(state.knowledge) :]
                ],
                "state": _snapshot(next_state),
            }
        )
        state = next_state

    return {
        "version": REPLAY_VERSION,
        "settings": {
            "player_count": len(initial.players),
            "discussion_enabled": initial.discussion_enabled,
            "discussion_rounds": initial.discussion_rounds,
            "fascist_track": to_json(FASCIST_TRACKS[initial.board.player_count]),
        },
        "players": [
            {
                "uid": p.uid,
                "seat": seat,
                "role": to_json(p.role),
                "party": to_json(p.party),
            }
            for seat, p in enumerate(initial.players)
        ],
        "initial": _snapshot(initial),
        "steps": steps,
        "result": _result(state),
    }


def write_replay(replay: Replay, path: str | Path) -> None:
    """Writes the replay to a gzipped JSON file.

    Args:
        replay: The replay to write.
        path: The file to write.
    """
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(replay_dict(replay), f, separators=(",", ":"))


def read_replay(path: str | Path) -> dict:
    """Reads a gzipped JSON replay file into plain dicts.

    Args:
        path: The file to read.

    Returns:
        The replay in the format returned by `replay_dict`.
    """
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)
