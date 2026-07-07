import asyncio

from tyrant.agents.random_agent import RandomBot
from tyrant.engine.game_runner import GameRunner
from tyrant.models.enums import Party


async def main():
    liberal_win = 0
    fascist_win = 0

    for i in range(1000):
        players = tuple(RandomBot(i) for i in range(10))
        runner = GameRunner(agents=players)
        end_state = await runner.run()
        if end_state.winner is Party.LIBERAL:
            liberal_win += 1
        else:
            fascist_win += 1

    print(f"Liberal wins: {liberal_win}\nFascist wins: {fascist_win}")


if __name__ == "__main__":
    asyncio.run(main())
