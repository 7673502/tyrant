# Tyrant

Tyrant is a Python package that implements the social-deduction board-game [Secret Hitler](https://www.secrethitler.com/) primarily to allow LLMs to play against one another.

## TODO

- [ ] **Custom Exception Hierarchy:** Refactor generic `ValueError`s into custom exceptions with a `TyrantError` base class (e.g., `InvalidMoveError`, `SelfTargetingError`, `WrongPhaseError`) to allow better error parsing and easier reprompting for LLM agents.
- [ ] **MCP Server:** Implement an optional Model Context Protocol (MCP) server to allow external LLM agents and clients to interact programmatically with the game loop.
