import pytest
from trial_randomizer.block import generate_block_schedule


def test_block_randomization():
    treatments = ["Arm A", "Arm B"]
    block_sizes = [4, 6]
    schedule = generate_block_schedule(treatments, block_sizes, total_subjects=20, seed=42)
    assert len(schedule) >= 20
    assert "Arm A" in schedule
    assert "Arm B" in schedule
