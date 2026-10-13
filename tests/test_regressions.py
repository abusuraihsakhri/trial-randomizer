"""Regression tests for allocation integrity and browser/API hardening."""

import csv
import os
import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents.api import app
from trial_randomizer.block import BlockRandomizer, generate_block_schedule
from trial_randomizer.minimization import MinimizationRandomizer
from trial_randomizer.stratified import StratifiedBlockRandomizer
from trial_randomizer.cli import main


@pytest.mark.parametrize("ratio", [[0, 1], [1, -1], [1.5, 1], [True, 1]])
def test_block_rejects_invalid_ratios(ratio):
    with pytest.raises(ValueError, match="ratio entries"):
        BlockRandomizer(["A", "B"], ratio=ratio)


def test_block_rejects_duplicate_arms_and_fractional_size():
    with pytest.raises(ValueError, match="unique"):
        BlockRandomizer(["A", "A"])
    with pytest.raises(ValueError, match="positive multiple"):
        BlockRandomizer(["A", "B"], block_sizes=[4.0])


def test_cohort_size_must_be_nonnegative_integer():
    with pytest.raises(ValueError, match="non-negative integer"):
        generate_block_schedule(["A", "B"], total_subjects=-1)
    with pytest.raises(ValueError, match="non-negative integer"):
        generate_block_schedule(["A", "B"], total_subjects=2.5)


def test_minimization_preserves_unequal_target_ratio():
    mr = MinimizationRandomizer(["A", "B"], ratio=[2, 1], p_biased_coin=1.0,
                                rng=random.Random(123))
    allocations = [mr.assign({"site": "SiteA"})[0] for _ in range(60)]
    assert allocations.count("A") == 40
    assert allocations.count("B") == 20


def test_minimization_rejects_invalid_configuration():
    with pytest.raises(ValueError, match="unique"):
        MinimizationRandomizer(["A", "A"])
    with pytest.raises(ValueError, match="positive integers"):
        MinimizationRandomizer(["A", "B"], ratio=[0, 1])
    with pytest.raises(ValueError, match="finite"):
        MinimizationRandomizer(["A", "B"], factor_weights={"site": float("nan")})
    with pytest.raises(ValueError, match="finite"):
        MinimizationRandomizer(["A", "B"], overall_weight=float("inf"))


def test_stratified_rejects_invalid_config_immediately():
    with pytest.raises(ValueError, match="unique"):
        StratifiedBlockRandomizer(["A", "A"])


def test_block_cli_does_not_expose_seed_in_audit_or_stdout(tmp_path, capsys):
    state = tmp_path / "state.json"
    audit = tmp_path / "audit.csv"
    assert main(["block", "--state", str(state), "--audit", str(audit),
                 "--arms", "A", "B", "--n", "3", "--seed", "12345"]) == 0
    with audit.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 3
    assert all(row["seed"] == "" for row in rows)
    assert "12345" not in capsys.readouterr().out


def test_cli_rejects_incompatible_state_without_allocating(tmp_path):
    state = tmp_path / "state.json"
    audit = tmp_path / "audit.csv"
    assert main(["block", "--state", str(state), "--audit", str(audit),
                 "--arms", "A", "B"]) == 0
    with pytest.raises(ValueError, match="State file belongs"):
        main(["minimize", "--state", str(state), "--audit", str(audit)])


def test_cli_rejects_zero_subjects(tmp_path):
    with pytest.raises(SystemExit, match="positive integer"):
        main(["block", "--state", str(tmp_path / "state.json"),
              "--audit", str(tmp_path / "audit.csv"), "--arms", "A", "B", "--n", "0"])


def test_cli_envelopes_writes_files(tmp_path):
    labels = tmp_path / "envelopes.txt"
    master = tmp_path / "master.csv"
    assert main(["envelopes", "--arms", "A", "B", "--n", "4",
                 "--labels-out", str(labels), "--master-out", str(master)]) == 0
    assert len(labels.read_text().splitlines()) == 4
    with master.open(newline="", encoding="utf-8") as file:
        assert len(list(csv.DictReader(file))) == 4


def test_cli_path_traversal_checked():
    from trial_randomizer.cli import _validate_path
    with pytest.raises(ValueError, match="traversal"):
        _validate_path("../escape.csv")


def test_api_fails_closed_without_key(monkeypatch):
    monkeypatch.delenv("TRIAL_RANDOMIZER_API_KEY", raising=False)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/api/audit/logs")
        assert response.status_code == 503


def test_api_rejects_invalid_key(monkeypatch):
    monkeypatch.setenv("TRIAL_RANDOMIZER_API_KEY", "test-secret")
    with TestClient(app) as client:
        assert client.get("/api/audit/logs").status_code == 401
        response = client.get("/api/audit/logs", headers={"x-api-key": "test-secret"})
        assert response.status_code == 200
