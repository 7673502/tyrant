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
    def __init__(
        self,
        uid: int,
        model: str,
        completion_kwargs: frozendict = frozendict(),
    ):
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
