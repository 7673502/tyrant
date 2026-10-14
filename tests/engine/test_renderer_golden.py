import json
import unittest
from pathlib import Path

from tests.scripted_game import play_first_legal_actions
from tyrant.engine.renderer import render_dict, render_text
from tyrant.models.enums import Role
from tyrant.models.game_state import GameState, create_game, scrub_state

GOLDEN_DIR = Path(__file__).parent / "golden"
SEVEN_PLAYER_GAME = play_first_legal_actions(create_game((1, 2, 3, 4, 5, 6, 7), 42))
FIVE_PLAYER_GAME = play_first_legal_actions(create_game((1, 2, 3, 4, 5), 42))
CASES = (
    ("seven_player_midgame_liberal", SEVEN_PLAYER_GAME[40], Role.LIBERAL),
    ("seven_player_midgame_fascist", SEVEN_PLAYER_GAME[40], Role.FASCIST),
    ("seven_player_final_hitler", SEVEN_PLAYER_GAME[-1], Role.HITLER),
    ("five_player_final_liberal", FIVE_PLAYER_GAME[-1], Role.LIBERAL),
)


def golden_case(state: GameState, role: Role) -> tuple[str, dict]:
    """Renders the state as text and as a dict for the first player with the given role."""
    uid = next(p.uid for p in state.players if p.role == role)
    scrubbed = scrub_state(state, uid)
    return render_text(scrubbed, uid), render_dict(scrubbed, uid)


class TestRendererGolden(unittest.TestCase):
    def test_render_text_matches_golden(self):
        """Verifies that render_text output matches the checked-in golden text files."""
        for name, state, role in CASES:
            with self.subTest(case=name):
                text, _ = golden_case(state, role)
                self.assertEqual(text, (GOLDEN_DIR / f"{name}.txt").read_text())

    def test_render_dict_matches_golden(self):
        """Verifies that render_dict output matches the checked-in golden JSON files."""
        for name, state, role in CASES:
            with self.subTest(case=name):
                _, rendered = golden_case(state, role)
                golden = json.loads((GOLDEN_DIR / f"{name}.json").read_text())
                self.assertEqual(rendered, golden)


if __name__ == "__main__":
    unittest.main()
