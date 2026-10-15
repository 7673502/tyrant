# Installation

Tyrant needs Python 3.13 or newer. Its only required dependency is [`frozendict`](https://pypi.org/project/frozendict/).

!!! note
    Tyrant is not on PyPI yet. Install it from GitHub.

## Core package

=== "pip"

    ```sh
    pip install "tyrant @ git+https://github.com/7673502/tyrant"
    ```

=== "uv"

    ```sh
    uv add "tyrant @ git+https://github.com/7673502/tyrant"
    ```

The core package has everything needed to run games with your own agents, the bundled agents, the renderer and replays. It makes no network calls.

## LLM support

[`LLMAgent`](../reference/llm.md#tyrant.llm.agent.LLMAgent) plays through [litellm](https://docs.litellm.ai/). It is an optional extra, so the core package stays light:

=== "pip"

    ```sh
    pip install "tyrant[llm] @ git+https://github.com/7673502/tyrant"
    ```

=== "uv"

    ```sh
    uv add "tyrant[llm] @ git+https://github.com/7673502/tyrant"
    ```

Without the extra, importing `tyrant.llm.agent` raises an `ImportError` that says how to install it. The rest of [`tyrant.llm`](../reference/llm.md), which builds prompts and parses replies, works without it.

## From a clone

To work on Tyrant itself or run the examples:

```sh
git clone https://github.com/7673502/tyrant
cd tyrant
uv sync --extra llm
uv run python examples/basic_usage.py
```

Run the tests with `uv run python -m unittest`.

## Check the install

```python
import tyrant

print(tyrant.GameRunner)
```

Next, [play your first game](../tutorials/first-game.md).
