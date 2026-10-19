import asyncio
import os
import sys

from tyrant import GameRunner
from tyrant.llm.agent import LLMAgent


async def main():
    model = os.environ.get("TYRANT_MODEL")
    if not model:
        sys.exit("Set TYRANT_MODEL to a litellm model, e.g. anthropic/claude-haiku-5-5")

    agents = tuple(LLMAgent(uid, model) for uid in range(5))
    runner = GameRunner(agents, discussion_enabled=True)
    end_state = await runner.run()

    prompt_tokens = sum(agent.prompt_tokens for agent in agents)
    completion_tokens = sum(agent.completion_tokens for agent in agents)
    cached_tokens = sum(agent.cached_tokens for agent in agents)
    fallbacks = sum(fault.fell_back for fault in runner.faults)

    print(f"Winner: {end_state.winner}")
    print(f"Faults: {len(runner.faults)} ({fallbacks} fell back to a random action)")
    for fault in runner.faults:
        print(
            f"  Step {fault.step}, Player {fault.uid} in {fault.phase}: {fault.reason}"
        )
        if fault.reply is not None:
            print(f"    Rejected reply: {fault.reply!r}")
    print(f"Prompt tokens: {prompt_tokens} ({cached_tokens} cached)")
    print(f"Completion tokens: {completion_tokens}")
    print(f"Cost: ${sum(agent.cost for agent in agents):.4f}")


if __name__ == "__main__":
    asyncio.run(main())
