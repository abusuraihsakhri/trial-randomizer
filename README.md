# Trial Randomizer

A Python package and command-line interface for experimental treatment allocation, with a browser-based demonstration of the same Python algorithms.

**Use limitation:** This project is intended for algorithm exploration, simulation, and research prototyping. It is **not** a validated clinical trial enrollment system. In particular, it does not provide centralized allocation concealment, role-based authorization, durable signed allocation records, or the operational controls needed for regulated trials.

## Features

- **Permuted block randomization:** configurable treatment arms, allocation ratios, and candidate block sizes.
- **Stratified blocks:** independent permuted-block sequences for each observed combination of stratification factors.
- **Pocock–Simon minimization:** marginal covariate balancing with configurable biased-coin probability and ratio-normalized imbalance scoring.
- **Command-line allocation:** JSON state persistence and CSV records; numbered envelope preparation and balance summaries.
- **Browser demonstration:** uses Pyodide to execute the actual Python allocation classes locally, with an exportable demonstration CSV.
- **Separate FastAPI analytical service:** exposes mock worker evaluations and an in-memory HMAC audit trail; it is not the clinical randomization API.

## Browser demonstration

The static browser interface is in `web/`. GitHub Pages deployment is configured through `.github/workflows/pages.yml`. The site loads Pyodide from jsDelivr; internet access is needed to load the runtime. The demo does not send entered allocation parameters or results to an application backend, and it does not persist them between reloads. Ordinary web/CDN access logs may still be collected by hosting providers.

To preview the browser site locally after installing Python:

```bash
mkdir -p /tmp/trial-randomizer-site/trial_randomizer
cp web/index.html web/app.js /tmp/trial-randomizer-site/
cp trial_randomizer/{__init__,block,minimization,stratified}.py /tmp/trial-randomizer-site/trial_randomizer/
python -m http.server 8001 --directory /tmp/trial-randomizer-site
```

Open `http://localhost:8001`. Do not enter real patient data or use demo allocations for live trial enrollment.

## Installation

Requires Python 3.10 or newer.

```bash
git clone https://github.com/abusuraihsakhri/trial-randomizer.git
cd trial-randomizer
python -m pip install -e ".[dev]"
python -m pytest -q
```

The runtime dependencies are FastAPI, Uvicorn, and Pydantic. The randomization algorithms themselves use only the Python standard library. Pyodide provides those modules in the browser without running FastAPI or a server-side Python process.

## Python API

```python
from trial_randomizer.block import BlockRandomizer
from trial_randomizer.minimization import MinimizationRandomizer
from trial_randomizer.stratified import StratifiedBlockRandomizer

block = BlockRandomizer(["Control", "Treatment"], ratio=[1, 1], block_sizes=[4, 6])
arm, block_id, block_size = block.next()

minimum = MinimizationRandomizer(
    ["Control", "Treatment"], ratio=[1, 1], p_biased_coin=0.8
)
arm, reason, scores = minimum.assign({"site": "North", "age": "over65"})

stratified = StratifiedBlockRandomizer(["Control", "Treatment"], block_sizes=[4])
arm, block_id, block_size, stratum_key = stratified.assign({"site": "North"})
```

For unequal allocation ratios (for example 2:1), block sizes must be positive multiples of the sum of the ratio entries. Minimization scores are normalized by the target ratio.

## CLI examples

Create and continue a permuted-block sequence:

```bash
trial-randomizer block --state trial_state.json --audit allocations.csv \
  --arms Control Treatment --ratio 1 1 --block-sizes 4 6 --n 10

trial-randomizer block --state trial_state.json --audit allocations.csv --n 1
```

Additional commands:

```bash
trial-randomizer minimize --state min_state.json --audit min_allocations.csv \
  --arms Control Treatment --factor site=North age=over65

trial-randomizer stratified --state strat_state.json --audit strat_allocations.csv \
  --arms Control Treatment --stratum site=North

trial-randomizer envelopes --arms Control Treatment --n 100 \
  --labels-out envelopes.txt --master-out master.csv

trial-randomizer balance-report --audit allocations.csv
```

**Protect state and audit files.** The JSON state retains the full pseudorandom generator state and seed, so anyone with access to it can predict allocations. An explicit `--seed` is useful for reproducible simulations but is inappropriate for concealed assignments. New allocation CSV records do not include the seed, but **the CSV is not cryptographically signed or tamper-evident**. The state and audit files are also separate writes, not an atomic transaction. Maintain independent backups and reconciliation controls if adapting the software for any real workflow.

## FastAPI analytical service

The separate agent service uses mock evaluators and does not enroll subjects or implement treatment allocation. Its `/api/*` endpoints require a configured `TRIAL_RANDOMIZER_API_KEY`, supplied in the `x-api-key` header; otherwise operational endpoints return HTTP 503. The HMAC trail in this subsystem uses `AUDIT_SECRET_KEY`, exists in memory only, and is lost on restart. It does not sign the allocation CSV.

For local testing:

```bash
export AUDIT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export TRIAL_RANDOMIZER_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
uvicorn agents.api:app --host 127.0.0.1 --port 8000
```

Endpoints: `GET /health`, `GET /metrics`, `POST /api/audit`, `POST /api/chat`, and `GET /api/audit/logs`. Docker deployment is available with `docker compose up --build` after setting both required environment variables; the Compose port defaults to loopback-only binding.

## Verification, privacy, and compatibility

Run `python -m pytest -q`; GitHub Actions tests Python 3.10–3.12, checks Python source compilation, validates browser JavaScript syntax, and builds a wheel. Modern browsers with WebAssembly and JavaScript support are required for the demo; initial runtime loading needs CDN access.

Treat every subject identifier, covariate, allocation log, state file, and envelope master key as potentially sensitive research data. The regex-based PHI checks in the separate agent subsystem are not a comprehensive de-identification or privacy guarantee.

## License

[MIT](LICENSE).
