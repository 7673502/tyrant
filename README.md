# Tyrant

[![PyPI](https://img.shields.io/pypi/v/tyrant)](https://pypi.org/project/tyrant/)
[![Python](https://img.shields.io/pypi/pyversions/tyrant)](https://pypi.org/project/tyrant/)
[![License](https://img.shields.io/pypi/l/tyrant)](https://github.com/7673502/tyrant/blob/main/LICENSE)
[![Tests](https://github.com/7673502/tyrant/actions/workflows/tests.yml/badge.svg)](https://github.com/7673502/tyrant/actions/workflows/tests.yml)
[![Docs](https://github.com/7673502/tyrant/actions/workflows/docs.yml/badge.svg)](https://docs.secretarena.org)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Tyrant is a Python package that implements the social-deduction board-game [Secret Hitler](https://www.secrethitler.com/) primarily to allow LLMs to play against one another. Game state is immutable, agents only ever see what their seat is allowed to know, and every game can be saved as a JSON replay or streamed live.

**Documentation: https://docs.secretarena.org**

## Install

Tyrant needs Python 3.13 or newer:

```sh
pip install tyrant
```

LLM support is an optional extra that adds [litellm](https://docs.litellm.ai/):

```sh
pip install "tyrant[llm]"
```

## Quick start

```python
import asyncio

from tyrant import GameRunner, RandomAgent


async def main():
    agents = [RandomAgent(uid) for uid in range(5)]
    final_state = await GameRunner(agents, seed=7).run()
    print(final_state.winner)


asyncio.run(main())
```

To play language models against each other, see [Running an LLM game](https://docs.secretarena.org/tutorials/llm-game/). More examples are in [`examples/`](examples/).

## License

[MIT](LICENSE)
