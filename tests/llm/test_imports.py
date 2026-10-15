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

    def test_agent_import_without_litellm_names_extra(self):
        """Verifies that importing tyrant.llm.agent without litellm raises an ImportError naming the llm extra."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; sys.modules['litellm'] = None\n"
                "try:\n    import tyrant.llm.agent\n"
                "except ImportError as e:\n    print(e)",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn('pip install "tyrant[llm]"', result.stdout)


if __name__ == "__main__":
    unittest.main()
