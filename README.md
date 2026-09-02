# Trial Randomizer

> **Domain:** Clinical Decision Support & Biomedical Computing  
> **Reference Guidelines & Standards:** `Standard Clinical Formulations & ISO/IEC Quality Frameworks`

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg?logo=fastapi&logoColor=white)
![Audit Trail](https://img.shields.io/badge/Audit-HMAC--SHA256_Tamper--Evident-brightgreen.svg)
![Zero-PHI Guard](https://img.shields.io/badge/Guard-Zero--PHI_Outbound-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)

</div>

---

## 📖 What It Does

Audit log storage and the balance-check report.

Every allocation decision made by any of the three methods is appended as
one row to a CSV file, so the full history of who got what, when, and why
can be reconstructed later for a trial's audit trail. Complex fields
(stratum covariates, per-arm imbalance scores) are stored as JSON text
inside their cell.

Permuted block randomization.

Standard method: subjects are allocated in blocks. Each block contains a
fixed multiple of the allocation ratio (e.g. ratio 1:1 with block size 4
gives 2 of each arm), the block's contents are shuffled, and subjects
receive arms one at a time off the shuffled block. When a block is
exhausted a new one is started. Supplying more than one block size makes
the block length itself unpredictable, which is standard practice for
concealment (a fixed block size lets the last 1-2 allocations in a block
be guessed).

---

## ⚙️ Key Capabilities & Algorithmic Modules

### 🔬 Core Algorithmic & Evaluation Engines

- **`BlockRandomizer`** — dedicated module for block randomizer evaluation and state verification.
- **`MinimizationRandomizer`** — dedicated module for minimization randomizer evaluation and state verification.
- **`StratifiedBlockRandomizer`** — dedicated module for stratified block randomizer evaluation and state verification.

---

## 📐 Mathematical Formulation & Logic

```text
  """Return (arm, block_id, block_size) for the next subject."""
  min_score = min(scores.values())
  return (version, tuple(internal), gauss_next)
```

---

## 💻 CLI Quickstart & Usage

### 1. Guided Interactive Mode
```bash
python cli.py
```

### 2. Direct Parameterized Evaluation
```bash
python cli.py --task-id <value> --target <value> --primary <value> --secondary <value>
```

### Parameter Reference
- `--task-id`: Specifies input measurement or parameter value.
- `--target`: Specifies input measurement or parameter value.
- `--primary`: Specifies input measurement or parameter value.
- `--secondary`: Specifies input measurement or parameter value.
- `--critical`: Specifies input measurement or parameter value.
- `--status`: Specifies input measurement or parameter value.
- `--input`: Specifies input measurement or parameter value.
- `--output`: Specifies input measurement or parameter value.

### Input Data Schema

| Field | Description | Requirement |
|:------|:------------|:------------|
| `suite_name` | Parameter / observation metric | Required |
| `system_slug` | Parameter / observation metric | Required |
| `standard_reference` | Parameter / observation metric | Required |
| `test_cases` | Parameter / observation metric | Required |

---

## 🛡️ Security & Enterprise Architecture

* **Zero-PHI Outbound Interceptor:** Active AST and regex inspection blocking SSNs, MRNs, phone numbers, and patient identifiers.
* **Tamper-Evident HMAC-SHA256 Audit Trail:** Chained, cryptographically signed logs for every evaluation and state transition.
* **Air-Gapped LLM Reasoning Adapter:** Agnostic integration for local Ollama instances (`llama3`, `mistral`), Claude 3.5 Sonnet, GPT-4o, and deterministic test mocks.
* **Active Learning Bayesian Calibration:** Dynamic tracker updating worker reliability weights and monitoring Brier calibration drift.
* **FastAPI & Prometheus Telemetry:** Exposes OpenAPI 3.1 REST endpoints and operational Prometheus metrics (`/metrics`).

---

## 🧪 Testing & Verification

Run the automated test suite:

```bash
pytest -v
```

Execute high-throughput batch simulation benchmarks:

```bash
python simulator.py --tasks 1000 --concurrency 8
```

---

## 🐳 Container Deployment

```bash
docker build -t trial-randomizer .
docker run -p 8000:8000 trial-randomizer
```
