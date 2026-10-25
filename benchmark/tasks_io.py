"""Loads and validates tasks.json."""
import json
from collections import Counter

from . import config


def load_tasks(path):
    tasks = json.load(open(path, encoding="utf-8"))
    ids = set()
    for t in tasks:
        assert t["id"] not in ids, f"duplicate task id {t['id']}"
        ids.add(t["id"])
        assert t["stratum"] in config.STRATA, f"{t['id']}: bad stratum"
        assert t["gold_subtasks"], f"{t['id']}: no gold subtasks"
        gids = {g["id"] for g in t["gold_subtasks"]}
        for g in t["gold_subtasks"]:
            assert set(g["depends_on"]) <= gids, f"{t['id']}: bad dependency"
        if "fault_query" in t:
            assert t["faulted_gold_id"] in gids, f"{t['id']}: bad faulted_gold_id"
    return tasks


def describe(tasks):
    return dict(Counter(t["stratum"] for t in tasks))
