# Private knowledge

What each player learned in secret is kept in `GameState.knowledge`, so it survives after transient fields such as `drawn_policies` are cleared. Each entry is a frozen subclass of [`Knowledge`](../reference/models.md#tyrant.models.Knowledge) with the `uid` of the player who learned it:

| Knowledge | Recorded when |
|---|---|
| [`PresidentDrawKnowledge`](../reference/models.md#tyrant.models.PresidentDrawKnowledge) | A president draws 3 policies after a passed election |
| [`ChancellorReceiveKnowledge`](../reference/models.md#tyrant.models.ChancellorReceiveKnowledge) | A chancellor receives 2 policies from the president |
| [`PeekKnowledge`](../reference/models.md#tyrant.models.PeekKnowledge) | A president peeks at the top 3 policies |
| [`InvestigationKnowledge`](../reference/models.md#tyrant.models.InvestigationKnowledge) | A president learns the party of an investigated player |

[`scrub_state`](../reference/models.md#tyrant.models.scrub_state) keeps only the viewer's own entries, so an agent never sees what another player learned.

## What else `scrub_state` hides

`scrub_state(state, viewer_uid)` returns a new state for one viewer. Besides other players' knowledge, it hides:

- other players' parties and roles, unless the viewer's role reveals them; an investigation reveals only the party,
- the contents of the draw and discard piles, though not their sizes,
- the policies in hand, unless the viewer is holding them,
- other players' votes while an election is still open,
- an investigation result the viewer didn't find,
- the state of the random generator that shuffles the deck.

Hidden values are replaced with the [`HIDDEN`](../reference/models.md#tyrant.models.HIDDEN) sentinel. Fascists see every fascist and Hitler. Hitler sees the fascists only in 5- and 6-player games. Liberals see nobody.
