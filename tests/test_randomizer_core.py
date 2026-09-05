"""
Core functionality tests for trial-randomizer randomization algorithms.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from trial_randomizer.block import BlockRandomizer, generate_block_schedule
from trial_randomizer.minimization import MinimizationRandomizer
from trial_randomizer.stratified import StratifiedBlockRandomizer
from trial_randomizer.audit import append_rows, read_rows, balance_counts, format_balance_report


class TestBlockRandomizer:
    """Tests for permuted block randomization."""

    def test_basic_block_randomization(self):
        br = BlockRandomizer(arms=["A", "B"], block_sizes=[4])
        results = [br.next() for _ in range(20)]
        arms = [r[0] for r in results]
        assert arms.count("A") == 10
        assert arms.count("B") == 10

    def test_multiple_block_sizes(self):
        br = BlockRandomizer(arms=["A", "B"], block_sizes=[4, 6, 8])
        results = [br.next() for _ in range(100)]
        arms = [r[0] for r in results]
        # With 1:1 ratio, should be roughly balanced
        assert abs(arms.count("A") - arms.count("B")) <= 2

    def test_unequal_ratio(self):
        br = BlockRandomizer(arms=["A", "B"], ratio=[2, 1], block_sizes=[6])
        results = [br.next() for _ in range(30)]
        arms = [r[0] for r in results]
        assert arms.count("A") == 20
        assert arms.count("B") == 10

    def test_three_arms(self):
        br = BlockRandomizer(arms=["A", "B", "C"], block_sizes=[6])
        results = [br.next() for _ in range(30)]
        arms = [r[0] for r in results]
        assert arms.count("A") == 10
        assert arms.count("B") == 10
        assert arms.count("C") == 10

    def test_invalid_arms(self):
        with pytest.raises(ValueError, match="need at least two arms"):
            BlockRandomizer(arms=["A"], block_sizes=[4])

    def test_invalid_ratio_length(self):
        with pytest.raises(ValueError, match="ratio must have exactly one entry per arm"):
            BlockRandomizer(arms=["A", "B"], ratio=[1, 1, 1], block_sizes=[4])

    def test_invalid_ratio_negative(self):
        with pytest.raises(ValueError, match="ratio entries must be positive"):
            BlockRandomizer(arms=["A", "B"], ratio=[1, -1], block_sizes=[4])

    def test_invalid_block_size(self):
        with pytest.raises(ValueError, match="must be a positive multiple"):
            BlockRandomizer(arms=["A", "B"], block_sizes=[5])

    def test_empty_block_sizes(self):
        with pytest.raises(ValueError, match="at least one block size is required"):
            BlockRandomizer(arms=["A", "B"], block_sizes=[])

    def test_reproducibility_with_seed(self):
        import random
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        br1 = BlockRandomizer(arms=["A", "B"], block_sizes=[4], rng=rng1)
        br2 = BlockRandomizer(arms=["A", "B"], block_sizes=[4], rng=rng2)
        results1 = [br1.next()[0] for _ in range(20)]
        results2 = [br2.next()[0] for _ in range(20)]
        assert results1 == results2

    def test_generate_block_schedule(self):
        schedule = generate_block_schedule(["A", "B"], block_sizes=[4], total_subjects=20, seed=42)
        assert len(schedule) == 20
        assert schedule.count("A") == 10
        assert schedule.count("B") == 10


class TestMinimizationRandomizer:
    """Tests for Pocock-Simon minimization."""

    def test_basic_minimization(self):
        mr = MinimizationRandomizer(arms=["A", "B"])
        covariates = {"site": "Site1", "age_group": "over65"}
        arm, reason, scores = mr.assign(covariates)
        assert arm in ["A", "B"]
        assert reason in ["tie_all_random", "tie_random", "biased_coin_minimize", "biased_coin_explore"]
        assert "A" in scores and "B" in scores

    def test_balance_improvement(self):
        """Test that minimization improves balance over random assignment."""
        mr = MinimizationRandomizer(arms=["A", "B"], p_biased_coin=1.0)
        # Assign 100 subjects with same covariates
        for _ in range(100):
            mr.assign({"site": "Site1"})
        # With p=1.0, should be perfectly balanced
        assert mr.totals["A"] == mr.totals["B"]

    def test_factor_weights(self):
        mr = MinimizationRandomizer(
            arms=["A", "B"],
            factor_weights={"site": 2.0, "age_group": 1.0}
        )
        arm, reason, scores = mr.assign({"site": "Site1", "age_group": "over65"})
        assert arm in ["A", "B"]

    def test_invalid_arms(self):
        with pytest.raises(ValueError, match="need at least two arms"):
            MinimizationRandomizer(arms=["A"])

    def test_invalid_p_biased_coin(self):
        with pytest.raises(ValueError, match="p_biased_coin must be in"):
            MinimizationRandomizer(arms=["A", "B"], p_biased_coin=0.0)

    def test_invalid_p_biased_coin_high(self):
        with pytest.raises(ValueError, match="p_biased_coin must be in"):
            MinimizationRandomizer(arms=["A", "B"], p_biased_coin=1.5)


class TestStratifiedBlockRandomizer:
    """Tests for stratified block randomization."""

    def test_basic_stratified(self):
        sbr = StratifiedBlockRandomizer(arms=["A", "B"], block_sizes=[4])
        covariates = {"site": "Site1"}
        arm, block_id, block_size, stratum_key = sbr.assign(covariates)
        assert arm in ["A", "B"]
        assert block_id == 1
        assert block_size == 4

    def test_multiple_strata(self):
        sbr = StratifiedBlockRandomizer(arms=["A", "B"], block_sizes=[4])
        # Assign to different strata
        for _ in range(10):
            sbr.assign({"site": "Site1"})
            sbr.assign({"site": "Site2"})
        # Each stratum should have its own block randomizer
        assert len(sbr._strata) == 2

    def test_balance_within_stratum(self):
        sbr = StratifiedBlockRandomizer(arms=["A", "B"], block_sizes=[4])
        results = []
        for _ in range(20):
            arm, _, _, _ = sbr.assign({"site": "Site1"})
            results.append(arm)
        assert results.count("A") == 10
        assert results.count("B") == 10


class TestAuditLog:
    """Tests for audit log functionality."""

    def test_append_and_read_rows(self, tmp_path):
        audit_file = tmp_path / "test_audit.csv"
        rows = [
            {"seq": 1, "timestamp": "2024-01-01T00:00:00", "method": "block",
             "subject_id": "S1", "arm": "A", "block_id": 1, "block_size": 4},
            {"seq": 2, "timestamp": "2024-01-01T00:01:00", "method": "block",
             "subject_id": "S2", "arm": "B", "block_id": 1, "block_size": 4},
        ]
        append_rows(str(audit_file), rows)
        read = read_rows(str(audit_file))
        assert len(read) == 2
        assert read[0]["arm"] == "A"
        assert read[1]["arm"] == "B"

    def test_read_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_rows(str(tmp_path / "nonexistent.csv"))

    def test_balance_counts(self):
        rows = [
            {"arm": "A", "stratum": {"site": "Site1"}},
            {"arm": "A", "stratum": {"site": "Site1"}},
            {"arm": "B", "stratum": {"site": "Site1"}},
            {"arm": "A", "stratum": {"site": "Site2"}},
            {"arm": "B", "stratum": {"site": "Site2"}},
        ]
        overall, per_stratum = balance_counts(rows)
        assert overall["A"] == 3
        assert overall["B"] == 2

    def test_format_balance_report(self):
        rows = [
            {"arm": "A", "stratum": {"site": "Site1"}},
            {"arm": "B", "stratum": {"site": "Site1"}},
        ]
        report = format_balance_report(rows)
        assert "Balance-check report" in report
        assert "A" in report
        assert "B" in report
