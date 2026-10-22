# Benchmarks

The `benchmarks/` folder at the repository root holds measurement scripts. They print numbers rather than pass or fail, so run them to see what a change costs. Run them from the repository root.

## Prompt size

`benchmarks.prompt_size` plays random games with discussion on, where every player always speaks at [`MAX_SPEECH_LENGTH`](../reference/models.md#tyrant.models.MAX_SPEECH_LENGTH), and prints one row per seed:

```sh
uv run python -m benchmarks.prompt_size --seeds 0 1 2 --players 10
```

It shows the largest and mean prompt per call and the total input and output tokens per game, estimated at 4 characters per token, with a prompt being [`SYSTEM_PROMPT`](../reference/llm.md#tyrant.llm.SYSTEM_PROMPT) plus [`build_prompt`](../reference/llm.md#tyrant.llm.build_prompt). The shared prefix is the average fraction of each player's prompt that starts identically to their previous one, which a provider's prompt cache can reuse. `measure(seed, player_count)` returns the same numbers for one game. A test runs it against loose thresholds that only catch bugs such as a duplicated timeline.

## Replay metrics

`benchmarks.replay_metrics` reads one or more [replay files](replays.md) and prints a table of play quality metrics with one column per file, such as how often elections are unanimous, how often players lie in claims, and how many speeches repeat earlier ones:

```sh
uv run python -m benchmarks.replay_metrics game-01.json.gz game-02.json.gz
```

## ISMCTS win rate

`benchmarks.ismcts_win_rate` plays one hero in seat 0 against four [`BiasedRandomAgent`](../reference/agents.md#tyrant.agents.BiasedRandomAgent)s in 5-player games, half with the hero liberal and half fascist, and prints its win rate in each role and its seconds per decision:

```sh
uv run python -m benchmarks.ismcts_win_rate --hero ismcts --iterations 300 --games 300
```

The hero is `ismcts`, an [`ISMCTSAgent`](../reference/agents.md#tyrant.agents.ISMCTSAgent); `uniform`, one that weighs every role deal equally; `true-roles`, one that is told the true roles; or `biased`, a `BiasedRandomAgent` as the baseline. Compare `ismcts` with `uniform` to see what the belief model adds, and with `true-roles` to see how much better beliefs could add. Games run in parallel across `--workers` processes, every core by default. With 300 games per role a win rate has a standard error of about 2.7 points, so smaller differences are noise.
