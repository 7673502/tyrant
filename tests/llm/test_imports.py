import subprocess
import sys
import unittest


class TestImports(unittest.TestCase):
    def test_imports_do_not_load_litellm(self):
        """Verifies that importing tyrant and tyrant.llm leaves litellm out of sys.modules."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, tyrant, tyrant.llm; print('litellm' in sys.modules)",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(result.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
