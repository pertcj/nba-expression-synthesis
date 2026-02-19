#!/usr/bin/env python3
"""
Backfill missing state_direct automaton stats in an existing counts CSV, using formulas from a .ltl file.

Backfill condition (per row i / formula_index):
  - counts CSV: state_direct fields are missing
  - counts CSV: BOTH transition and transition_to_state are present (not missing)
  - metrics CSV: "state_direct aut_time" is NOT 120 (120 means it timed out -> skip)

Notes:
  - Robust to formula_index dtype mismatches (string/int) across files.
  - Treats "", whitespace, "NA", "nan", "None", "null" as missing in counts CSV.
  - Writes updates incrementally (every --flush_every rows updated) to avoid progress loss.
"""

import argparse
import csv
import logging
import multiprocessing
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import spot

from nba_expression_synthesis.synthesis.transition_graph_pipeline import aut_to_tgraph

spot.setup()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TIMEOUT_MARKER = 120.0


# -----------------------------
# Timeout wrapper
# -----------------------------
def _worker(func, args, return_dict):
    try:
        return_dict["result"] = func(*args)
    except Exception as e:
        return_dict["error"] = str(e)


def run_with_timeout(func, args, timeout: float):
    manager = multiprocessing.Manager()
    return_dict = manager.dict()

    process = multiprocessing.Process(target=_worker, args=(func, args, return_dict))
    process.start()
    process.join(timeout)

    if process.is_alive():
        process.terminate()
        process.join()
        logging.warning(f"Function execution of {func.__name__} timed out after {timeout} seconds.")
        return None

    if "error" in return_dict:
        logging.error(f"Error in {func.__name__}: {return_dict['error']}")
        return None

    return return_dict.get("result", None)


# -----------------------------
# LTL loading + length
# -----------------------------
_TOKEN_RE = re.compile(r"\b\w+\b|[GFXUR]|[&|(->)!]")


def load_formulas(input_path: Path, filter_length: int = -1) -> Tuple[List[str], List[int]]:
    ltls: List[str] = []
    for line in input_path.read_text().splitlines():
        spec = line.strip()
        if not spec or spec.startswith("%"):
            continue
        if spec.startswith("LTLSPEC"):
            ltls.append(spec.split(" ", 1)[1].strip())
        else:
            ltls.append(spec)

    ltllens = [len(_TOKEN_RE.findall(ltl)) for ltl in ltls]

    if filter_length != -1:
        filtered = [(ltl, ln) for (ltl, ln) in zip(ltls, ltllens) if ln <= filter_length]
        ltls = [x[0] for x in filtered]
        ltllens = [x[1] for x in filtered]

    return ltls, ltllens


# -----------------------------
# CSV helpers (robust missing + indexing)
# -----------------------------
_MISSING_TOKENS = {"", "na", "n/a", "nan", "none", "null", "nil", "<na>"}


def is_missing(v: Optional[str]) -> bool:
    if v is None:
        return True
    s = str(v).strip()
    if s == "":
        return True
    return s.lower() in _MISSING_TOKENS


def to_int(v: Optional[str], default: Optional[int] = None) -> Optional[int]:
    if is_missing(v):
        return default
    try:
        return int(float(str(v).strip()))
    except Exception:
        return default


def to_float(v: Optional[str]) -> Optional[float]:
    if is_missing(v):
        return None
    try:
        return float(str(v).strip())
    except Exception:
        return None


def method_columns(method: str) -> List[str]:
    return [
        f"{method} states",
        f"{method} accepting_states",
        f"{method} transitions",
        f"{method} deterministic",
    ]


def read_csv_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return rows, fieldnames


def write_csv_rows(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def ensure_counts_schema(
    counts_csv: Path,
    ltllens: List[int],
    methods: List[str],
) -> Tuple[List[Dict[str, str]], List[str], Dict[int, int]]:
    """
    Returns:
      rows, fieldnames, index_to_rowpos

    index_to_rowpos maps formula_index -> row position in rows.
    """
    base_cols = ["formula_index", "formula_length"]
    required_cols = base_cols[:]
    for m in methods:
        required_cols.extend(method_columns(m))

    if counts_csv.exists():
        rows, fieldnames = read_csv_rows(counts_csv)
        merged = list(fieldnames)
        for c in required_cols:
            if c not in merged:
                merged.append(c)

        # normalize rows to have all columns
        for r in rows:
            for c in merged:
                r.setdefault(c, "")

        # build mapping formula_index -> rowpos (prefer explicit formula_index; fallback rowpos)
        index_to_rowpos: Dict[int, int] = {}
        for pos, r in enumerate(rows):
            idx = to_int(r.get("formula_index"), default=pos)
            r["formula_index"] = str(idx)
            # fill formula_length if empty and we have it from ltl list
            if is_missing(r.get("formula_length")) and idx is not None and 0 <= idx < len(ltllens):
                r["formula_length"] = str(ltllens[idx])
            index_to_rowpos[idx] = pos

        # extend to cover all formulas
        for idx in range(len(ltllens)):
            if idx not in index_to_rowpos:
                new_row = {c: "" for c in merged}
                new_row["formula_index"] = str(idx)
                new_row["formula_length"] = str(ltllens[idx])
                rows.append(new_row)
                index_to_rowpos[idx] = len(rows) - 1

        return rows, merged, index_to_rowpos

    # create new
    fieldnames = required_cols
    rows = []
    index_to_rowpos: Dict[int, int] = {}
    for idx, ln in enumerate(ltllens):
        r = {c: "" for c in fieldnames}
        r["formula_index"] = str(idx)
        r["formula_length"] = str(ln)
        rows.append(r)
        index_to_rowpos[idx] = idx
    return rows, fieldnames, index_to_rowpos


def load_metrics_timeout_set(metrics_csv: Path, col: str = "state_direct aut_time", col2: str = "state_direct regex_const_time") -> set[int]:
    """
    Returns set of formula_index values that should be skipped because metrics says timed out (aut_time == 120).
    Robust to missing/blank indices by falling back to row position.
    """
    rows, _ = read_csv_rows(metrics_csv)
    timeout_idxs: set[int] = set()
    for pos, r in enumerate(rows):
        idx = to_int(r.get("formula_index"), default=pos)
        t = to_float(r.get(col))
        t2 = to_float(r.get(col2))
        if (t is not None and t == TIMEOUT_MARKER) or (t2 is not None and t2 == TIMEOUT_MARKER):
            timeout_idxs.add(idx)
    return timeout_idxs


# -----------------------------
# Spot counting
# -----------------------------
def count_states_worker(ltl: str, method: str):
    match method:
        case "transition":
            aut = spot.translate(ltl, "buchi")
        case "state_direct":
            aut = spot.translate(ltl, "buchi", "sbacc")
        case "state_from_transition":
            transition_aut = spot.translate(ltl, "buchi")
            aut = spot.degeneralize(transition_aut)
            aut.copy_state_names_from(transition_aut)
        case _:
            raise ValueError(f"Invalid method {method}")

    tgraph = aut_to_tgraph(aut)
    num_states = len(tgraph.vertices)
    num_accepting_states = len(tgraph.final_states)
    num_transitions = len(tgraph.nonacc_trans) + len(tgraph.acc_trans)
    deterministic = aut.is_deterministic()
    return num_states, num_accepting_states, num_transitions, deterministic


# -----------------------------
# Backfill logic
# -----------------------------
def backfill_state_direct(
    input_path: Path,
    counts_csv_path: Path,
    metrics_csv_path: Path,
    filter_length: int = -1,
    timeout: float = 120.0,
    flush_every: int = 25,
) -> None:
    ltls, ltllens = load_formulas(input_path, filter_length=filter_length)

    skip_idxs = load_metrics_timeout_set(metrics_csv_path, col="state_direct aut_time")

    methods = ["transition", "state_from_transition", "state_direct"]
    rows, fieldnames, idx_to_pos = ensure_counts_schema(counts_csv_path, ltllens, methods)

    # columns we care about
    sd_cols = method_columns("state_direct")
    tr_cols = method_columns("transition")
    tts_cols = method_columns("state_from_transition")

    updated = 0
    considered = 0
    skipped_metrics = 0
    skipped_prereq = 0

    for idx in range(len(ltls)):
        pos = idx_to_pos.get(idx)
        if pos is None:
            continue
        row = rows[pos]

        # metrics says SD timed out earlier -> skip
        if idx in skip_idxs:
            skipped_metrics += 1
            continue

        # must have BOTH other methods present (states field is the primary gate)
        # (matches your requirement: "there is not a missing entry in either of the other two methods")
        if is_missing(row.get("transition states")) and is_missing(row.get("state_from_transition states")):
            skipped_prereq += 1
            continue

        # state_direct must be missing (states is the primary gate)
        # If you want stricter: require ALL sd fields missing; current uses "states" missing as trigger.
        if not is_missing(row.get("state_direct states")):
            continue

        considered += 1
        ltl = ltls[idx]
        logging.info(f"Backfilling state_direct for formula_index={idx} (len={ltllens[idx]})")

        result = run_with_timeout(count_states_worker, (ltl, "state_direct"), timeout)
        if result is None:
            # do not write metrics here; only skip runtime failures
            continue

        num_states, num_accepting_states, num_transitions, deterministic = result
        row["state_direct states"] = str(num_states)
        row["state_direct accepting_states"] = str(num_accepting_states)
        row["state_direct transitions"] = str(num_transitions)
        row["state_direct deterministic"] = str(deterministic)

        updated += 1
        if flush_every > 0 and updated % flush_every == 0:
            write_csv_rows(counts_csv_path, rows, fieldnames)

    write_csv_rows(counts_csv_path, rows, fieldnames)
    logging.info(
        f"Backfill complete. considered={considered} updated={updated} "
        f"skipped_metrics_timeout={skipped_metrics} skipped_missing_prereq={skipped_prereq}"
    )
    print(f"Updated {updated} rows in {counts_csv_path}")


def main():
    repo_root = Path(__file__).resolve().parents[1]
    default_input = repo_root / "formulas" / "merged.ltl"
    default_counts = repo_root / "ltl_state_counts.csv"
    default_metrics = repo_root / "ltl_metrics.csv"

    ap = argparse.ArgumentParser(description="Backfill missing state_direct stats in an existing counts CSV.")
    ap.add_argument("--input", default=str(default_input), help="Path to .ltl file")
    ap.add_argument("--counts", default=str(default_counts), help="Counts CSV file to read/update")
    ap.add_argument("--metrics", default=str(default_metrics), help='Metrics CSV (skip if "state_direct aut_time"==120)')
    ap.add_argument("--filter_length", type=int, default=-1, help="Filter length for LTL formulas")
    ap.add_argument("--aut_timeout", type=float, default=120.0, help="Timeout for Spot to construct the automaton")
    ap.add_argument("--flush_every", type=int, default=25, help="Write CSV every N successful updates (0 disables)")

    args = ap.parse_args()

    backfill_state_direct(
        input_path=Path(args.input),
        counts_csv_path=Path(args.counts),
        metrics_csv_path=Path(args.metrics),
        filter_length=args.filter_length,
        timeout=args.aut_timeout,
        flush_every=args.flush_every,
    )


if __name__ == "__main__":
    main()
