# Contributing to Tyrant

Contributions are welcome. Report bugs and suggest features through [GitHub issues](https://github.com/7673502/tyrant/issues).

## Before you start

Open an issue before starting a large change or a new feature so the approach can be agreed first. Small fixes can go straight to a pull request.

## Setup

Tyrant needs Python 3.13 or newer and [uv](https://docs.astral.sh/uv/):

```sh
git clone https://github.com/7673502/tyrant
cd tyrant
uv sync --extra llm
```

## Checks

CI runs these on every pull request. Run them before pushing:

```sh
uv run ruff format .
uv run ruff check .
uv run python -m unittest
```

CI runs `ruff format --check`, so unformatted code fails.

## Code standards

- The core game logic stays separate from the LLM code. `litellm` is an optional extra, and the core depends only on `frozendict`.
- Models are frozen dataclasses (`@dataclass(frozen=True)`) that hold only immutable types: `tuple` instead of `list`, `frozendict` instead of `dict`.
- Functions return new instances and never mutate their inputs.
- Every model has a test named `test_<class_name>_immutability`, such as `test_game_state_immutability`, checking that it is frozen and every field is immutable. Every free function that takes a model or collection has a test named `test_<function_name>_immutability` checking that it returns a new instance and leaves its input unchanged. Functions that take only strings or other primitives don't need one.
- Every test has a one-sentence docstring that starts with a capital letter and ends with a period.
- Don't write inline comments explaining what code does.
- Put imports only at the top of the file.
- Keep changes focused. Don't reformat or refactor unrelated code.

## Docs

Public API docstrings use Google style and are rendered by mkdocstrings. When a change affects behaviour described in `docs/`, update it. Build the docs the way CI does:

```sh
uv sync --group docs --extra llm
uv run mkdocs build --strict
```

Use `uv run mkdocs serve` to preview them.

## Benchmarks

Measure changes to prompts or LLM play with the scripts in [`benchmarks/`](benchmarks/), as described in the [benchmarks guide](https://docs.secretarena.org/guides/benchmarks/). For example:

```sh
uv run python -m benchmarks.prompt_size --seeds 0 1 2 --players 10
```

## Pull requests

- Branch from `main`.
- Write titles in Conventional Commit style, as in the history: a prefix such as `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `build:` or `chore:`, then an imperative sentence starting with a capital letter, such as `fix: Default the metrics notes cap to MAX_NOTES_LENGTH`.
- Keep each pull request to one change.
- Add tests for new behaviour and bug fixes.

A maintainer has to approve CI runs for pull requests from outside contributors, so the first run may wait.

## AI use

You can use AI tools to write code and pull requests. Say so in the pull request description; a `Co-Authored-By` trailer counts.

Pull requests are reviewed by a maintainer who didn't write your code, so you need to understand and be able to explain every change, and to have run the checks. [`AGENTS.md`](AGENTS.md) holds these same rules for coding agents, so point your agent at it.

Write issues yourself, about a problem you have reproduced or a change you want. You can use AI to help word them, but AI-generated reports you haven't checked will be closed.

## License

Contributions are licensed under the [MIT License](LICENSE).
