"""Simple bundled agents for testing and baselines."""

from tyrant.agents.biased_random_agent import BiasedRandomAgent
from tyrant.agents.human_agent import HumanAgent
from tyrant.agents.random_agent import RandomAgent

__all__ = [
    "BiasedRandomAgent",
    "HumanAgent",
    "RandomAgent",
]
