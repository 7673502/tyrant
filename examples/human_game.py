import asyncio

from tyrant import GameRunner, HumanAgent, RandomAgent


async def main():
    agents = [HumanAgent(0)] + [RandomAgent(uid) for uid in range(1, 5)]
    runner = GameRunner(agents, discussion_enabled=True, timeout=None)
    final_state = await runner.run()
    print(f"Winner: {final_state.winner}")


if __name__ == "__main__":
    asyncio.run(main())
