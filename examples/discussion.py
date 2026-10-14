import asyncio
import random
from dataclasses import replace

from tyrant import GameRunner, GameState
from tyrant.models import Action, SpeakAction, SpeechEvent


class ChattyAgent:
    def __init__(self, uid: int):
        self.uid = uid

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        action = random.choice(valid_actions)
        if isinstance(action, SpeakAction):
            return replace(action, message=f"Player {self.uid} thinks this is fine.")
        return action


async def main():
    players = tuple(ChattyAgent(i) for i in range(7))
    runner = GameRunner(agents=players, discussion_enabled=True)
    end_state = await runner.run()

    for event in end_state.events:
        if isinstance(event, SpeechEvent):
            text = event.text if event.text is not None else "(stays silent)"
            print(f"[{event.context}] Player {event.uid}: {text}")
    print(f"Winner: {end_state.winner}")


if __name__ == "__main__":
    asyncio.run(main())
