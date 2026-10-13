"""Stratified block randomization.

A middle-ground option between simple permuted blocks and full covariate
minimization: subjects are grouped into strata (e.g. by site, or by a
single coarse covariate combination), and each stratum runs its own
independent permuted-block sequence. This keeps arms balanced within each
stratum at the cost of needing enough subjects per stratum to fill blocks
-- with many strata or small strata, minimization usually balances better.
"""

from .block import BlockRandomizer


class StratifiedBlockRandomizer:
    def __init__(self, arms, ratio=None, block_sizes=(4,), rng=None):
        BlockRandomizer(arms, ratio, block_sizes, rng)  # validate at construction
        self.arms = arms
        self.ratio = ratio
        self.block_sizes = block_sizes
        self.rng = rng
        self._strata = {}

    def _get_block_randomizer(self, stratum_key):
        if stratum_key not in self._strata:
            self._strata[stratum_key] = BlockRandomizer(
                self.arms, self.ratio, self.block_sizes, self.rng
            )
        return self._strata[stratum_key]

    def assign(self, covariates):
        """Assign one subject given a dict of stratification covariates.
        Returns (arm, block_id, block_size, stratum_key)."""
        stratum_key = tuple(sorted(covariates.items()))
        br = self._get_block_randomizer(stratum_key)
        arm, block_id, block_size = br.next()
        return arm, block_id, block_size, stratum_key
