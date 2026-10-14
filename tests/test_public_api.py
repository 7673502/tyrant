import unittest

import tyrant
import tyrant.agents
import tyrant.engine
import tyrant.models


class TestPublicApi(unittest.TestCase):
    def test_tyrant_exports(self):
        """Every name in tyrant.__all__ is importable from tyrant."""
        for name in tyrant.__all__:
            self.assertTrue(hasattr(tyrant, name), name)

    def test_agents_exports(self):
        """Every name in tyrant.agents.__all__ is importable from tyrant.agents."""
        for name in tyrant.agents.__all__:
            self.assertTrue(hasattr(tyrant.agents, name), name)

    def test_engine_exports(self):
        """Every name in tyrant.engine.__all__ is importable from tyrant.engine."""
        for name in tyrant.engine.__all__:
            self.assertTrue(hasattr(tyrant.engine, name), name)

    def test_models_exports(self):
        """Every name in tyrant.models.__all__ is importable from tyrant.models."""
        for name in tyrant.models.__all__:
            self.assertTrue(hasattr(tyrant.models, name), name)

    def test_tyrant_reexports_are_the_same_objects(self):
        """Names re-exported by tyrant are the same objects as in their subpackages."""
        for name in tyrant.__all__:
            for package in (tyrant.agents, tyrant.engine, tyrant.models):
                if name in package.__all__:
                    self.assertIs(getattr(tyrant, name), getattr(package, name))


if __name__ == "__main__":
    unittest.main()
