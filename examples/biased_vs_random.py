import asyncio
from typing import Callable

from tyrant.agents.biased_random import BiasedRandomAgent
from tyrant.agents.random_agent import RandomAgent
from tyrant.engine.game_runner import GameRunner
from tyrant.models.agent import Agent
from tyrant.models.enums import Party, Role


async def batch_run(
    liberal_cls: Callable[[int], Agent],
    fascist_cls: Callable[[int], Agent],
    trials: int = 100,
) -> tuple[int, int]:
    liberal_win = 0
    fascist_win = 0

    for i in range(trials):
        players = tuple(liberal_cls(i) for i in range(2)) + tuple(
            fascist_cls(i) for i in range(2, 5)
        )
        roles = {
            0: Role.FASCIST,
            1: Role.HITLER,
            2: Role.LIBERAL,
            3: Role.LIBERAL,
            4: Role.LIBERAL,
        }
        runner = GameRunner(agents=players, roles=roles)
        end_state = await runner.run()
        if end_state.winner is Party.LIBERAL:
            liberal_win += 1
        else:
            fascist_win += 1

    return (liberal_win, fascist_win)


async def main():
    trials = 200
    biased_liberal_wins, random_fascist_wins = await batch_run(
        liberal_cls=BiasedRandomAgent, fascist_cls=RandomAgent, trials=trials
    )
    biased_fascist_wins, random_liberal_wins = await batch_run(
        liberal_cls=RandomAgent, fascist_cls=BiasedRandomAgent, trials=trials
    )

    biased_liberal_win_rate = biased_liberal_wins / trials
    biased_fascist_win_rate = biased_fascist_wins / trials
    random_liberal_win_rate = random_liberal_wins / trials
    random_fascist_win_rate = random_fascist_wins / trials

    print(f"{'Team':<20} {'Liberal Win %':>16} {'Fascist Win %':>16}")
    print("-" * 55)
    print(
        f"{'RandomAgent':<20} {random_liberal_win_rate:>16.1%} {random_fascist_win_rate:>16.1%}"
    )
    print(
        f"{'BiasedRandomAgent':<20} {biased_liberal_win_rate:>16.1%} {biased_fascist_win_rate:>16.1%}"
    )
    print(
        f"\nEach team played {trials} games as liberal and {trials} games as fascist."
    )


if __name__ == "__main__":
    asyncio.run(main())
