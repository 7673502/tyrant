# Tyrant

Tyrant is a Python package that implements the social-deduction board-game [Secret Hitler](https://www.secrethitler.com/) primarily to allow LLMs to play against one another. Game state is immutable, agents only ever see what their seat is allowed to know, and every game can be saved as a JSON replay.

**Documentation: https://docs.secretarena.org**

## Install

Tyrant needs Python 3.13 or newer. It is not on PyPI yet, so install it from GitHub:

```sh
pip install "tyrant @ git+https://github.com/7673502/tyrant"
```

LLM support is an optional extra that adds [litellm](https://docs.litellm.ai/):

```sh
pip install "tyrant[llm] @ git+https://github.com/7673502/tyrant"
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
