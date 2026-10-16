"""An agent that plays through litellm; it needs the `llm` extra."""

try:
    import litellm
except ImportError as e:
    raise ImportError(
        'LLMAgent requires litellm. Install it with: pip install "tyrant[llm]"'
    ) from e

from collections.abc import Callable

from frozendict import frozendict

from tyrant.exceptions import AgentError, InvalidMoveError
from tyrant.llm.prompt import build_prompt, parse_action, parse_notes, system_prompt
from tyrant.models.action import Action
from tyrant.models.game_state import GameState

_NO_USAGE = frozendict(prompt_tokens=0, completion_tokens=0, cached_tokens=0, cost=0.0)


class LLMAgent:
    """An agent that plays through any model litellm supports.

    Each turn it sends `SYSTEM_PROMPT`, followed by the persona if one is set, as the system message and `build_prompt` as the user message, then reads the reply with `parse_action` and `parse_notes`. When a reply is rejected, the next call for the same state adds that reply and the reason to the conversation. Provider and network errors are raised as `AgentError`. When `on_exchange` is set, it is called once for each provider call with the messages sent and what came back; an exception it raises propagates out of `choose_action`.

    Attributes:
        uid: The player's unique ID.
        model: The litellm model string.
        completion_kwargs: Extra arguments for `litellm.acompletion`.
        persona: A playing style added to the system message under `## Your Personality`, or empty for none.
        notes: Private notes, shown back to the agent on each of its turns.
        prompt_tokens: Total prompt tokens used.
        completion_tokens: Total completion tokens used.
        cached_tokens: Total prompt tokens read from the provider's cache.
        cost: Total cost in US dollars, from `litellm.completion_cost`.
        profile: The model and persona, which replays show for the player.
        on_exchange: Called with each provider call's messages, reply, usage and error, or `None`.
    """

    def __init__(
        self,
        uid: int,
        model: str,
        completion_kwargs: frozendict = frozendict(),
        persona: str = "",
        on_exchange: Callable[[dict], None] | None = None,
    ):
        """Creates the agent.

        Args:
            uid: The player's unique ID.
            model: A litellm model string, such as `anthropic/claude-haiku-5-5`.
            completion_kwargs: Extra arguments for `litellm.acompletion`, such as `temperature`.
            persona: A playing style, such as "cautious, rarely accuses without a contradiction", or empty for none.
            on_exchange: Called once for each provider call with a plain JSON dict holding `uid`, the `messages` sent, the `reply` (`None` when the call failed), that call's `prompt_tokens`, `completion_tokens`, `cached_tokens` and `cost`, and the `error` that rejected the call, or `None`.
        """
        self.uid = uid
        self.model = model
        self.completion_kwargs = completion_kwargs
        self.persona = persona
        self.notes = ""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cached_tokens = 0
        self.cost = 0.0
        self.on_exchange = on_exchange
        self._rejected: tuple[GameState, str, InvalidMoveError] | None = None

    @property
    def profile(self) -> frozendict[str, str]:
        """The model and persona, which replays show for the player."""
        return frozendict(model=self.model, persona=self.persona)

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
            InvalidMoveError: If the reply has no usable choice; its `reply` holds the raw reply.
            AgentError: If the provider call fails.
        """
        messages = [
            {"role": "system", "content": system_prompt(self.persona)},
            {
                "role": "user",
                "content": build_prompt(state, self.uid, valid_actions, self.notes),
            },
        ]
        if self._rejected is not None and self._rejected[0] == state:
            _, reply, error = self._rejected
            messages.append({"role": "assistant", "content": reply})
            messages.append(
                {
                    "role": "user",
                    "content": f"Your previous reply was rejected: {error}. "
                    "Choose again from Your Options above. Reply with plain text, "
                    'then end with one JSON object like {"action": 2, "notes": "…"}. '
                    "Do not use tool-call or XML syntax.",
                }
            )
        try:
            response = await litellm.acompletion(
                model=self.model, messages=messages, **self.completion_kwargs
            )
        except Exception as e:
            error = AgentError(f"Provider call failed: {e!r}")
            self._emit(messages, None, _NO_USAGE, error)
            raise error from e
        usage = self._record_usage(response)
        reply = response.choices[0].message.content or ""
        try:
            action = parse_action(reply, valid_actions)
        except InvalidMoveError as e:
            error = InvalidMoveError(str(e), reply=reply)
            self._rejected = (state, reply, error)
            self._emit(messages, reply, usage, error)
            raise error from e
        self._emit(messages, reply, usage, None)
        notes = parse_notes(reply)
        if notes is not None:
            self.notes = notes
        self._rejected = None
        return action

    def _record_usage(self, response) -> dict:
        """Adds the response's token counts and cost to the running totals and returns them."""
        usage = response.usage
        details = usage.prompt_tokens_details
        cached = details.cached_tokens if details is not None else 0
        try:
            cost = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = 0.0
        call = {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "cached_tokens": cached or 0,
            "cost": cost,
        }
        self.prompt_tokens += call["prompt_tokens"]
        self.completion_tokens += call["completion_tokens"]
        self.cached_tokens += call["cached_tokens"]
        self.cost += call["cost"]
        return call

    def _emit(
        self,
        messages: list[dict],
        reply: str | None,
        usage: dict,
        error: Exception | None,
    ) -> None:
        """Passes one provider call to `on_exchange`, if it is set."""
        if self.on_exchange is None:
            return
        self.on_exchange(
            {
                "uid": self.uid,
                "messages": [dict(m) for m in messages],
                "reply": reply,
                **usage,
                "error": None if error is None else repr(error),
            }
        )
