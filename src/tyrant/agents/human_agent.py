import asyncio
from collections.abc import Callable
from dataclasses import replace

from tyrant.engine.renderer import render_text
from tyrant.models.action import Action, SpeakAction
from tyrant.models.game_state import GameState


class HumanAgent:
    """An agent played by a person at the terminal.

    Each turn it shows the player's view and the offered actions as numbered options, reads a number until a valid one is entered and, for a speech, reads the message. Input is read in a worker thread, so other agents keep running while it waits. Run it with `GameRunner(timeout=None)`: a timed-out prompt cannot be cancelled and would swallow the next line typed.

    Attributes:
        uid: The player's unique ID.
        input_fn: Shows a prompt and returns the line the player typed.
        output_fn: Shows text to the player.
    """

    def __init__(
        self,
        uid: int,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
    ):
        """Creates the agent.

        Args:
            uid: The player's unique ID.
            input_fn: Shows a prompt and returns the line the player typed.
            output_fn: Shows text to the player.
        """
        self.uid = uid
        self.input_fn = input_fn
        self.output_fn = output_fn

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        """Shows the player's view and options and returns the one they pick.

        Args:
            state: The game state, scrubbed for this agent.
            valid_actions: The actions this agent may take now.

        Returns:
            The offered action the player picked, with their message filled in for a speech.
        """
        self.output_fn(render_text(state, self.uid))
        self.output_fn("## Your Options")
        for number, action in enumerate(valid_actions, start=1):
            self.output_fn(f"{number}. {action.description}")

        count = len(valid_actions)
        while True:
            reply = (
                await asyncio.to_thread(self.input_fn, f"Choose 1-{count}: ")
            ).strip()
            if reply.isdigit() and 1 <= int(reply) <= count:
                break
            self.output_fn(f"Enter a number from 1 to {count}.")

        action = valid_actions[int(reply) - 1]
        if isinstance(action, SpeakAction):
            message = await asyncio.to_thread(self.input_fn, "Your message: ")
            return replace(action, message=message.strip())
        return action
