import copy
import json
import unittest
from dataclasses import replace

from tests.scripted_game import play_first_legal_actions
from tyrant.engine.renderer import render_dict
from tyrant.exceptions import TyrantError
from tyrant.models.enums import GamePhase, Role, Vote
from tyrant.models.game_state import (
    GameState,
    cast_vote,
    create_game,
    nominate_chancellor,
    scrub_state,
)

UIDS = (1, 2, 3, 4, 5, 6, 7)


def _uid_with_role(state: GameState, role: Role) -> int:
    return next(p.uid for p in state.players if p.role == role)


def _nominated(state: GameState) -> GameState:
    president = state.players[state.president_index].uid
    return nominate_chancellor(
        state, next(p.uid for p in state.players if p.uid != president)
    )


class TestRenderDict(unittest.TestCase):
    def setUp(self):
        self.state = create_game(UIDS, 42)
        self.states = play_first_legal_actions(
            create_game(UIDS, 42, discussion_enabled=True)
        )

    def test_render_dict_immutability(self):
        """Verifies that render_dict returns a new dict and does not mutate the input state."""
        state = scrub_state(self.states[-1], 1)
        before = copy.deepcopy(state)
        first = render_dict(state, 1)
        second = render_dict(state, 1)
        self.assertEqual(state, before)
        self.assertIsNot(first, second)
        self.assertEqual(first, second)

    def test_render_dict_is_json_serializable(self):
        """Verifies that every rendered state in a full game round-trips through JSON."""
        for state in self.states:
            for uid in UIDS:
                rendered = render_dict(scrub_state(state, uid), uid)
                self.assertEqual(json.loads(json.dumps(rendered)), rendered)

    def test_render_dict_hidden_renders_as_unknown(self):
        """Verifies that hidden values render as unknown and never as the HIDDEN sentinel."""
        liberal = _uid_with_role(self.state, Role.LIBERAL)
        rendered = render_dict(scrub_state(self.state, liberal), liberal)
        text = json.dumps(rendered)
        self.assertNotIn("HIDDEN", text)
        others = [p for p in rendered["players"] if p["uid"] != liberal]
        self.assertTrue(all(p["party"] == "unknown" for p in others))
        self.assertTrue(all(p["role"] == "unknown" for p in others))

    def test_render_dict_liberal_has_no_teammates(self):
        """Verifies that a liberal viewer has no known teammates."""
        liberal = _uid_with_role(self.state, Role.LIBERAL)
        viewer = render_dict(scrub_state(self.state, liberal), liberal)["viewer"]
        self.assertEqual(viewer["role"], "liberal")
        self.assertEqual(viewer["teammates"], [])

    def test_render_dict_fascist_sees_teammates(self):
        """Verifies that a fascist viewer sees every other fascist and Hitler."""
        fascist = _uid_with_role(self.state, Role.FASCIST)
        viewer = render_dict(scrub_state(self.state, fascist), fascist)["viewer"]
        expected = [
            {"uid": p.uid, "role": p.role.value}
            for p in self.state.players
            if p.uid != fascist and p.role in (Role.FASCIST, Role.HITLER)
        ]
        self.assertEqual(viewer["teammates"], expected)

    def test_render_dict_board(self):
        """Verifies that the board section reports policies, tracker and piles."""
        board = render_dict(scrub_state(self.state, 1), 1)["board"]
        self.assertEqual(board["liberal_policies"], 0)
        self.assertEqual(board["fascist_policies"], 0)
        self.assertEqual(board["election_tracker"], 0)
        self.assertEqual(board["draw_pile"], 17)
        self.assertEqual(len(board["fascist_track"]), 6)

    def test_render_dict_awaiting_nomination(self):
        """Verifies that the president must act during nomination."""
        turn = render_dict(scrub_state(self.state, 1), 1)["turn"]
        self.assertEqual(turn["phase"], "nomination")
        self.assertEqual(turn["awaiting"], [self.state.players[0].uid])

    def test_render_dict_awaiting_voters(self):
        """Verifies that only players who have not voted are awaited during voting."""
        state = _nominated(self.state)
        state = cast_vote(state, 1, Vote.JA)
        turn = render_dict(scrub_state(state, 2), 2)["turn"]
        self.assertEqual(turn["awaiting"], [p.uid for p in state.players if p.uid != 1])

    def test_render_dict_awaiting_speaker(self):
        """Verifies that the current speaker is awaited during discussion."""
        state = _nominated(replace(self.state, discussion_enabled=True))
        turn = render_dict(scrub_state(state, 1), 1)["turn"]
        self.assertEqual(turn["phase"], "discussion")
        self.assertEqual(turn["awaiting"], [state.discussion.current_speaker])

    def test_render_dict_awaiting_claimants(self):
        """Verifies that only pending claimants are awaited during policy claims."""
        state = replace(
            self.state,
            phase=GamePhase.CLAIM_POLICIES,
            chancellor=2,
            pending_president_enact_claim=False,
            pending_chancellor_enact_claim=True,
        )
        turn = render_dict(scrub_state(state, 1), 1)["turn"]
        self.assertEqual(turn["awaiting"], [2])

    def test_render_dict_game_over(self):
        """Verifies that a finished game awaits nobody and reports the winner."""
        final = self.states[-1]
        turn = render_dict(scrub_state(final, 1), 1)["turn"]
        self.assertEqual(turn["awaiting"], [])
        self.assertEqual(turn["winner"], final.winner.value)
        self.assertEqual(
            render_dict(scrub_state(final, 1), 1)["timeline"][-1]["type"], "game_over"
        )

    def test_render_dict_timeline_matches_events(self):
        """Verifies that the timeline has one typed entry per public event in order."""
        final = self.states[-1]
        timeline = render_dict(scrub_state(final, 1), 1)["timeline"]
        self.assertEqual(len(timeline), len(final.events))
        self.assertEqual(timeline[0]["type"], "nomination")
        self.assertIn("speech", {entry["type"] for entry in timeline})

    def test_render_dict_knowledge_is_viewers_own(self):
        """Verifies that only the viewer's private knowledge is rendered."""
        final = self.states[-1]
        for uid in UIDS:
            knowledge = render_dict(scrub_state(final, uid), uid)["knowledge"]
            self.assertEqual(
                len(knowledge), sum(1 for k in final.knowledge if k.uid == uid)
            )
            self.assertTrue(all(k["uid"] == uid for k in knowledge))

    def test_render_dict_unknown_viewer(self):
        """Verifies that rendering for a viewer not in the game raises TyrantError."""
        with self.assertRaises(TyrantError):
            render_dict(self.state, 99)


if __name__ == "__main__":
    unittest.main()
