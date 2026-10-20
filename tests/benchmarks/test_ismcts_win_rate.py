import unittest
from contextlib import redirect_stdout
from io import StringIO

from benchmarks.ismcts_win_rate import HEROES, main, measure
from tyrant.models.enums import Role


class TestMeasure(unittest.TestCase):
    def test_measure_heroes(self):
        """Verifies that every hero finishes a game and only ISMCTS heroes record search times."""
        for hero in HEROES:
            with self.subTest(hero=hero):
                result = measure(hero, Role.LIBERAL, 0, 5)
                self.assertIsInstance(result["won"], bool)
                self.assertIsInstance(result["seconds"], tuple)
                self.assertEqual(bool(result["seconds"]), hero != "biased")


class TestMain(unittest.TestCase):
    def _run(self, argv: list[str]) -> str:
        output = StringIO()
        with redirect_stdout(output):
            main(argv)
        return output.getvalue()

    def test_main_table(self):
        """Verifies that main prints a header and one row for the hero."""
        lines = self._run(
            ["--hero", "uniform", "--iterations", "5", "--games", "2", "--workers", "1"]
        ).splitlines()
        self.assertEqual(lines[0].split()[:2], ["Hero", "Iterations"])
        self.assertEqual(lines[1].split()[:3], ["uniform", "5", "2"])
        self.assertEqual(len(lines), 2)

    def test_main_immutability(self):
        """Verifies that main does not mutate its argument list."""
        argv = ["--hero", "biased", "--games", "2", "--workers", "1"]
        self._run(argv)
        self.assertEqual(argv, ["--hero", "biased", "--games", "2", "--workers", "1"])


if __name__ == "__main__":
    unittest.main()
