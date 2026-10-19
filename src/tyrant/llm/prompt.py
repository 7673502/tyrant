import json
import re
from dataclasses import replace
from typing import Final

from frozendict import frozendict

from tyrant.engine.renderer import render_text
from tyrant.exceptions import InvalidMoveError
from tyrant.models.action import Action, SpeakAction
from tyrant.models.discussion import MAX_SPEECH_LENGTH
from tyrant.models.enums import Role
from tyrant.models.game_state import GameState

RULES: Final[str] = """# Secret Hitler Rules

## Teams and Roles
- Every player is secretly a Liberal or a Fascist. One Fascist is Hitler.
- Fascists know every other Fascist and who Hitler is. Hitler knows the Fascists only in games of 5 or 6 players. Liberals know nobody.
- The teammates you know are listed with their roles in your view. Everyone else's role is hidden.

## Winning
- Liberals win when 5 Liberal policies are enacted (`liberal_policies`) or when Hitler is executed (`hitler_executed`).
- Fascists win when 6 Fascist policies are enacted (`fascist_policies`) or when Hitler is elected Chancellor after 3 or more Fascist policies have been enacted (`hitler_elected`).

## Policy Deck
- The deck holds 6 Liberal and 11 Fascist policies. When fewer than 3 remain, the discard pile is shuffled back in.

## Nomination
- The presidency passes to the next living player in seat order each round.
- The President nominates a living Chancellor other than themself.
- The last elected Chancellor can never be nominated. While more than 5 players are alive, the last elected President can't be nominated either.

## Voting
- Every living player votes ja or nein at the same time. The government is elected only if ja votes outnumber nein votes.
- Each failed election advances the election tracker. When it reaches 3, the top policy of the deck is enacted automatically, its presidential power is ignored, the tracker resets, and term limits are cleared.
- If Hitler is elected Chancellor after 3 or more Fascist policies have been enacted, the Fascists win immediately.

## Legislative Session
- The President draws 3 policies, secretly discards 1, and passes 2 to the Chancellor, who enacts 1. Nobody else sees these policies.
- After 5 Fascist policies, the Chancellor may propose a veto. If the President agrees, both policies are discarded and the election tracker advances. If the President refuses, the Chancellor must enact one.

## Presidential Powers
Some Fascist policies grant the President a power, which they must use before the next round. The fascist track on the board lists, in order, the power each Fascist policy grants in this game.
- Investigate loyalty: the President learns another player's party, not their role. Nobody can be investigated twice.
- Special election: the President picks the next President. Afterwards, the presidency continues from the player after the President who called it.
- Policy peek: the President sees the top 3 policies of the deck.
- Execution: the President kills a player, who no longer votes, speaks, or holds office. If that player is Hitler, the Liberals win.

## Claims
- After a policy is enacted, the President and the Chancellor may each claim which policies they saw. The President's claim also names the policy they discarded, so it implies the 2 policies they passed. After an investigation or a policy peek, the President may claim what they learned.
- Claims may be lies, and any claim may be declined.

## Discussion
- At set points, such as after a nomination or after claims, living players take turns to speak in seat order for a fixed number of rounds. The discussion ends early once every living player passes in a row.
- Each turn, a player either says something to the table or stays silent. Everyone hears every speech.

## Hidden Information
- `unknown` means the value is hidden from you.
"""

RESPONSE_FORMAT: Final[str] = f"""# Response Format
Think through your decision in plain text first if you want. Then end your reply with exactly one JSON object:

{{"action": N, "message": "..."}}

- `action` is the number of the option you choose from Your Options.
- `message` is only required when you choose the option to say something to the table. It is what you say, at most {MAX_SPEECH_LENGTH} characters. Leave it out otherwise.
- Only the last JSON object in your reply is read.
"""

SYSTEM_PROMPT: Final[str] = RULES + "\n" + RESPONSE_FORMAT
"""The rules and the reply format, the same for every game and every player."""


def system_prompt(persona: str = "") -> str:
    """Returns `SYSTEM_PROMPT`, followed by a `## Your Personality` section when a persona is given.

    Args:
        persona: A playing style for the player, or empty for none.

    Returns:
        The system message, which always starts with `SYSTEM_PROMPT` so providers can reuse their cache.
    """
    if not persona:
        return SYSTEM_PROMPT
    return f"{SYSTEM_PROMPT}\n## Your Personality\n{persona}\n"


GOALS: Final = frozendict(
    {
        Role.LIBERAL: "You are a Liberal. You win when 5 Liberal policies are enacted or when Hitler is executed. You lose when 6 Fascist policies are enacted or when Hitler is elected Chancellor once 3 or more Fascist policies are enacted.",
        Role.FASCIST: "You are a Fascist. You win when Hitler is elected Chancellor once 3 or more Fascist policies are enacted, or when 6 Fascist policies are enacted. You lose when 5 Liberal policies are enacted or when Hitler is executed.",
        Role.HITLER: "You are Hitler. You win if you are elected Chancellor once 3 or more Fascist policies are enacted, or when 6 Fascist policies are enacted. You lose if you are executed or when 5 Liberal policies are enacted.",
    }
)
"""One line per role stating when that player wins and loses."""


def render_goal(role: Role) -> str:
    """Returns a Markdown section stating when a player with the given role wins and loses.

    Args:
        role: The viewer's role.

    Returns:
        A `## Your Goal` section.
    """
    return "## Your Goal\n" + GOALS[role]


def render_actions(valid_actions: tuple[Action, ...]) -> str:
    """Returns a Markdown section listing the valid actions as numbered options.

    Args:
        valid_actions: The actions the agent may take now.

    Returns:
        A `## Your Options` section, numbered from 1.
    """
    lines = ["## Your Options"]
    for number, action in enumerate(valid_actions, start=1):
        note = " (include a `message`)" if isinstance(action, SpeakAction) else ""
        lines.append(f"{number}. {action.description}{note}")
    return "\n".join(lines)


def build_prompt(
    state: GameState,
    viewer_uid: int,
    valid_actions: tuple[Action, ...],
) -> str:
    """Returns the viewer's rendered state, their goal, then their numbered options.

    Args:
        state: The game state; it is scrubbed for the viewer first.
        viewer_uid: UID of the player being prompted.
        valid_actions: The actions the player may take now.

    Returns:
        The user message for this turn.
    """
    role = next(p.role for p in state.players if p.uid == viewer_uid)
    return "\n".join(
        [
            render_text(state, viewer_uid),
            render_goal(role),
            render_actions(valid_actions),
        ]
    )


_XML_PARAMETER: Final = re.compile(
    r'<parameter name="(action|message)">(.*?)</parameter>', re.DOTALL
)


def _xml_choice(response: str) -> dict | None:
    """Returns the `action` and `message` parameters of a tool-call style reply, or None if it has no action."""
    choice = dict(_XML_PARAMETER.findall(response))
    if "action" not in choice:
        return None
    action = choice["action"].strip()
    if action.isascii() and action.isdigit():
        choice["action"] = int(action)
    return choice


def _last_choice(response: str) -> dict:
    """Returns the last JSON object in the reply that has an `action` key, falling back to tool-call style parameters."""
    decoder = json.JSONDecoder()
    start = response.rfind("{")
    while start != -1:
        try:
            value, _ = decoder.raw_decode(response, start)
        except json.JSONDecodeError:
            value = None
        if isinstance(value, dict) and "action" in value:
            return value
        start = response.rfind("{", 0, start)
    choice = _xml_choice(response)
    if choice is not None:
        return choice
    raise InvalidMoveError("Reply has no JSON object with an action")


def parse_action(response: str, valid_actions: tuple[Action, ...]) -> Action:
    """Returns the offered action chosen by the last JSON object in an LLM reply.

    Args:
        response: The model's reply.
        valid_actions: The actions offered in the prompt, in the same order.

    Returns:
        The chosen action, with `message` filled in for a `SpeakAction`.

    Raises:
        InvalidMoveError: If the reply has no usable choice, the number is not a valid option, or a speech has no message.
    """
    choice = _last_choice(response)
    number = choice["action"]
    if type(number) is not int:
        raise InvalidMoveError(f"Action must be an integer, got {number!r}")
    if not 1 <= number <= len(valid_actions):
        raise InvalidMoveError(
            f"Action must be between 1 and {len(valid_actions)}, got {number}"
        )
    action = valid_actions[number - 1]
    if not isinstance(action, SpeakAction):
        return action
    message = choice.get("message")
    if not isinstance(message, str) or not message.strip():
        raise InvalidMoveError("Speaking requires a non-empty message")
    return replace(action, message=message)
