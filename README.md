# Trial Randomizer

> **Domain:** Clinical Decision Support & Biomedical Computing

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg?logo=fastapi&logoColor=white)

</div>

---

## Overview

Trial Randomizer is a clinical trial treatment allocation library implementing three randomization methods:

1. **Permuted Block Randomization** — Standard method with configurable block sizes for allocation concealment
2. **Pocock-Simon Minimization** — Covariate-adaptive randomization balancing multiple prognostic factors
3. **Stratified Block Randomization** — Independent block sequences per stratum

All methods produce a tamper-evident, HMAC-SHA256 signed audit trail for regulatory compliance.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/abusuraihsakhri/trial-randomizer.git
cd trial-randomizer

# Install dependencies
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### Requirements

- Python 3.10+
- fastapi >= 0.111.0
- uvicorn >= 0.29.0
- pydantic >= 2.0.0

---

## Usage

### Python API

```python
from trial_randomizer.block import BlockRandomizer, generate_block_schedule
from trial_randomizer.minimization import MinimizationRandomizer
from trial_randomizer.stratified import StratifiedBlockRandomizer

# Permuted block randomization
schedule = generate_block_schedule(
    treatments=["Arm A", "Arm B"],
    block_sizes=[4, 6],
    total_subjects=100,
    seed=42
)

# Using the BlockRandomizer directly
br = BlockRandomizer(arms=["A", "B"], block_sizes=[4, 6])
arm, block_id, block_size = br.next()

# Pocock-Simon minimization
mr = MinimizationRandomizer(arms=["A", "B"], p_biased_coin=0.8)
arm, reason, scores = mr.assign({"site": "Site1", "age_group": "over65"})

# Stratified block randomization
sbr = StratifiedBlockRandomizer(arms=["A", "B"], block_sizes=[4])
arm, block_id, block_size, stratum = sbr.assign({"site": "Site1"})
```

### Command Line Interface

```bash
# Permuted block randomization
python -m trial_randomizer.cli block \
    --state trial_state.json \
    --audit audit_log.csv \
    --arms A B \
    --ratio 1 1 \
    --block-sizes 4 6 \
    --n 10

# Pocock-Simon minimization
python -m trial_randomizer.cli minimize \
    --state trial_state.json \
    --audit audit_log.csv \
    --arms A B \
    --factor site=Site1 age_group=over65

# Stratified block randomization
python -m trial_randomizer.cli stratified \
    --state trial_state.json \
    --audit audit_log.csv \
    --arms A B \
    --stratum site=Site1

# Generate concealment envelopes
python -m trial_randomizer.cli envelopes \
    --arms A B \
    --n 100 \
    --labels-out envelopes.txt \
    --master-out master_key.csv

# Balance-check report
python -m trial_randomizer.cli balance-report \
    --audit audit_log.csv
```

### FastAPI REST Server

```bash
# Start the server
python cli.py serve --host 127.0.0.1 --port 8000

# Or using uvicorn directly
uvicorn agents.api:app --host 127.0.0.1 --port 8000
```

API Endpoints:
- `GET /health` — Health check
- `GET /metrics` — Prometheus-style metrics
- `POST /api/audit` — Submit a task for evaluation
- `POST /api/chat` — Query the supervisory chat
- `GET /api/audit/logs` — Retrieve audit trail

---

## Security Features

### Zero-PHI Outbound Guard
Active regex inspection blocking SSNs, MRNs, phone numbers, emails, and patient identifiers from outbound data.

### Tamper-Evident Audit Trail
Chained, HMAC-SHA256 signed logs for every allocation decision and state transition. Integrity verification includes both hash chain linkage and signature validation.

**Important:** Set the `AUDIT_SECRET_KEY` environment variable in production. Without it, a random key is generated (with a warning), which is not suitable for production use.

```bash
# Production deployment
export AUDIT_SECRET_KEY="your-secure-random-key"
```

### Path Traversal Protection
All file path inputs are validated to prevent directory traversal attacks.

---

## Testing

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=trial_randomizer --cov=agents

# Run specific test files
pytest tests/test_randomizer_core.py -v
pytest tests/test_security.py -v
```

---

## Docker Deployment

```bash
# Build and run with Docker Compose
AUDIT_SECRET_KEY="your-secure-key" docker-compose up --build

# Or build and run manually
docker build -t trial-randomizer .
docker run -p 8000:8000 -e AUDIT_SECRET_KEY="your-secure-key" trial-randomizer
```

---

## Project Structure

```
trial-randomizer/
├── trial_randomizer/      # Core randomization library
│   ├── block.py           # Permuted block randomization
│   ├── minimization.py    # Pocock-Simon minimization
│   ├── stratified.py      # Stratified block randomization
│   ├── audit.py           # Audit log storage and reporting
│   ├── state.py           # JSON state persistence
│   └── cli.py             # Command-line interface
├── agents/                # Enterprise analytical suite
│   ├── api.py             # FastAPI REST server
│   ├── base.py            # Security, PHI guard, audit trail
│   ├── models.py          # Pydantic data models
│   ├── supervisor.py      # Multi-agent orchestrator
│   ├── workers.py         # Specialized evaluation workers
│   └── ...
├── tests/                 # Test suite
├── cli.py                 # Main CLI entry point
├── simulator.py           # High-throughput simulation
├── enrichment.py          # Additional analytical engines
├── pyproject.toml         # Project configuration
├── Dockerfile             # Container build
└── docker-compose.yml     # Container orchestration
```

---

## License

MIT License
