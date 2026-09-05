"""Audit log storage and the balance-check report.

Every allocation decision made by any of the three methods is appended as
one row to a CSV file, so the full history of who got what, when, and why
can be reconstructed later for a trial's audit trail. Complex fields
(stratum covariates, per-arm imbalance scores) are stored as JSON text
inside their cell.
"""

import csv
import json
import os
from collections import Counter, defaultdict

FIELDS = [
    "seq",
    "timestamp",
    "method",
    "subject_id",
    "arm",
    "stratum",
    "block_id",
    "block_size",
    "scores",
    "reason",
    "seed",
]

_JSON_FIELDS = ("stratum", "scores")


def append_rows(path, rows):
    """Append allocation records to a CSV audit log, writing the header
    first if the file does not already exist."""
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        for r in rows:
            row = dict(r)
            for key in _JSON_FIELDS:
                value = row.get(key)
                if isinstance(value, (dict, list, tuple)):
                    row[key] = json.dumps(value, sort_keys=True, default=str)
            writer.writerow(row)


def read_rows(path):
    """Read an audit log CSV back into a list of dicts, decoding the JSON
    fields."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audit log not found: {path}")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in _JSON_FIELDS:
            value = row.get(key)
            if value:
                try:
                    row[key] = json.loads(value)
                except json.JSONDecodeError:
                    pass
    return rows


def balance_counts(rows):
    """Tally arm counts overall and per stratum from a list of audit
    records."""
    overall = Counter()
    per_stratum = defaultdict(Counter)
    for r in rows:
        arm = r.get("arm")
        if not arm:
            continue
        overall[arm] += 1
        stratum = r.get("stratum")
        if stratum:
            key = (
                json.dumps(stratum, sort_keys=True)
                if not isinstance(stratum, str)
                else stratum
            )
            if key and key != "{}":
                per_stratum[key][arm] += 1
    return overall, per_stratum


def format_balance_report(rows):
    """Build a human-readable balance-check report string."""
    overall, per_stratum = balance_counts(rows)
    arms = sorted(overall.keys())
    lines = ["=== Balance-check report ===", f"Total allocations: {sum(overall.values())}", ""]

    lines.append("Overall arm balance:")
    total = sum(overall.values())
    for arm in arms:
        c = overall[arm]
        pct = 100 * c / total if total else 0.0
        lines.append(f"  {arm:>12}: {c:5d}  ({pct:5.1f}%)")
    if arms:
        counts = [overall[a] for a in arms]
        lines.append(f"  max-min imbalance: {max(counts) - min(counts)}")

    if per_stratum:
        lines.append("")
        lines.append("Per-stratum arm balance:")
        for key in sorted(per_stratum.keys()):
            c = per_stratum[key]
            stotal = sum(c.values())
            lines.append(f"  stratum {key}:")
            for arm in arms:
                n = c.get(arm, 0)
                pct = 100 * n / stotal if stotal else 0.0
                lines.append(f"    {arm:>12}: {n:5d}  ({pct:5.1f}%)")
            counts = [c.get(a, 0) for a in arms]
            lines.append(f"    max-min imbalance: {max(counts) - min(counts)}")

    return "\n".join(lines)
