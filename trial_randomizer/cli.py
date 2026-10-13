"""Command-line interface for Trial Randomizer.

Subcommands:
  block           permuted block randomization, one call per subject
  minimize        Pocock-Simon covariate minimization, one call per subject
  stratified      stratified block randomization, one call per subject
  envelopes       pre-generate a numbered, concealment-friendly envelope list
  balance-report  balance-check report from one or more audit logs

`block`, `minimize` and `stratified` are stateful across invocations: the
first call (which must supply --arms) creates a JSON state file; every
later call reuses it, so subjects can be enrolled one at a time, on
different days, and the sequence (and its RNG) picks up exactly where it
left off.
"""

import argparse
import os
import random
import sys
from datetime import datetime

from . import audit
from .block import BlockRandomizer
from .minimization import MinimizationRandomizer
from .stratified import StratifiedBlockRandomizer
from .state import load_state, save_state, rng_state_to_json, rng_state_from_json


def parse_kv_strings(items):
    result = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"error: expected NAME=VALUE, got '{item}'")
        k, v = item.split("=", 1)
        result[k] = v
    return result


def parse_kv_floats(items):
    result = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"error: expected NAME=WEIGHT, got '{item}'")
        k, v = item.split("=", 1)
        try:
            result[k] = float(v)
        except ValueError:
            raise SystemExit(f"error: weight for '{k}' must be numeric, got '{v}'")
    return result


def _new_seed(explicit_seed):
    if explicit_seed is not None:
        return explicit_seed
    return random.SystemRandom().getrandbits(128)


def _rng_from_state(state):
    rng = random.Random()
    rng.setstate(rng_state_from_json(state["rng_state"]))
    return rng


def _check_method(state, method):
    if state.get("method") != method:
        raise ValueError(f"State file belongs to {state.get('method')!r}, not {method!r}")


def _now():
    return datetime.now().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# block
# --------------------------------------------------------------------------

def cmd_block(args):
    if args.n < 1:
        raise SystemExit("error: --n must be a positive integer")
    state = load_state(args.state)
    if state is None:
        if not args.arms:
            raise SystemExit("error: --arms is required to initialize a new --state file")
        ratio = args.ratio or [1] * len(args.arms)
        block_sizes = args.block_sizes or [sum(ratio) * 2]
        seed = _new_seed(args.seed)
        rng = random.Random(seed)
        try:
            BlockRandomizer(args.arms, ratio, block_sizes, rng)  # validates
        except ValueError as e:
            raise SystemExit(f"error: {e}")
        state = {
            "method": "block",
            "arms": args.arms,
            "ratio": ratio,
            "block_sizes": block_sizes,
            "seed": seed,
            "rng_state": rng_state_to_json(rng.getstate()),
            "queue": [],
            "block_id": 0,
            "block_size_current": None,
            "seq": 0,
        }
        print(f"[init] arms={args.arms} ratio={ratio} block_sizes={block_sizes}")
    else:
        _check_method(state, "block")
        rng = _rng_from_state(state)

    br = BlockRandomizer(state["arms"], state["ratio"], state["block_sizes"], rng)
    br._queue = list(state["queue"])
    br._block_id = state["block_id"]
    br._block_size_current = state["block_size_current"]

    subject_ids = args.subject_ids if args.subject_ids else [None] * args.n
    if len(subject_ids) != args.n:
        raise SystemExit("error: number of --subject-ids must equal --n")

    rows = []
    for sid in subject_ids:
        arm, block_id, block_size = br.next()
        state["seq"] += 1
        rows.append({
            "seq": state["seq"],
            "timestamp": _now(),
            "method": "permuted_block",
            "subject_id": sid or "",
            "arm": arm,
            "block_id": block_id,
            "block_size": block_size,
        })
        print(f"seq {state['seq']}: subject={sid or '(unlabeled)'} -> arm {arm}")

    state["queue"] = br._queue
    state["block_id"] = br._block_id
    state["block_size_current"] = br._block_size_current
    state["rng_state"] = rng_state_to_json(rng.getstate())
    save_state(args.state, state)
    audit.append_rows(args.audit, rows)


# --------------------------------------------------------------------------
# minimize
# --------------------------------------------------------------------------

def cmd_minimize(args):
    state = load_state(args.state)
    if state is None:
        if not args.arms:
            raise SystemExit("error: --arms is required to initialize a new --state file")
        ratio = args.ratio or [1] * len(args.arms)
        factor_weights = parse_kv_floats(args.factor_weight) if args.factor_weight else {}
        seed = _new_seed(args.seed)
        rng = random.Random(seed)
        try:
            MinimizationRandomizer(args.arms, ratio, factor_weights, args.p, rng)  # validates
        except ValueError as e:
            raise SystemExit(f"error: {e}")
        state = {
            "method": "minimize",
            "arms": args.arms,
            "ratio": ratio,
            "factor_weights": factor_weights,
            "p": args.p,
            "include_overall": not args.no_overall,
            "overall_weight": args.overall_weight,
            "seed": seed,
            "rng_state": rng_state_to_json(rng.getstate()),
            "counts": {},
            "totals": {a: 0 for a in args.arms},
            "seq": 0,
        }
        print(
            f"[init] arms={args.arms} ratio={ratio} "
            f"factor_weights={factor_weights} p={args.p}"
        )
    else:
        _check_method(state, "minimize")
        rng = _rng_from_state(state)

    mr = MinimizationRandomizer(
        state["arms"],
        state["ratio"],
        state["factor_weights"],
        state["p"],
        rng,
        state["include_overall"],
        state["overall_weight"],
    )
    mr.counts = state["counts"]
    mr.totals = state["totals"]

    covariates = parse_kv_strings(args.factor) if args.factor else {}
    arm, reason, scores = mr.assign(covariates)

    state["seq"] += 1
    row = {
        "seq": state["seq"],
        "timestamp": _now(),
        "method": "minimization",
        "subject_id": args.subject_id or "",
        "arm": arm,
        "stratum": covariates,
        "scores": scores,
        "reason": reason,
    }
    state["counts"] = mr.counts
    state["totals"] = mr.totals
    state["rng_state"] = rng_state_to_json(rng.getstate())
    save_state(args.state, state)
    audit.append_rows(args.audit, [row])

    print(f"seq {state['seq']}: subject={args.subject_id or '(unlabeled)'} "
          f"covariates={covariates} -> arm {arm} ({reason})")
    print(f"  imbalance scores if assigned to each arm: {scores}")


# --------------------------------------------------------------------------
# stratified
# --------------------------------------------------------------------------

def cmd_stratified(args):
    state = load_state(args.state)
    if state is None:
        if not args.arms:
            raise SystemExit("error: --arms is required to initialize a new --state file")
        ratio = args.ratio or [1] * len(args.arms)
        block_sizes = args.block_sizes or [sum(ratio) * 2]
        seed = _new_seed(args.seed)
        rng = random.Random(seed)
        try:
            BlockRandomizer(args.arms, ratio, block_sizes, rng)  # validates
        except ValueError as e:
            raise SystemExit(f"error: {e}")
        state = {
            "method": "stratified",
            "arms": args.arms,
            "ratio": ratio,
            "block_sizes": block_sizes,
            "seed": seed,
            "rng_state": rng_state_to_json(rng.getstate()),
            "strata": {},
            "seq": 0,
        }
        print(f"[init] arms={args.arms} ratio={ratio} block_sizes={block_sizes}")
    else:
        _check_method(state, "stratified")
        rng = _rng_from_state(state)

    sbr = StratifiedBlockRandomizer(state["arms"], state["ratio"], state["block_sizes"], rng)
    for key_str, sub in state["strata"].items():
        br = BlockRandomizer(state["arms"], state["ratio"], state["block_sizes"], rng)
        br._queue = list(sub["queue"])
        br._block_id = sub["block_id"]
        br._block_size_current = sub["block_size_current"]
        sbr._strata[tuple(tuple(pair) for pair in sub["stratum_items"])] = br

    covariates = parse_kv_strings(args.stratum) if args.stratum else {}
    arm, block_id, block_size, stratum_key = sbr.assign(covariates)

    state["seq"] += 1
    row = {
        "seq": state["seq"],
        "timestamp": _now(),
        "method": "stratified_block",
        "subject_id": args.subject_id or "",
        "arm": arm,
        "stratum": covariates,
        "block_id": block_id,
        "block_size": block_size,
    }

    state["strata"] = {}
    for key, br in sbr._strata.items():
        key_str = "|".join(f"{k}={v}" for k, v in key) or "(none)"
        state["strata"][key_str] = {
            "stratum_items": [list(pair) for pair in key],
            "queue": br._queue,
            "block_id": br._block_id,
            "block_size_current": br._block_size_current,
        }
    state["rng_state"] = rng_state_to_json(rng.getstate())
    save_state(args.state, state)
    audit.append_rows(args.audit, [row])

    print(f"seq {state['seq']}: subject={args.subject_id or '(unlabeled)'} "
          f"stratum={covariates} -> arm {arm} (block {block_id}, size {block_size})")


# --------------------------------------------------------------------------
# envelopes
# --------------------------------------------------------------------------

def cmd_envelopes(args):
    import csv as csv_mod

    ratio = args.ratio or [1] * len(args.arms)
    block_sizes = args.block_sizes or [sum(ratio) * 2]
    seed = _new_seed(args.seed)
    rng = random.Random(seed)

    rows = []
    labels = []
    envelope_no = 0

    if args.strata_file:
        strata_path = _validate_path(args.strata_file)
        with open(strata_path, newline="", encoding="utf-8") as f:
            strata_rows = list(csv_mod.DictReader(f))
        if not strata_rows:
            raise SystemExit("error: --strata-file has no data rows")
        for srow in strata_rows:
            if "n" not in srow:
                raise SystemExit("error: --strata-file must have an 'n' column")
            n = int(srow["n"])
            covars = {k: v for k, v in srow.items() if k != "n"}
            try:
                br = BlockRandomizer(args.arms, ratio, block_sizes, rng)
            except ValueError as e:
                raise SystemExit(f"error: {e}")
            for _ in range(n):
                envelope_no += 1
                arm, block_id, block_size = br.next()
                rows.append({
                    "seq": envelope_no,
                    "timestamp": _now(),
                    "method": "permuted_block_envelope",
                    "subject_id": "",
                    "arm": arm,
                    "stratum": covars,
                    "block_id": block_id,
                    "block_size": block_size,
                })
                tag = "/".join(covars.values())
                labels.append(f"Envelope {envelope_no:04d}  [{tag}]" if tag else f"Envelope {envelope_no:04d}")
    else:
        if not args.n:
            raise SystemExit("error: --n is required when --strata-file is not given")
        try:
            br = BlockRandomizer(args.arms, ratio, block_sizes, rng)
        except ValueError as e:
            raise SystemExit(f"error: {e}")
        for _ in range(args.n):
            envelope_no += 1
            arm, block_id, block_size = br.next()
            rows.append({
                "seq": envelope_no,
                "timestamp": _now(),
                "method": "permuted_block_envelope",
                "subject_id": "",
                "arm": arm,
                "block_id": block_id,
                "block_size": block_size,
            })
            labels.append(f"Envelope {envelope_no:04d}")

    labels_out_path = _validate_path(args.labels_out)
    master_out_path = _validate_path(args.master_out)
    with open(labels_out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(labels) + "\n")
    audit.append_rows(master_out_path, rows)

    print(f"Generated {envelope_no} envelopes.")
    print(f"  Blinded envelope labels (safe to print/seal) -> {args.labels_out}")
    print(f"  Master allocation key (KEEP CONFIDENTIAL)     -> {args.master_out}")


# --------------------------------------------------------------------------
# balance-report
# --------------------------------------------------------------------------

def cmd_balance_report(args):
    rows = []
    for path in args.audit:
        rows.extend(audit.read_rows(_validate_path(path)))
    text = audit.format_balance_report(rows)
    print(text)
    if args.output:
        output_path = _validate_path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text + "\n")


# --------------------------------------------------------------------------
# argument parser
# --------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="trial_randomizer",
        description="Treatment allocation for clinical trials: permuted block "
                    "randomization, Pocock-Simon minimization, and stratified "
                    "block randomization, with an audit-ready allocation log.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # block
    sp = sub.add_parser("block", help="permuted block randomization (one call per subject/batch)")
    sp.add_argument("--state", required=True, help="path to the JSON state file (created on first use)")
    sp.add_argument("--audit", required=True, help="path to the audit log CSV (appended)")
    sp.add_argument("--arms", nargs="+", help="arm names, e.g. --arms A B (required to initialize)")
    sp.add_argument("--ratio", nargs="+", type=int, help="allocation ratio, one int per arm, e.g. 1 1")
    sp.add_argument("--block-sizes", nargs="+", type=int, help="candidate block sizes (multiples of sum(ratio))")
    sp.add_argument("--seed", type=int, help="RNG seed (random if omitted; printed so it can be recorded)")
    sp.add_argument("--n", type=int, default=1, help="number of subjects to allocate now (default 1)")
    sp.add_argument("--subject-ids", nargs="+", help="optional subject id per allocation")
    sp.set_defaults(func=cmd_block)

    # minimize
    sp = sub.add_parser("minimize", help="Pocock-Simon minimization (one call per subject)")
    sp.add_argument("--state", required=True)
    sp.add_argument("--audit", required=True)
    sp.add_argument("--arms", nargs="+")
    sp.add_argument("--ratio", nargs="+", type=int)
    sp.add_argument("--factor-weight", nargs="+", metavar="NAME=WEIGHT",
                     help="stratification factor weight, e.g. --factor-weight site=1 age_group=1")
    sp.add_argument("--p", type=float, default=0.8, help="biased-coin probability for the minimizing arm (default 0.8)")
    sp.add_argument("--overall-weight", type=float, default=1.0, help="weight for overall marginal balance (default 1.0)")
    sp.add_argument("--no-overall", action="store_true", help="exclude overall marginal balance from the score")
    sp.add_argument("--seed", type=int)
    sp.add_argument("--subject-id", help="subject identifier for the audit log")
    sp.add_argument("--factor", nargs="+", metavar="NAME=LEVEL",
                     help="this subject's covariate levels, e.g. --factor site=SiteA age_group=over65")
    sp.set_defaults(func=cmd_minimize)

    # stratified
    sp = sub.add_parser("stratified", help="stratified block randomization (one call per subject)")
    sp.add_argument("--state", required=True)
    sp.add_argument("--audit", required=True)
    sp.add_argument("--arms", nargs="+")
    sp.add_argument("--ratio", nargs="+", type=int)
    sp.add_argument("--block-sizes", nargs="+", type=int)
    sp.add_argument("--seed", type=int)
    sp.add_argument("--subject-id")
    sp.add_argument("--stratum", nargs="+", metavar="NAME=LEVEL",
                     help="this subject's stratum, e.g. --stratum site=SiteA")
    sp.set_defaults(func=cmd_stratified)

    # envelopes
    sp = sub.add_parser("envelopes", help="pre-generate a numbered, concealment-friendly envelope list")
    sp.add_argument("--arms", nargs="+", required=True)
    sp.add_argument("--ratio", nargs="+", type=int)
    sp.add_argument("--block-sizes", nargs="+", type=int)
    sp.add_argument("--seed", type=int)
    sp.add_argument("--n", type=int, help="total number of envelopes (ignored if --strata-file is given)")
    sp.add_argument("--strata-file", help="CSV with stratum columns plus an 'n' column giving envelopes per stratum")
    sp.add_argument("--labels-out", required=True, help="output path for the blinded, printable envelope list")
    sp.add_argument("--master-out", required=True, help="output path for the confidential master allocation key")
    sp.set_defaults(func=cmd_envelopes)

    # balance-report
    sp = sub.add_parser("balance-report", help="balance-check report from one or more audit logs")
    sp.add_argument("--audit", nargs="+", required=True, help="audit log CSV file(s)")
    sp.add_argument("--output", help="optional path to also save the report as text")
    sp.set_defaults(func=cmd_balance_report)

    return p


def _validate_path(path):
    """Validate that a path does not contain directory traversal attempts."""
    normalized = os.path.normpath(path)
    if ".." in str(path).replace("\\", "/").split("/"):
        raise ValueError(f"Path contains directory traversal: {path}")
    return normalized


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except SystemExit:
        raise
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
