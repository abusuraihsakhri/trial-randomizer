"""JSON persistence for randomizer state, including the RNG state itself
so a sequence started in one CLI invocation continues correctly (and
reproducibly) in the next one."""

import json
import os


def rng_state_to_json(state):
    version, internal, gauss_next = state
    return [version, list(internal), gauss_next]


def rng_state_from_json(data):
    version, internal, gauss_next = data
    return (version, tuple(internal), gauss_next)


def load_state(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(path, state):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
