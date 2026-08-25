"""Pocock & Simon (1975) minimization.

Reference: Pocock SJ, Simon R. "Sequential treatment assignment with
balancing for prognostic factors in the controlled clinical trial."
Biometrics. 1975;31(1):103-115.

For every stratification factor the algorithm tracks assignment counts by
arm within each observed level of that factor (marginal counts, not full
cross-tabulated strata -- this is what lets minimization balance many
covariates at once without the empty-cell problem stratified blocks run
into). For a new subject, and for each candidate arm, it computes the
"range" imbalance statistic (max count - min count across arms) that would
result within each of the subject's factor levels if the subject were
assigned to that arm, weights each factor's range by its configured
weight, and sums them (the original range method proposed by Pocock and
Simon, as opposed to the variance method). The arm with the lowest total
imbalance is favored. Overall (marginal) treatment balance is included as
an implicit extra factor by default, matching common minimization
implementations. Ties are broken with weighted simple randomization
(weighted by the allocation ratio); non-ties use the biased-coin rule,
assigning the best arm with probability p and the runner-up(s) with
probability 1-p, so the method is never fully deterministic.
"""

import random


class MinimizationRandomizer:
    def __init__(
        self,
        arms,
        ratio=None,
        factor_weights=None,
        p_biased_coin=0.8,
        rng=None,
        include_overall=True,
        overall_weight=1.0,
    ):
        if len(arms) < 2:
            raise ValueError("need at least two arms")
        if ratio is None:
            ratio = [1] * len(arms)
        if len(ratio) != len(arms):
            raise ValueError("ratio must have exactly one entry per arm")
        if not (0.0 < p_biased_coin <= 1.0):
            raise ValueError("p_biased_coin must be in (0, 1]")

        self.arms = list(arms)
        self.ratio = list(ratio)
        self.factor_weights = dict(factor_weights or {})
        self.p = p_biased_coin
        self.rng = rng if rng is not None else random.Random()
        self.include_overall = include_overall
        self.overall_weight = overall_weight

        # counts[factor][level][arm] -> int
        self.counts = {}
        self.totals = {a: 0 for a in self.arms}

    def _range_if_assigned(self, factor, level, arm):
        levels = self.counts.setdefault(factor, {})
        arm_counts = levels.setdefault(level, {a: 0 for a in self.arms})
        hypothetical = dict(arm_counts)
        hypothetical[arm] = hypothetical.get(arm, 0) + 1
        return max(hypothetical.values()) - min(hypothetical.values())

    def _overall_range_if_assigned(self, arm):
        hypothetical = dict(self.totals)
        hypothetical[arm] = hypothetical.get(arm, 0) + 1
        return max(hypothetical.values()) - min(hypothetical.values())

    def score(self, covariates):
        """Return {arm: weighted total imbalance} if this subject were
        assigned to each arm."""
        scores = {}
        for arm in self.arms:
            total = 0.0
            for factor, level in covariates.items():
                weight = self.factor_weights.get(factor, 1.0)
                total += weight * self._range_if_assigned(factor, level, arm)
            if self.include_overall:
                total += self.overall_weight * self._overall_range_if_assigned(arm)
            scores[arm] = total
        return scores

    def _weighted_choice(self, candidates):
        weights = [self.ratio[self.arms.index(a)] for a in candidates]
        return self.rng.choices(candidates, weights=weights, k=1)[0]

    def assign(self, covariates):
        """Assign one subject. Returns (arm, reason, scores)."""
        scores = self.score(covariates)
        min_score = min(scores.values())
        best_arms = [a for a, s in scores.items() if abs(s - min_score) < 1e-9]

        if len(best_arms) == len(self.arms):
            arm = self._weighted_choice(self.arms)
            reason = "tie_all_random"
        elif len(best_arms) > 1:
            arm = self._weighted_choice(best_arms)
            reason = "tie_random"
        elif self.rng.random() < self.p:
            arm = best_arms[0]
            reason = "biased_coin_minimize"
        else:
            others = [a for a in self.arms if a != best_arms[0]]
            arm = self.rng.choice(others)
            reason = "biased_coin_explore"

        for factor, level in covariates.items():
            levels = self.counts.setdefault(factor, {})
            arm_counts = levels.setdefault(level, {a: 0 for a in self.arms})
            arm_counts[arm] = arm_counts.get(arm, 0) + 1
        self.totals[arm] = self.totals.get(arm, 0) + 1

        return arm, reason, scores
