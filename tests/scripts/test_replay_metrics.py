import copy
import gzip
import json
import re
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.replay_metrics import (
    claim_conflicts,
    claim_lie_rates,
    faults,
    invented_references,
    load,
    main,
    notes_at_cap,
    repeated_speech_rate,
    speech_share,
    unanimous_election_rate,
)
from tyrant.llm.prompt import MAX_NOTES_LENGTH

F = "fascist"
L = "liberal"


def _step(action_type: str, events=(), knowledge=(), notes=None) -> dict:
    return {
        "action": {"type": action_type},
        "fallback": False,
        "notes": notes,
        "events": list(events),
        "knowledge": list(knowledge),
    }


def _election(votes: dict) -> dict:
    return {"type": "election", "votes": votes}


def _speech(uid: int, text: str | None) -> dict:
    return {"type": "speech", "uid": uid, "text": text}


def _claim(
    claim_type: str, uid: int, policies, discarded=None, correction=False
) -> dict:
    claim = {"type": claim_type, "uid": uid, "policies": policies}
    if discarded is not None:
        claim["discarded"] = discarded
    event = {"type": "claim", "claim": claim}
    if correction:
        event["correction"] = True
    return event


def _government(president: int, chancellor: int, drawn, discarded, passed) -> list:
    return [
        _step(
            "vote",
            [_election({"0": "ja", "1": "ja", "2": "ja"})],
            [
                {"type": "president_draw", "uid": president, "policies": drawn},
            ],
        ),
        _step(
            "president_discard",
            knowledge=[
                {
                    "type": "president_discard",
                    "uid": president,
                    "discarded": discarded,
                    "passed": passed,
                },
                {"type": "chancellor_receive", "uid": chancellor, "policies": passed},
            ],
        ),
        _step("chancellor_enact", [{"type": "policy_enacted", "policy": F}]),
    ]


def _replay() -> dict:
    steps = [
        *_government(0, 1, [F, F, L], F, [F, L]),
        _step(
            "claim_president_enact",
            [_claim("president_enact", 0, [L, L, F], F)],
            notes="x" * 195,
        ),
        _step("claim_chancellor_enact", [_claim("chancellor_enact", 1, [F, L])]),
        _step("speak", [_speech(0, "I passed a liberal and a fascist to you")]),
        _step("pass", [_speech(1, None)]),
        _step(
            "speak", [_speech(0, "As I said in S5 I passed a liberal and a fascist")]
        ),
        _step("vote", [_election({"0": "ja", "1": "nein", "2": "ja"})]),
        _step("vote", [_election({"0": "nein", "1": "nein", "2": "nein"})]),
        *_government(1, 2, [F, L, L], L, [F, L]),
        _step("claim_president_enact", [_claim("president_enact", 1, [F, F, L], F)]),
        _step("claim_chancellor_enact", [_claim("chancellor_enact", 2, None)]),
    ]
    return {
        "version": 4,
        "players": [
            {"uid": 0, "party": L},
            {"uid": 1, "party": F},
            {"uid": 2, "party": L},
        ],
        "steps": steps,
        "faults": [
            {"reason": "TimeoutError()"},
            {"reason": "InvalidMoveError('Reply has no JSON object with an action')"},
            {"reason": "TimeoutError()"},
        ],
    }


def _v2_replay() -> dict:
    replay = _replay()
    del replay["faults"]
    for step in replay["steps"]:
        del step["notes"]
        step["knowledge"] = [
            k for k in step["knowledge"] if k["type"] != "president_discard"
        ]
        for event in step["events"]:
            if event["type"] == "claim":
                event["claim"].pop("discarded", None)
    return replay


class TestReplayMetrics(unittest.TestCase):
    def setUp(self):
        self.replay = _replay()

    def test_unanimous_election_rate(self):
        """Verifies that unanimous and all-ja elections are counted separately."""
        self.assertEqual(unanimous_election_rate(self.replay), (3, 2, 4))

    def test_claim_lie_rates(self):
        """Verifies that false and declined claims are counted per party."""
        self.assertEqual(
            claim_lie_rates(self.replay),
            {"liberal": (1, 1, 2), "fascist": (1, 0, 2)},
        )

    def test_claim_lie_rates_wrong_discard(self):
        """Verifies that a president claim with the true draw but a false discard is a lie."""
        claim = self.replay["steps"][3]["events"][0]["claim"]
        claim["policies"] = [F, F, L]
        claim["discarded"] = L
        self.assertEqual(claim_lie_rates(self.replay)["liberal"], (1, 1, 2))

    def test_claim_lie_rates_v2(self):
        """Verifies that v2 president claims are checked against the draw alone."""
        self.assertEqual(
            claim_lie_rates(_v2_replay()),
            {"liberal": (1, 1, 2), "fascist": (1, 0, 2)},
        )

    def test_claim_conflicts(self):
        """Verifies that a conflicting government is raised and not resolved."""
        self.assertEqual(claim_conflicts(self.replay), (1, 0))

    def test_claim_conflicts_resolved(self):
        """Verifies that a consistent correction resolves the conflict."""
        self.replay["steps"].insert(
            5,
            _step(
                "correct_claim",
                [_claim("president_enact", 0, [F, F, L], F, correction=True)],
            ),
        )
        self.assertEqual(claim_conflicts(self.replay), (1, 1))

    def test_claim_conflicts_unresolved_by_conflicting_correction(self):
        """Verifies that a correction that still conflicts leaves the conflict unresolved."""
        self.replay["steps"].insert(
            5,
            _step(
                "correct_claim",
                [_claim("president_enact", 0, [L, L, L], L, correction=True)],
            ),
        )
        self.assertEqual(claim_conflicts(self.replay), (1, 0))

    def test_claim_lie_rates_ignore_corrections(self):
        """Verifies that corrections do not count as new claims in the lie rates."""
        self.replay["steps"].insert(
            5,
            _step(
                "correct_claim",
                [_claim("president_enact", 0, [F, F, L], F, correction=True)],
            ),
        )
        self.assertEqual(
            claim_lie_rates(self.replay),
            {"liberal": (1, 1, 2), "fascist": (1, 0, 2)},
        )

    def test_claim_conflicts_v2(self):
        """Verifies that a v2 conflict is a received card missing from the claimed draw."""
        self.assertEqual(claim_conflicts(_v2_replay()), (0, 0))
        replay = _v2_replay()
        replay["steps"][4]["events"][0]["claim"]["policies"] = [L, L]
        self.assertEqual(claim_conflicts(replay), (0, 0))
        replay["steps"][3]["events"][0]["claim"]["policies"] = [F, F, F]
        self.assertEqual(claim_conflicts(replay), (1, 0))

    def test_notes_at_cap(self):
        """Verifies that notes within the margin of the cap are counted."""
        self.assertEqual(notes_at_cap(self.replay), (0, 15))
        self.assertEqual(notes_at_cap(self.replay, cap=200), (1, 15))

    def test_notes_at_cap_defaults_to_max_notes_length(self):
        """Verifies that notes_at_cap counts notes near MAX_NOTES_LENGTH when no cap is given."""
        replay = _replay()
        replay["steps"][3]["notes"] = "x" * (MAX_NOTES_LENGTH - 5)
        self.assertEqual(notes_at_cap(replay), (1, 15))

    def test_speech_share(self):
        """Verifies that speak and pass steps are counted against all steps."""
        self.assertEqual(speech_share(self.replay), (3, 2, 15))

    def test_repeated_speech_rate(self):
        """Verifies that a speech repeating the same player's 3-grams is counted."""
        self.assertEqual(repeated_speech_rate(self.replay), (1, 2))

    def test_repeated_speech_rate_other_player(self):
        """Verifies that repeating another player's words is not counted."""
        self.replay["steps"][7]["events"][0]["uid"] = 2
        self.assertEqual(repeated_speech_rate(self.replay), (0, 2))

    def test_invented_references(self):
        """Verifies that speeches citing a numbered line are counted."""
        self.assertEqual(invented_references(self.replay), (1, 2))

    def test_faults(self):
        """Verifies that faults are counted by exception class with the fallbacks."""
        self.replay["steps"][0]["fallback"] = True
        self.assertEqual(
            faults(self.replay), ({"InvalidMoveError": 1, "TimeoutError": 2}, 1)
        )

    def test_v2_metrics_are_none(self):
        """Verifies that metrics without data in a v2 replay are None."""
        replay = _v2_replay()
        self.assertIsNone(notes_at_cap(replay))
        self.assertIsNone(faults(replay))

    def test_unanimous_election_rate_immutability(self):
        """Verifies that unanimous_election_rate does not mutate the replay."""
        self._assert_unchanged(unanimous_election_rate)

    def test_claim_lie_rates_immutability(self):
        """Verifies that claim_lie_rates does not mutate the replay."""
        self._assert_unchanged(claim_lie_rates)

    def test_claim_conflicts_immutability(self):
        """Verifies that claim_conflicts does not mutate the replay."""
        self._assert_unchanged(claim_conflicts)

    def test_notes_at_cap_immutability(self):
        """Verifies that notes_at_cap does not mutate the replay."""
        self._assert_unchanged(notes_at_cap)

    def test_speech_share_immutability(self):
        """Verifies that speech_share does not mutate the replay."""
        self._assert_unchanged(speech_share)

    def test_repeated_speech_rate_immutability(self):
        """Verifies that repeated_speech_rate does not mutate the replay."""
        self._assert_unchanged(repeated_speech_rate)

    def test_invented_references_immutability(self):
        """Verifies that invented_references does not mutate the replay."""
        self._assert_unchanged(invented_references)

    def test_faults_immutability(self):
        """Verifies that faults does not mutate the replay."""
        self._assert_unchanged(faults)

    def _assert_unchanged(self, metric):
        before = copy.deepcopy(self.replay)
        metric(self.replay)
        self.assertEqual(self.replay, before)


class TestLoad(unittest.TestCase):
    def test_load_gzip(self):
        """Verifies that a gzipped replay file is read."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "game.json.gz"
            with gzip.open(path, "wt", encoding="utf-8") as f:
                json.dump(_replay(), f)
            self.assertEqual(load(path), _replay())

    def test_load_plain(self):
        """Verifies that a plain JSON replay file is read."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "game.json"
            path.write_text(json.dumps(_replay()), encoding="utf-8")
            self.assertEqual(load(path), _replay())

    def test_load_immutability(self):
        """Verifies that load returns a new dict on each call."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "game.json"
            path.write_text(json.dumps(_replay()), encoding="utf-8")
            self.assertIsNot(load(path), load(path))


class TestMain(unittest.TestCase):
    def _run(self, argv: list[str]) -> str:
        output = StringIO()
        with redirect_stdout(output):
            main(argv)
        return output.getvalue()

    def test_main_table(self):
        """Verifies that main prints one column per replay file."""
        with TemporaryDirectory() as directory:
            plain = Path(directory) / "a.json"
            plain.write_text(json.dumps(_replay()), encoding="utf-8")
            old = Path(directory) / "b.json"
            old.write_text(json.dumps(_v2_replay()), encoding="utf-8")
            output = self._run([str(plain), str(old)])
        rows = [re.split(r"\s{2,}", line) for line in output.splitlines()]
        self.assertEqual(rows[0], ["Metric", "a.json", "b.json"])
        self.assertIn(["Unanimous elections", "3/4 (75%)", "3/4 (75%)"], rows)
        self.assertIn(["Notes at cap", "0/15 (0%)", "n/a"], rows)

    def test_main_notes_cap(self):
        """Verifies that main passes the notes cap option to the notes metric."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "a.json"
            path.write_text(json.dumps(_replay()), encoding="utf-8")
            output = self._run([str(path), "--notes-cap", "200"])
        self.assertIn("Notes at cap              1/15 (7%)", output)

    def test_main_immutability(self):
        """Verifies that main does not mutate its argument list."""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "a.json"
            path.write_text(json.dumps(_replay()), encoding="utf-8")
            argv = [str(path)]
            self._run(argv)
            self.assertEqual(argv, [str(path)])
