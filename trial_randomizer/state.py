"""JSON persistence for randomizer state, including the RNG state itself
so a sequence started in one CLI invocation continues correctly (and
reproducibly) in the next one."""

import json
import os


def rng_state_to_json(state):
    """Serialize an RNG state tuple to a JSON-serializable list."""
    version, internal, gauss_next = state
    return [version, list(internal), gauss_next]


def rng_state_from_json(data):
    """Deserialize an RNG state from JSON. Validates structure."""
    if not isinstance(data, (list, tuple)) or len(data) != 3:
        raise ValueError(f"Invalid RNG state format: expected list of 3 elements, got {type(data)}")
    version, internal, gauss_next = data
    if not isinstance(internal, (list, tuple)):
        raise ValueError(f"Invalid RNG state: internal state must be a list, got {type(internal)}")
    return (version, tuple(internal), gauss_next)


def load_state(path):
    """Load state from a JSON file. Returns None if file doesn't exist."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid state file: expected JSON object, got {type(data)}")
    return data


def save_state(path, state):
    """Save state to a JSON file."""
    if not isinstance(state, dict):
        raise ValueError(f"Invalid state: expected dict, got {type(state)}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
