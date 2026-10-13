"""Permuted block randomization.

Standard method: subjects are allocated in blocks. Each block contains a
fixed multiple of the allocation ratio (e.g. ratio 1:1 with block size 4
gives 2 of each arm), the block's contents are shuffled, and subjects
receive arms one at a time off the shuffled block. When a block is
exhausted a new one is started. Supplying more than one block size makes
the block length itself unpredictable, which is standard practice for
concealment (a fixed block size lets the last 1-2 allocations in a block
be guessed).
"""

import random
from numbers import Integral


class BlockRandomizer:
    def __init__(self, arms, ratio=None, block_sizes=(4,), rng=None):
        if len(arms) < 2:
            raise ValueError("need at least two arms")
        if len(set(arms)) != len(arms):
            raise ValueError("arm names must be unique")
        if ratio is None:
            ratio = [1] * len(arms)
        if len(ratio) != len(arms):
            raise ValueError("ratio must have exactly one entry per arm")
        if any(not isinstance(r, Integral) or isinstance(r, bool) or r <= 0 for r in ratio):
            raise ValueError("ratio entries must be positive")
        if not block_sizes:
            raise ValueError("at least one block size is required")

        unit = sum(ratio)
        for bs in block_sizes:
            if not isinstance(bs, Integral) or isinstance(bs, bool) or bs <= 0 or bs % unit != 0:
                raise ValueError(
                    f"block size {bs} must be a positive multiple of the "
                    f"allocation ratio unit ({unit} = sum of ratio)"
                )

        self.arms = list(arms)
        self.ratio = list(ratio)
        self.block_sizes = list(block_sizes)
        self.rng = rng if rng is not None else random.Random()

        self._queue = []
        self._block_id = 0
        self._block_size_current = None

    def _new_block(self):
        self._block_id += 1
        size = self.rng.choice(self.block_sizes)
        self._block_size_current = size
        multiplier = size // sum(self.ratio)
        block = []
        for arm, r in zip(self.arms, self.ratio):
            block.extend([arm] * (r * multiplier))
        self.rng.shuffle(block)
        self._queue = block

    def next(self):
        """Return (arm, block_id, block_size) for the next subject."""
        if not self._queue:
            self._new_block()
        # pop() from the end is O(1) vs pop(0) which is O(n).
        # Since the block is already shuffled, popping from the end is equivalent.
        arm = self._queue.pop()
        return arm, self._block_id, self._block_size_current


def generate_block_schedule(treatments, block_sizes=(4,), total_subjects=20, ratio=None, seed=None):
    """Generate a sequence of randomized allocations for a cohort of subjects."""
    if not isinstance(total_subjects, Integral) or isinstance(total_subjects, bool) or total_subjects < 0:
        raise ValueError("total_subjects must be a non-negative integer")
    rng = random.Random(seed) if seed is not None else random.Random()
    randomizer = BlockRandomizer(arms=treatments, ratio=ratio, block_sizes=block_sizes, rng=rng)
    schedule = []
    for _ in range(total_subjects):
        arm, _, _ = randomizer.next()
        schedule.append(arm)
    return schedule

