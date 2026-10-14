import gzip
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.scripted_game import record_first_legal_actions
from tyrant.engine.renderer import to_json
from tyrant.engine.replay import _snapshot, read_replay, replay_dict, write_replay
from tyrant.engine.router import apply_action, get_legal_actions
from tyrant.models.action import SpeakAction
from tyrant.models.enums import GamePhase
from tyrant.models.event import GameOverEvent
from tyrant.models.game_state import create_game
from tyrant.models.replay import Replay, record_step

UIDS = (1, 2, 3, 4, 5)


def _speech_replay() -> Replay:
    state = create_game(UIDS, 42, discussion_enabled=True)
    replay = Replay(initial_state=state)
    while state.phase != GamePhase.DISCUSSION:
        uid, action = next(
            (p.uid, get_legal_actions(state, p.uid)[0])
            for p in state.players
            if get_legal_actions(state, p.uid)
        )
        state = apply_action(state, action, uid)
        replay = record_step(replay, uid, action)
    speaker = state.discussion.current_speaker
    speech = SpeakAction(description="Say something", message="  I   am liberal. ")
    return record_step(replay, speaker, speech)


class TestReplayDict(unittest.TestCase):
    def setUp(self):
        self.replay, self.final = record_first_legal_actions(create_game(UIDS, 42))
        self.view = replay_dict(self.replay)

    def test_replay_dict_step_count(self):
        """Verifies that the replay has one step per applied action."""
        self.assertEqual(len(self.view["steps"]), len(self.replay.steps))
        self.assertEqual(
            [s["index"] for s in self.view["steps"]],
            list(range(len(self.replay.steps))),
        )

    def test_replay_dict_events_cover_log(self):
        """Verifies that the step events joined in order equal the final event log."""
        events = [e for s in self.view["steps"] for e in s["events"]]
        self.assertEqual(events, [to_json(e, "Event") for e in self.final.events])

    def test_replay_dict_knowledge_covers_log(self):
        """Verifies that the step knowledge joined in order equals the final knowledge log."""
        knowledge = [k for s in self.view["steps"] for k in s["knowledge"]]
        self.assertEqual(
            knowledge, [to_json(k, "Knowledge") for k in self.final.knowledge]
        )

    def test_replay_dict_last_state_matches_final(self):
        """Verifies that the last step's snapshot matches the final game state."""
        self.assertEqual(self.view["steps"][-1]["state"], _snapshot(self.final))

    def test_replay_dict_result(self):
        """Verifies that the result reports the winner and condition of the game."""
        game_over = self.final.events[-1]
        self.assertIsInstance(game_over, GameOverEvent)
        self.assertEqual(
            self.view["result"],
            {
                "winner": game_over.winner.value,
                "condition": game_over.condition.value,
            },
        )

    def test_replay_dict_format(self):
        """Verifies the exact format of the header, initial snapshot, and first step."""
        self.assertEqual(self.view["version"], 1)
        self.assertEqual(
            self.view["settings"],
            {
                "player_count": 5,
                "discussion_enabled": False,
                "discussion_rounds": 2,
                "fascist_track": [
                    "none",
                    "none",
                    "policy_peek",
                    "execution",
                    "execution",
                    "none",
                ],
            },
        )
        self.assertEqual(
            self.view["players"],
            [
                {"uid": 4, "seat": 0, "role": "liberal", "party": "liberal"},
                {"uid": 3, "seat": 1, "role": "liberal", "party": "liberal"},
                {"uid": 1, "seat": 2, "role": "liberal", "party": "liberal"},
                {"uid": 5, "seat": 3, "role": "hitler", "party": "fascist"},
                {"uid": 2, "seat": 4, "role": "fascist", "party": "fascist"},
            ],
        )
        initial = {
            "phase": "nomination",
            "president": 4,
            "chancellor": None,
            "previous_president": None,
            "previous_chancellor": None,
            "alive": [4, 3, 1, 5, 2],
            "liberal_policies": 0,
            "fascist_policies": 0,
            "election_tracker": 0,
            "draw_pile": 17,
            "discard_pile": 0,
            "hand": [],
            "votes": {},
            "active_power": "none",
            "discussion": None,
        }
        self.assertEqual(self.view["initial"], initial)
        self.assertEqual(
            self.view["steps"][0],
            {
                "index": 0,
                "uid": 4,
                "action": {"type": "nominate", "target_uid": 3},
                "events": [
                    {"type": "nomination", "president_uid": 4, "chancellor_uid": 3}
                ],
                "knowledge": [],
                "state": initial | {"phase": "voting", "chancellor": 3},
            },
        )

    def test_replay_dict_omits_agent_filled_fields(self):
        """Verifies that actions leave out the description and message fields."""
        for step in replay_dict(_speech_replay())["steps"]:
            self.assertNotIn("description", step["action"])
            self.assertNotIn("message", step["action"])

    def test_replay_dict_speech_text_in_event(self):
        """Verifies that a speech step carries its cleaned text in the speech event."""
        replay = _speech_replay()
        step = replay_dict(replay)["steps"][-1]
        self.assertEqual(step["action"], {"type": "speak"})
        self.assertEqual(
            step["events"],
            [
                {
                    "type": "speech",
                    "uid": replay.steps[-1].uid,
                    "text": "I am liberal.",
                    "context": step["state"]["discussion"]["context"],
                }
            ],
        )

    def test_replay_dict_snapshot_discussion(self):
        """Verifies that a snapshot during discussion reports the context, round, and speaker."""
        step = replay_dict(_speech_replay())["steps"][-1]
        discussion = step["state"]["discussion"]
        self.assertEqual(set(discussion), {"context", "round", "rounds", "speaker"})
        self.assertEqual(discussion["rounds"], 2)

    def test_replay_dict_is_json_serializable(self):
        """Verifies that every value in the replay is plain JSON."""
        self.assertEqual(json.loads(json.dumps(self.view)), self.view)

    def test_replay_dict_without_steps(self):
        """Verifies that a replay with no steps has no result and no steps."""
        view = replay_dict(Replay(initial_state=self.replay.initial_state))
        self.assertIsNone(view["result"])
        self.assertEqual(view["steps"], [])

    def test_replay_dict_immutability(self):
        """Verifies that replay_dict does not mutate the replay."""
        steps = self.replay.steps
        initial_state = self.replay.initial_state
        replay_dict(self.replay)
        self.assertIs(self.replay.steps, steps)
        self.assertIs(self.replay.initial_state, initial_state)


class TestReplayFile(unittest.TestCase):
    def test_write_replay_round_trip(self):
        """Verifies that a written replay is gzipped and reads back as replay_dict."""
        replay, _ = record_first_legal_actions(create_game(UIDS, 42))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "game.json.gz"
            write_replay(replay, path)
            self.assertEqual(path.read_bytes()[:2], b"\x1f\x8b")
            self.assertEqual(read_replay(path), replay_dict(replay))
            with gzip.open(path, "rt") as f:
                self.assertNotIn(" ", f.read(200))


if __name__ == "__main__":
    unittest.main()
