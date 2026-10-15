"""An agent that plays through litellm; it needs the `llm` extra."""

try:
    import litellm
except ImportError as e:
    raise ImportError(
        'LLMAgent requires litellm. Install it with: pip install "tyrant[llm]"'
    ) from e

from frozendict import frozendict

from tyrant.exceptions import InvalidMoveError
from tyrant.llm.prompt import SYSTEM_PROMPT, build_prompt, parse_action, parse_notes
from tyrant.models.action import Action
from tyrant.models.game_state import GameState


class LLMAgent:
    """An agent that plays through any model litellm supports.

    Each turn it sends `SYSTEM_PROMPT` as the system message and `build_prompt` as the user message, then reads the reply with `parse_action` and `parse_notes`. When a reply is rejected, the next call adds that reply and the reason to the conversation.

    Attributes:
        uid: The player's unique ID.
        model: The litellm model string.
        completion_kwargs: Extra arguments for `litellm.acompletion`.
        notes: Private notes, shown back to the agent on each of its turns.
        prompt_tokens: Total prompt tokens used.
        completion_tokens: Total completion tokens used.
        cached_tokens: Total prompt tokens read from the provider's cache.
        cost: Total cost in US dollars, from `litellm.completion_cost`.
    """

    def __init__(
        self,
        uid: int,
        model: str,
        completion_kwargs: frozendict = frozendict(),
    ):
        """Creates the agent.

        Args:
            uid: The player's unique ID.
            model: A litellm model string, such as `anthropic/claude-haiku-5-5`.
            completion_kwargs: Extra arguments for `litellm.acompletion`, such as `temperature`.
        """
        self.uid = uid
        self.model = model
        self.completion_kwargs = completion_kwargs
        self.notes = ""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cached_tokens = 0
        self.cost = 0.0
        self._rejected: tuple[str, InvalidMoveError] | None = None

    async def choose_action(
        self, state: GameState, valid_actions: tuple[Action, ...]
    ) -> Action:
        """Asks the model for an action and updates the notes from its reply.

        Args:
            state: The game state, scrubbed for this agent.
            valid_actions: The actions this agent may take now.

        Returns:
            The offered action the model chose.

        Raises:
            InvalidMoveError: If the reply has no usable choice.
        """
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_prompt(state, self.uid, valid_actions, self.notes),
            },
        ]
        if self._rejected is not None:
            reply, error = self._rejected
            messages.append({"role": "assistant", "content": reply})
            messages.append(
                {
                    "role": "user",
                    "content": f"Your previous reply was rejected: {error}. "
                    "Choose again from Your Options above.",
                }
            )
        response = await litellm.acompletion(
            model=self.model, messages=messages, **self.completion_kwargs
        )
        self._record_usage(response)
        reply = response.choices[0].message.content or ""
        try:
            action = parse_action(reply, valid_actions)
        except InvalidMoveError as e:
            self._rejected = (reply, e)
            raise
        notes = parse_notes(reply)
        if notes is not None:
            self.notes = notes
        self._rejected = None
        return action

    def _record_usage(self, response) -> None:
        """Adds the response's token counts and cost to the running totals."""
        usage = response.usage
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        details = usage.prompt_tokens_details
        if details is not None and details.cached_tokens:
            self.cached_tokens += details.cached_tokens
        try:
            self.cost += litellm.completion_cost(completion_response=response)
        except Exception:
            pass
