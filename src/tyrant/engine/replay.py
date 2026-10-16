import gzip
import json
from importlib.metadata import version
from pathlib import Path
from typing import Final

from tyrant.engine.renderer import to_json
from tyrant.engine.router import apply_action
from tyrant.models.action import AGENT_FILLED_FIELDS, Action
from tyrant.models.agent_fault import AgentFault
from tyrant.models.board import FASCIST_TRACKS
from tyrant.models.event import GameOverEvent
from tyrant.models.game_state import GameState
from tyrant.models.replay import Replay, ReplayStep

REPLAY_VERSION: Final = 4
TYRANT_VERSION: Final = version("tyrant")


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


def result_dict(state: GameState) -> dict | None:
    """Returns the winner and win condition as JSON.

    Args:
        state: The state to read the result from.

    Returns:
        The winner and win condition, or `None` if the game has not ended.
    """
    game_over = next(
        (e for e in reversed(state.events) if isinstance(e, GameOverEvent)), None
    )
    if game_over is None:
        return None
    return {
        "winner": to_json(game_over.winner),
        "condition": to_json(game_over.condition),
    }


def step_dict(
    index: int, step: ReplayStep, state: GameState, next_state: GameState
) -> dict:
    """Returns one replay step as JSON.

    Args:
        index: The step's position in the replay.
        step: The step.
        state: The state before the step.
        next_state: The state after the step.

    Returns:
        The step's action, the events and private knowledge it produced, the agent's notes and the board snapshot after it.
    """
    return {
        "index": index,
        "uid": step.uid,
        "action": _action(step.action),
        "fallback": step.fallback,
        "notes": step.notes,
        "events": [to_json(e, "Event") for e in next_state.events[len(state.events) :]],
        "knowledge": [
            to_json(k, "Knowledge")
            for k in next_state.knowledge[len(state.knowledge) :]
        ],
        "state": _snapshot(next_state),
    }


def fault_dict(fault: AgentFault) -> dict:
    """Returns one agent fault as JSON.

    Args:
        fault: The failed attempt.

    Returns:
        The step, player, phase, reason, rejected reply and whether the runner fell back.
    """
    return {
        "step": fault.step,
        "uid": fault.uid,
        "phase": to_json(fault.phase),
        "reason": fault.reason,
        "reply": fault.reply,
        "fell_back": fault.fell_back,
    }


def replay_dict(replay: Replay) -> dict:
    """Returns a JSON-serializable replay with a full board snapshot after every step.

    Args:
        replay: The replay to convert.

    Returns:
        Plain JSON values holding the settings, every player's hidden role and agent, the initial snapshot, one entry per step, every agent fault and the result.
    """
    initial = replay.initial_state
    state = initial
    steps = []
    for index, step in enumerate(replay.steps):
        next_state = apply_action(state, step.action, step.uid)
        steps.append(step_dict(index, step, state, next_state))
        state = next_state

    return {
        "version": REPLAY_VERSION,
        "tyrant_version": TYRANT_VERSION,
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
                "agent": dict(replay.agents[p.uid]) if p.uid in replay.agents else None,
            }
            for seat, p in enumerate(initial.players)
        ],
        "initial": _snapshot(initial),
        "steps": steps,
        "faults": [fault_dict(fault) for fault in replay.faults],
        "result": result_dict(state),
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
