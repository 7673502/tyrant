# GameState Implementation Plan

## Current Codebase Inventory

The project has these existing building blocks, all frozen dataclasses with pure-functional free functions:

| Model | Fields | Free Functions |
|-------|--------|----------------|
| [Player](src/tyrant/models/player.py) | `uid`, `party`, `role`, `is_alive` | — |
| [Board](src/tyrant/models/board.py) | `player_count`, `liberal_played`, `fascist_played` | `play_tile` |
| [Deck](src/tyrant/models/deck.py) | `draw_pile`, `discard_pile` | `create_deck`, `shuffle_deck`, `draw_policies`, `top_deck`, `discard_policies` |
| [BallotBox](src/tyrant/models/ballot_box.py) | `votes` (frozendict) | `submit_vote` |
| [ElectionTracker](src/tyrant/models/election_tracker.py) | `failed_elections` | `increment_election_tracker` |
| [Enums](src/tyrant/models/enums.py) | `Party`, `Role`, `PolicyTile`, `PresidentialPower`, `Vote`, `GamePhase` | — |

Design conventions observed:
- All models are `@dataclass(frozen=True)` — immutable value objects
- State transitions are free functions returning new instances (never mutating)
- `frozendict` used for immutable maps (e.g., `BallotBox.votes`)
- `Random` is injected for reproducibility (see `Deck`)
- Tests verify immutability, correctness, and reproducibility

---

## What GameState Needs to Represent

GameState is the top-level container that composes all sub-models into a single immutable snapshot of a Secret Hitler game. It must track:

1. **Players** — ordered list, identities, alive/dead status (serves as rotation order)
2. **Board** — liberal/fascist tiles played (already exists)
3. **Deck** — draw/discard piles (already exists)
4. **Election Tracker** — failed election count (already exists)
5. **Turn state** — current president, nominated chancellor, term-limited players
6. **Phase** — what action is expected next (`GamePhase` enum already exists)
7. **Ballot Box** — votes for current election (already exists)
8. **Drawn policies** — the 3 (or 2) cards currently in play during legislative session
9. **Winner** — game outcome, if decided
10. **Previous government** — for term limits
11. **Investigations** — tracking which president investigated which player (for knowledge sharing and enforcing once-per-game limits)

---

## Proposed GameState Dataclass

```python
@dataclass(frozen=True)
class GameState:
    players: tuple[Player, ...]
    board: Board
    deck: Deck
    election_tracker: ElectionTracker
    phase: GamePhase
    president_index: int                    # index into players tuple
    nominated_chancellor: int | None        # uid or None
    ballot_box: BallotBox
    drawn_policies: tuple[PolicyTile, ...]  # 3 tiles (president), 2 tiles (chancellor), or ()
    previous_president: int | None          # uid, for term limits
    previous_chancellor: int | None         # uid, for term limits
    winner: Party | None
    special_election_president: int | None  # uid, if special election is active
    veto_denied_this_term: bool = False
    investigations: frozendict[int, int] = frozendict()  # investigated_uid -> investigator_uid
```

> [!NOTE]
> This is a data-only container. All game logic lives in free functions that accept and return `GameState`.

---

## Proposed Free Functions (Step-by-Step Plan)

### Step 1: `create_game(uids: tuple[int, ...], rng: Random) -> GameState`

Initializes a new game:
- Create `len(uids)` `Player` instances with assigned `Party`/`Role` per Secret Hitler rules.
- Shuffle the created `Player` instances (based on `rng`) to randomize the rotation order.
- Create the `Board`, `Deck`, `ElectionTracker`, empty `BallotBox`.
- Set `phase = GamePhase.NOMINATION`.
- Set `president_index = 0`.

**Verify:** Correct role distribution (1 Hitler + F fascists + L liberals), shuffled deck, phase is `NOMINATION`.

### Step 1.5: `_advance_to_nomination(state: GameState) -> GameState` (Internal Helper)

Centralized helper for transitioning to a new nomination phase.
- Advances `president_index` (handling special elections properly and ensuring that the president in rotation is alive).
- Resets `ballot_box` to empty.
- Resets `veto_denied_this_term = False`.
- Clears `nominated_chancellor`.
- Sets `phase = GamePhase.NOMINATION`.
All paths that end a term or fail an election must call this function.

**Verify:** Proper index rotation, states reset correctly, special election state cleared after use.

### Step 2: `nominate_chancellor(state: GameState, chancellor_uid: int) -> GameState`

President nominates a chancellor:
- Validate: phase is `NOMINATION`, chancellor is alive, not the current president.
- Validate Term Limits:
  - Calculate active player count: `alive_count = len([p for p in state.players if p.is_alive])`.
  - If `alive_count > 6`: target cannot be `previous_president` or `previous_chancellor`.
  - If `alive_count <= 6`: target cannot be `previous_chancellor`.
- Return new state with `nominated_chancellor` set, `phase = GamePhase.VOTING`.

**Verify:** Invalid nominations rejected, dynamic term limit sizes correctly evaluated, phase transitions correctly.

### Step 3: `cast_vote(state: GameState, uid: int, vote: Vote) -> GameState`

A player casts their vote:
- Validate: phase is `VOTING`, player is alive, hasn't voted yet (or allow change).
- Delegate to `submit_vote`.
- If all alive players have voted, trigger election resolution internally.

**Verify:** Votes accumulate correctly, phase doesn't change until all votes are in.

### Step 4: Election resolution (internal, called from `cast_vote` when complete)

When all votes are in:
- **Ja majority:**
  - Check Hitler-zone win condition (Hitler elected chancellor → fascist win).
  - Set `phase = GamePhase.PRESIDENT_DISCARD`, draw 3 policies, reset election tracker.
  - Update `previous_president`/`previous_chancellor`.
- **Nein majority:**
  - Increment election tracker.
  - If tracker triggers top-deck: top-deck a policy, play it (no presidential power), reshuffle if needed. Reset previous government.
  - Call `_advance_to_nomination(state)`.

**Verify:** Win condition on Hitler chancellor, top-deck on 3 failures, proper reset calls.

### Step 5: `president_discard(state: GameState, discard_index: int) -> GameState`

President discards one of three drawn policies:
- Validate: phase is `PRESIDENT_DISCARD`, index is valid.
- Move discarded tile to discard pile, keep remaining 2 as `drawn_policies`.
- Set `phase = GamePhase.CHANCELLOR_ENACT`.

**Verify:** Exactly 2 policies remain, discard pile grows by 1.

### Step 6: `chancellor_discard(state: GameState, discard_index: int) -> GameState`

Chancellor discards one of two remaining policies (or initiates veto):
- Validate: phase is `CHANCELLOR_ENACT`, index is valid.
- Play the remaining tile on the board via `play_tile`.
- Discard the other tile.
- Check board win conditions.
- If liberal tile → call `_advance_to_nomination(state)`.
- If fascist tile and presidential power is not `NONE` → `phase = GamePhase.PRESIDENTIAL_POWER`.
- If fascist tile and power is `NONE` → call `_advance_to_nomination(state)`.

**Verify:** Policy played correctly, presidential power triggers, win conditions.

### Step 7: `chancellor_veto(state: GameState) -> GameState`

Chancellor proposes a veto (only when veto power unlocked):
- Validate: phase is `CHANCELLOR_ENACT`, veto power is unlocked, `veto_denied_this_term` is `False`.
- Set `phase = GamePhase.PRESIDENT_VETO_RESPONSE`.

**Verify:** Only available when 5+ fascist tiles played and veto hasn't been denied this term.

### Step 8: `president_veto_response(state: GameState, approve: bool) -> GameState`

President approves or denies the veto:
- **Approve:** Discard both remaining policies, increment election tracker (check top-deck logic). Call `_advance_to_nomination(state)`.
- **Deny:** Set `veto_denied_this_term = True`, `phase = GamePhase.CHANCELLOR_ENACT` (chancellor must now choose).

**Verify:** Approved veto increments tracker, denied veto locks out further vetoes and returns to chancellor.

### Step 9: Presidential power functions

One function per power, all requiring `phase == GamePhase.PRESIDENTIAL_POWER`:

- `investigate_loyalty(state, target_uid) -> GameState` — Update `investigations` map. Call `_advance_to_nomination(state)`.
- `call_special_election(state, target_uid) -> GameState` — Set `special_election_president`. Call `_advance_to_nomination(state)` (which respects the special election).
- `policy_peek(state) -> GameState` — Caller reads `state.deck.peek`. Call `_advance_to_nomination(state)`.
- `execute_player(state, target_uid) -> GameState` — Mark player dead. If Hitler is killed → liberal win. Call `_advance_to_nomination(state)`.

**Verify:** Each power transitions correctly, execution win condition, special election tracking.

### Step 10: `scrub_state(state: GameState, viewer_uid: int) -> GameState`

Produces a localized view of the GameState with hidden information removed based on Secret Hitler rules.
- **Roles and Parties:**
  - If viewer is Liberal: All other players' roles/parties are hidden (`None`).
  - If viewer is Hitler (in 7-10 player games): All other players' roles/parties are hidden (`None`).
  - If viewer is Fascist (or Hitler in 5-6 player games): Fascists see each other and Hitler. Non-fascists are hidden (`None`).
  - **Investigations:** If the viewer has investigated a player (i.e. `state.investigations.get(player_uid) == viewer_uid`), that player's party is visible to the viewer (role remains hidden).
- **Deck:** The order of `draw_pile` and `discard_pile` is hidden (perhaps replaced with empty tuples or masked values so length is known but contents are not, pending exact implementation).
- **Drawn Policies:** Hidden (`()`) unless the viewer is the active President during `PRESIDENT_DISCARD` or the active Chancellor during `CHANCELLOR_ENACT`.
- **Policy Peek:** If the viewer just used Policy Peek, the top 3 cards can be temporarily revealed in a side channel, or `drawn_policies` is used to expose them.

**Verify:** Scrubbing correctly respects team-knowledge rules, investigations, player counts, and current active phases.

---

## Implementation Order

```
1. GameState dataclass + _advance_to_nomination + create_game  → verify: correct setup, helpers
2. nominate_chancellor                         → verify: validation, dynamic term limits
3. cast_vote + election resolution             → verify: ja/nein paths, Hitler win, top-deck
4. president_discard                           → verify: 3→2 policies, discard pile
5. chancellor_discard                          → verify: policy played, power triggers, wins
6. chancellor_veto + president_veto_response   → verify: veto flow, tracker increment, denied flag
7. Presidential power functions                → verify: each power, execution win
8. scrub_state                                 → verify: information hiding based on rules
```

Each step gets its own test class. Tests follow the existing patterns: immutability checks, correctness, edge cases.

