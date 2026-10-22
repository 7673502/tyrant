"""Measures how often one hero agent wins against four BiasedRandomAgents.

Each game has 5 players with fixed roles and the hero in seat 0. Half the
games make the hero liberal and half fascist, alternating between a fascist
and Hitler, and game n of each role uses seed n. The hero is an ISMCTSAgent,
an ISMCTSAgent that weighs every role deal equally, an ISMCTSAgent that is
told the true roles, or a BiasedRandomAgent as the baseline. The uniform hero
shows what the belief model adds and the true-roles hero shows how much
better beliefs could add.

Seconds per decision time each search, including the belief model. Games run
in parallel worker processes, so timings from many workers on one machine
run slower than a lone game would.
"""

import argparse
import asyncio
import os
import time
from multiprocessing import Pool

from frozendict import frozendict

from tyrant.agents.biased_random_agent import BiasedRandomAgent
from tyrant.agents.ismcts.agent import ISMCTSAgent
from tyrant.agents.ismcts.beliefs import role_assignments, role_weights
from tyrant.agents.ismcts.search import search
from tyrant.engine.game_runner import GameRunner
from tyrant.models.action import Action
from tyrant.models.agent import Agent
from tyrant.models.enums import Party, Role
from tyrant.models.game_state import GameState

HEROES = ("ismcts", "uniform", "true-roles", "biased")
ROLES = frozendict(
    {
        Role.LIBERAL: (
            Role.LIBERAL,
            Role.LIBERAL,
            Role.LIBERAL,
            Role.FASCIST,
            Role.HITLER,
        ),
        Role.FASCIST: (
            Role.FASCIST,
            Role.LIBERAL,
            Role.LIBERAL,
            Role.LIBERAL,
            Role.HITLER,
        ),
        Role.HITLER: (
            Role.HITLER,
            Role.LIBERAL,
            Role.LIBERAL,
            Role.LIBERAL,
            Role.FASCIST,
        ),
    }
)
COLUMNS = (
    "Hero",
    "Iterations",
    "Games per role",
    "Liberal win",
    "Fascist win",
    "Mean s/decision",
    "Max s/decision",
)


class TimedAgent(ISMCTSAgent):
    """An ISMCTSAgent that records how long each search takes, and can weigh deals equally or know the true roles."""

    def __init__(
        self,
        uid: int,
        iterations: int,
        seed: int,
        roles: frozendict[int, Role] | None,
        uniform: bool,
    ):
        super().__init__(uid, iterations=iterations, seed=seed)
        self.roles = roles
        self.uniform = uniform
        self.seconds: list[float] = []

    def _search(self, state: GameState) -> Action:
        start = time.perf_counter()
        if self.roles is not None:
            assignments, weights = (self.roles,), (1.0,)
        else:
            assignments = role_assignments(state, self.uid)
            weights = (
                (1.0,) * len(assignments)
                if self.uniform
                else role_weights(state, assignments)
            )
        action = search(
            state,
            self.uid,
            assignments,
            weights,
            self.iterations,
            self.exploration,
            self.rng,
        )
        self.seconds.append(time.perf_counter() - start)
        return action


def measure(hero: str, role: Role, seed: int, iterations: int) -> frozendict:
    """Plays one game and returns whether the hero's party won.

    Args:
        hero: One of `HEROES`.
        role: The hero's role.
        seed: The game seed, also used to seed the hero's search.
        iterations: Search iterations per decision for an ISMCTS hero.

    Returns:
        `won`, whether the hero's party won, and `seconds`, the time of each
        of the hero's searches.
    """
    roles = frozendict(enumerate(ROLES[role]))
    agent: Agent
    if hero == "biased":
        agent = BiasedRandomAgent(0)
    else:
        agent = TimedAgent(
            0,
            iterations,
            seed,
            roles if hero == "true-roles" else None,
            hero == "uniform",
        )
    agents = [agent] + [BiasedRandomAgent(uid) for uid in range(1, 5)]
    state = asyncio.run(GameRunner(agents, roles=roles, seed=seed).run())
    party = Party.LIBERAL if role is Role.LIBERAL else Party.FASCIST
    return frozendict(
        won=state.winner is party, seconds=tuple(getattr(agent, "seconds", ()))
    )


def _measure(job: tuple[str, Role, int, int]) -> frozendict:
    return measure(*job)


def main(argv: list[str] | None = None) -> None:
    """Prints a table with one row of win rates and decision times.

    Args:
        argv: The command-line arguments, or None to read them from sys.argv.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hero", choices=HEROES, default="ismcts")
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--workers", type=int, default=os.cpu_count())
    args = parser.parse_args(argv)
    jobs = [
        (args.hero, role, seed, args.iterations)
        for seed in range(args.games)
        for role in (Role.LIBERAL, Role.HITLER if seed % 2 == 0 else Role.FASCIST)
    ]
    if args.workers == 1:
        results = [_measure(job) for job in jobs]
    else:
        with Pool(args.workers) as pool:
            results = pool.map(_measure, jobs, chunksize=1)
    liberal = [
        r["won"] for (_, role, _, _), r in zip(jobs, results) if role is Role.LIBERAL
    ]
    fascist = [
        r["won"]
        for (_, role, _, _), r in zip(jobs, results)
        if role is not Role.LIBERAL
    ]
    seconds = [s for r in results for s in r["seconds"]]
    row = [
        args.hero,
        "-" if args.hero == "biased" else str(args.iterations),
        str(args.games),
        f"{sum(liberal) / len(liberal):.1%}",
        f"{sum(fascist) / len(fascist):.1%}",
        f"{sum(seconds) / len(seconds):.2f}" if seconds else "-",
        f"{max(seconds):.2f}" if seconds else "-",
    ]
    table = [list(COLUMNS), row]
    widths = [max(len(r[i]) for r in table) for i in range(len(COLUMNS))]
    for r in table:
        print("  ".join(cell.ljust(width) for cell, width in zip(r, widths)).rstrip())


if __name__ == "__main__":
    main()
