from typing import Final

from tyrant.engine.renderer import render_text
from tyrant.models.action import Action, SpeakAction
from tyrant.models.discussion import MAX_SPEECH_LENGTH
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
- After a policy is enacted, the President and the Chancellor may each claim which policies they saw. After an investigation or a policy peek, the President may claim what they learned.
- Claims may be lies, and any claim may be declined.

## Discussion
- At set points, such as after a nomination or after claims, living players take turns to speak in seat order for a fixed number of rounds.
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


def render_actions(valid_actions: tuple[Action, ...]) -> str:
    """Returns a Markdown section listing the valid actions as numbered options."""
    lines = ["## Your Options"]
    for number, action in enumerate(valid_actions, start=1):
        note = " (include a `message`)" if isinstance(action, SpeakAction) else ""
        lines.append(f"{number}. {action.description}{note}")
    return "\n".join(lines)


def build_prompt(
    state: GameState, viewer_uid: int, valid_actions: tuple[Action, ...]
) -> str:
    """Returns the viewer's rendered state followed by their numbered options."""
    return render_text(state, viewer_uid) + "\n" + render_actions(valid_actions)
