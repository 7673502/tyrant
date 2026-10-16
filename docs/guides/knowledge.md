# Private knowledge

What each player learned in secret is kept in `GameState.knowledge`, so it survives after transient fields such as `drawn_policies` are cleared. Each entry is a frozen subclass of [`Knowledge`](../reference/models.md#tyrant.models.Knowledge) with the `uid` of the player who learned it:

| Knowledge | Recorded when |
|---|---|
| [`PresidentDrawKnowledge`](../reference/models.md#tyrant.models.PresidentDrawKnowledge) | A president draws 3 policies after a passed election |
| [`PresidentDiscardKnowledge`](../reference/models.md#tyrant.models.PresidentDiscardKnowledge) | The president discards 1 policy and passes the other 2 to the chancellor |
| [`ChancellorReceiveKnowledge`](../reference/models.md#tyrant.models.ChancellorReceiveKnowledge) | A chancellor receives 2 policies from the president |
| [`PeekKnowledge`](../reference/models.md#tyrant.models.PeekKnowledge) | A president peeks at the top 3 policies |
| [`InvestigationKnowledge`](../reference/models.md#tyrant.models.InvestigationKnowledge) | A president learns the party of an investigated player |

[`render_text`](../reference/engine.md#tyrant.engine.render_text) shows a draw and the discard that follows it as one line, such as "In Gov 3 (P1→P2) you drew fascist, fascist, liberal, discarded fascist, passed fascist, liberal." The label names the [government](rendering.md#governments) the session belonged to. Nothing extra is recorded for a veto. The vetoed policies are the two the president passed, and the public `veto` event in the timeline shows that the veto was approved. Drawn, passed and received policies are always listed fascist first; a peek keeps its top-to-bottom order.

## Claim options

[`get_legal_actions`](../reference/engine.md#tyrant.engine.get_legal_actions) reads the claimant's knowledge to put the truthful claim first, labelled "Tell the truth", for example "Tell the truth: you drew fascist, fascist, liberal and discarded fascist, so you passed fascist, liberal." Every other claim is labelled as a lie, such as "Lie: claim you drew fascist, liberal, liberal and discarded fascist, so you passed liberal, liberal.", and the decline comes last. A president's truth is their latest discard, a chancellor's is the latest policies they received, a peek's is the policies in hand and an investigation's is the party found. The claim options list policies in the same order as the knowledge lines, so an agent can match its hand to an option word for word.

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
