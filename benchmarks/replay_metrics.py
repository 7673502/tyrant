"""Measures LLM play quality from replay files.

Each metric is a pure function of a replay dict. Only replays in the current
format are read; older formats raise UnsupportedReplayError.

Claims are matched to the private knowledge of the government they follow:
a president claim is checked against that government's draw (and its
discard, when the claim names one), and a chancellor claim against what the
chancellor received. A Liberal claim that differs from the truth is a
mis-claim rather than a lie. Lie rates count each player's first claim about
a government; a correction (a claim event with `correction` set) counts
only towards resolving that government's claim conflict.

A speech is repeated when at least REPEAT_THRESHOLD of its word 3-grams
already appeared in the same player's earlier speeches. The threshold is a
heuristic and stays fixed so that runs remain comparable.
"""

import argparse
import gzip
import json
import re
from collections import Counter
from pathlib import Path

from tyrant.engine.replay import check_replay_version

REPEAT_THRESHOLD = 0.5
NGRAM_SIZE = 3


def load(path: str | Path) -> dict:
    """Reads a replay file that is either gzipped or plain JSON.

    Args:
        path: The replay file.

    Returns:
        The replay as plain dicts.

    Raises:
        UnsupportedReplayError: If the replay is not in the current format.
    """
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            replay = json.load(f)
    except gzip.BadGzipFile:
        with open(path, encoding="utf-8") as f:
            replay = json.load(f)
    check_replay_version(replay)
    return replay


def _events(replay: dict, event_type: str) -> list[dict]:
    return [
        event
        for step in replay["steps"]
        for event in step["events"]
        if event["type"] == event_type
    ]


def _speeches(replay: dict) -> list[dict]:
    return [event for event in _events(replay, "speech") if event["text"] is not None]


def _parties(replay: dict) -> dict[int, str]:
    return {player["uid"]: player["party"] for player in replay["players"]}


def unanimous_election_rate(replay: dict) -> tuple[int, int, int]:
    """Counts elections where every vote was the same.

    Args:
        replay: The replay dict.

    Returns:
        The unanimous elections, the all-ja elections and all elections.
    """
    elections = _events(replay, "election")
    votes = [set(election["votes"].values()) for election in elections]
    unanimous = sum(len(vote) == 1 for vote in votes)
    all_ja = sum(vote == {"ja"} for vote in votes)
    return unanimous, all_ja, len(elections)


def _enact_claims(replay: dict) -> list[tuple[dict, dict]]:
    truth: dict = {}
    claims = []
    for step in replay["steps"]:
        for item in step["knowledge"]:
            if item["type"] == "president_draw":
                truth = {"president_draw": item}
            elif item["type"] in ("president_discard", "chancellor_receive"):
                truth[item["type"]] = item
        for event in step["events"]:
            if event["type"] != "claim":
                continue
            claim = event["claim"]
            if event.get("correction"):
                continue
            if claim["type"] in ("president_enact", "chancellor_enact"):
                claims.append((claim, dict(truth)))
    return claims


def _is_true(claim: dict, truth: dict) -> bool:
    if claim["type"] == "chancellor_enact":
        return Counter(claim["policies"]) == Counter(
            truth["chancellor_receive"]["policies"]
        )
    if Counter(claim["policies"]) != Counter(truth["president_draw"]["policies"]):
        return False
    return claim["discarded"] == truth["president_discard"]["discarded"]


def claim_lie_rates(replay: dict) -> dict[str, tuple[int, int, int]]:
    """Counts enact claims that differ from the claimant's private knowledge.

    Args:
        replay: The replay dict.

    Returns:
        For each party, the false claims, the declined claims and all claims
        made by its members.
    """
    parties = _parties(replay)
    rates = {"liberal": (0, 0, 0), "fascist": (0, 0, 0)}
    for claim, truth in _enact_claims(replay):
        party = parties[claim["uid"]]
        false, declined, total = rates[party]
        if claim["policies"] is None:
            rates[party] = (false, declined + 1, total + 1)
        else:
            rates[party] = (false + (not _is_true(claim, truth)), declined, total + 1)
    return rates


def _passed(claim: dict) -> Counter:
    drawn = Counter(claim["policies"])
    drawn[claim["discarded"]] -= 1
    return +drawn


def _conflict(president: dict, chancellor: dict) -> bool:
    return _passed(president) != Counter(chancellor["policies"])


def claim_conflicts(replay: dict) -> tuple[int, int]:
    """Counts governments whose president and chancellor claims conflict.

    Args:
        replay: The replay dict.

    Returns:
        The governments whose first claims conflict, and how many of those
        a correction made consistent.
    """
    order: list[list[dict]] = []
    for step in replay["steps"]:
        for event in step["events"]:
            if event["type"] == "policy_enacted":
                order.append([])
            elif event["type"] == "claim" and order:
                order[-1].append(event)
    raised = resolved = 0
    for events in order:
        presidents = [
            e
            for e in events
            if e["claim"]["type"] == "president_enact" and e["claim"]["policies"]
        ]
        chancellors = [
            e
            for e in events
            if e["claim"]["type"] == "chancellor_enact" and e["claim"]["policies"]
        ]
        if not presidents or not chancellors:
            continue
        if _conflict(presidents[0]["claim"], chancellors[0]["claim"]):
            raised += 1
            corrected = presidents[-1].get("correction") or chancellors[-1].get(
                "correction"
            )
            resolved += bool(corrected) and not _conflict(
                presidents[-1]["claim"], chancellors[-1]["claim"]
            )
    return raised, resolved


def speech_share(replay: dict) -> tuple[int, int, int]:
    """Counts discussion steps.

    Args:
        replay: The replay dict.

    Returns:
        The speak and pass steps, the speak steps and all steps.
    """
    types = Counter(step["action"]["type"] for step in replay["steps"])
    return types["speak"] + types["pass"], types["speak"], len(replay["steps"])


def _ngrams(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return {
        tuple(words[i : i + NGRAM_SIZE]) for i in range(len(words) - NGRAM_SIZE + 1)
    }


def repeated_speech_rate(replay: dict) -> tuple[int, int]:
    """Counts speeches that mostly repeat the same player's earlier speeches.

    Args:
        replay: The replay dict.

    Returns:
        The repeated speeches and all speeches.
    """
    seen: dict[int, set[tuple[str, ...]]] = {}
    speeches = _speeches(replay)
    repeated = 0
    for speech in speeches:
        grams = _ngrams(speech["text"])
        earlier = seen.setdefault(speech["uid"], set())
        if grams and len(grams & earlier) / len(grams) >= REPEAT_THRESHOLD:
            repeated += 1
        earlier |= grams
    return repeated, len(speeches)


def faults(replay: dict) -> tuple[dict[str, int], int]:
    """Counts agent faults by exception class, and steps played by fallback.

    Args:
        replay: The replay dict.

    Returns:
        The faults per exception class and the fallback steps.
    """
    reasons = Counter(fault["reason"].split("(")[0] for fault in replay["faults"])
    fallbacks = sum(step["fallback"] for step in replay["steps"])
    return dict(sorted(reasons.items())), fallbacks


def _fraction(part: int, whole: int) -> str:
    if whole == 0:
        return f"{part}/0"
    return f"{part}/{whole} ({part / whole:.0%})"


def _rows(replay: dict) -> list[tuple[str, str]]:
    unanimous, all_ja, elections = unanimous_election_rate(replay)
    lies = claim_lie_rates(replay)
    raised, resolved = claim_conflicts(replay)
    discussion, speeches, steps = speech_share(replay)
    reasons, fallbacks = faults(replay)
    return [
        ("Version", str(replay["version"])),
        ("Steps", str(steps)),
        ("Discussion share", _fraction(discussion, steps)),
        ("Speech share", _fraction(speeches, steps)),
        ("Unanimous elections", _fraction(unanimous, elections)),
        ("All-ja elections", _fraction(all_ja, elections)),
        ("Fascist claim lies", _fraction(lies["fascist"][0], lies["fascist"][2])),
        ("Liberal mis-claims", _fraction(lies["liberal"][0], lies["liberal"][2])),
        ("Declined claims", str(lies["fascist"][1] + lies["liberal"][1])),
        ("Claim conflicts raised", str(raised)),
        ("Claim conflicts resolved", str(resolved)),
        ("Repeated speeches", _fraction(*repeated_speech_rate(replay))),
        ("Faults", ", ".join(f"{k} {v}" for k, v in reasons.items()) or "0"),
        ("Fallbacks", str(fallbacks)),
    ]


def main(argv: list[str] | None = None) -> None:
    """Prints a table of metrics with one column per replay file.

    Args:
        argv: The command-line arguments, or None to read them from sys.argv.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("replays", nargs="+", type=Path)
    args = parser.parse_args(argv)
    columns = [_rows(load(path)) for path in args.replays]
    header = ["Metric", *(path.name for path in args.replays)]
    table = [header] + [
        [label, *(column[i][1] for column in columns)]
        for i, (label, _) in enumerate(columns[0])
    ]
    widths = [max(len(row[i]) for row in table) for i in range(len(header))]
    for row in table:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())


if __name__ == "__main__":
    main()
