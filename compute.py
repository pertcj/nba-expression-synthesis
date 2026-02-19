import argparse
import csv
import logging
import os
import re
import threading
from pathlib import Path
from typing import List

from solve import process_formula

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def initialize_csv(csv_filename: str, ltls: List[str], ltllens: List[int], 
                   methods: List[str], nfa2regex: List[str], metrics: List[str]):
    headers = ['formula_index', 'formula_length'] 
    # + [
    #     f"{method} {nfa_method} {metric}" 
    #     for method in methods 
    #     for nfa_method in (nfa2regex if method_supports_nfa2regex(method) else [''])
    #     for metric in metrics + [f"{metric} time" for metric in metrics]
    # ]
    for method in methods:
        if not method_supports_nfa2regex(method):
            for metric in metrics + [f"{metric} time" for metric in metrics]:
                headers.append(f"{method} {metric}")
            for x in ["aut_time", "regex_const_time", "simplify_time"]:
                headers.append(f"{method} {x}")
        else:
            for nfa_method in nfa2regex:
                for metric in metrics + [f"{metric} time" for metric in metrics]:
                    headers.append(f"{method} {nfa_method} {metric}")
                for x in ["aut_time", "regex_const_time", "simplify_time"]:
                    headers.append(f"{method} {nfa_method} {x}")

    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        for i, ltl_len in enumerate(ltllens):
            writer.writerow({'formula_index': i, 'formula_length': ltl_len})

def compute_metrics(
    input_path: Path,
    output_path: Path,
    methods=["simplify_state_direct", "state_direct", "transition_selection", "simplify_transition_selection", "transition_to_state", "simplify_transition_to_state", "transition_only", "simplify_transition_only"],
    nfa2regex=["bmc", "mny"],
    metrics=["length", "size", "starheight"],
    filter_length=-1,
    timeouts=(120, 120, 120, 60),
):
    
    # Read and filter formulas
    with open(input_path, 'r') as formula_file:
        ltls = []
        for spec in formula_file:
            spec = spec.strip()
            if not spec or spec.startswith('%'):
                continue
            if spec.startswith('LTLSPEC'):
                ltls.append(spec.split(' ', 1)[1].strip())
            else:
                ltls.append(spec)
    
    ltllens = [len(re.findall(r'\b\w+\b|[GFXUR]|[&|(->)!]', ltl)) for ltl in ltls]
    
    if filter_length != -1:
        ltls = [ltl for ltl, length in zip(ltls, ltllens) if length <= filter_length]
        ltllens = [length for length in ltllens if length <= filter_length]

    # Prepare CSV file
    # Initialize CSV file with headers and empty rows
    initialize_csv(str(output_path), ltls, ltllens, methods, nfa2regex, metrics)

    try:

        for i, (ltl, ltl_len) in enumerate(zip(ltls, ltllens)):
            logging.info(f"Processing formula {i} of length {ltl_len}")
            for method in methods:
                uses_nfa = method_supports_nfa2regex(method)
                for nfa_method in (nfa2regex if uses_nfa else [None]):
                    try:
                        process_formula(
                            formula=ltl,
                            index=i,
                            length=ltl_len,
                            solver=method,
                            nfa2regex=nfa_method or "None",
                            metrics=metrics,
                            output=str(output_path),
                            timeouts=timeouts,
                        )
                    except Exception as e:
                        logging.error(f"Unexpected error occurred: {str(e)}")

    except Exception as e:
        logging.error(f"Exception {e} occurred while processing formulas.")

    print(f"Processing complete. Results written to {output_path}")

    for thread in threading.enumerate():
        if thread != threading.current_thread():
            thread.join(0.1)  # Give each thread 0.1 seconds to finish
    print("All threads terminated.")


# Helper function to determine if a method uses NFA
NFA2REGEX_METHODS = {
    "transition_selection",
    "simplify_transition_selection",
    "transition_to_state",
    "simplify_transition_to_state",
    "transition_only",
    "simplify_transition_only",
    "transition_selection2",
    "simplify_transition_selection2",
}

# Helper function to determine if a method supports the nfa2regex flag. If a method does not support nfa2regex, it uses bmc.
def method_supports_nfa2regex(method: str) -> bool:
    return method in NFA2REGEX_METHODS


def main():
    repo_root = Path(__file__).resolve().parent
    default_input = repo_root / "formulas" / "merged.ltl"
    default_output = repo_root / "metrics.csv"

    parser = argparse.ArgumentParser(description='Compute metrics for LTL formulas.')
    parser.add_argument('--input', default=str(default_input), help='Path to .ltl file')
    parser.add_argument('--output', default=str(default_output), help='Output CSV file')
    parser.add_argument('--methods', nargs='+', default=["simplify_state_direct", "state_direct", "transition_selection", "simplify_transition_selection", "transition_to_state", "simplify_transition_to_state", "transition_only", "simplify_transition_only"],
                         help='List of methods to determine metrics')
    parser.add_argument('--nfa2regex', nargs='+', default=["bmc", "mny"], help="Method to convert NFA to regex, choices = bmc (state-elim), mny")
    parser.add_argument('--metrics', nargs='+', default=["length", "size", "starheight"], help='List of metrics to compute')
    parser.add_argument('--filter_length', type=int, default=-1, help='Filter length for LTL formulas')
    parser.add_argument('--aut_timeout', type=float, default=120.0, help='Timeout for SPOT to construct the automaton')
    parser.add_argument('--regex_timeout', type=float, default=120.0, help='Timeout for constructing the expression from the automaton')
    parser.add_argument('--simplify_timeout', type=float, default=120.0, help='Timeout for post-processing to simplify the expression')
    parser.add_argument('--metric_timeout', type=float, default=60.0, help='Timeout for computing a metric')
    parser.add_argument('--recursion_limit', type=int, default=10000, help='Recursion limit for Python')

    args = parser.parse_args()
    os.environ['PYTHONHASHSEED'] = '0'
    import sys
    sys.setrecursionlimit(args.recursion_limit)

    print("Beginning data collection script...")
    compute_metrics(
        input_path=Path(args.input),
        output_path=Path(args.output),
        methods=args.methods,
        nfa2regex=args.nfa2regex,
        metrics=args.metrics,
        filter_length=args.filter_length,
        timeouts=(args.aut_timeout, args.regex_timeout, args.simplify_timeout, args.metric_timeout),
    )
    print("Data collection script completed.")
    exit(0)


if __name__ == '__main__':
    main()
