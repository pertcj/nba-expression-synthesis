import argparse

import sys
from functools import partial
import functools
import time
import csv

import multiprocessing
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Import your solvers here
from nba_expression_synthesis.regex_methods import (
    simplify_state_direct_solver, state_direct_solver, transition_bmc_original_solver,
    simplify_transition_bmc_original_solver, transition_mny_original_solver,
    simplify_transition_bmc_original2_solver, transition_bmc_original2_solver,
    simplify_transition_mny_original_solver, transition_bmc_only_transition_solver,
    simplify_transition_bmc_only_transition_solver, transition_mny_only_transition_solver,
    simplify_transition_mny_only_transition_solver, transition_bmc_only_state_solver,
    simplify_transition_bmc_only_state_solver, transition_mny_only_state_solver,
    simplify_transition_mny_only_state_solver
)

from nba_expression_synthesis.syntax.omega_regex import OmegaRegex

def worker(func, args, return_dict):
    try:
        result = func(*args)
        return_dict['result'] = result
    except Exception as e:
        return_dict['error'] = str(e)

def run_with_timeout(func, args, timeout):
    manager = multiprocessing.Manager()
    return_dict = manager.dict()

    process = multiprocessing.Process(target=worker, args=(func, args, return_dict))
    process.start()
    process.join(timeout)

    if process.is_alive():
        process.terminate()
        process.join()
        logging.warning(f"Function execution of {func.__name__} timed out after {timeout} seconds.")
        return None

    if 'error' in return_dict:
        logging.error(f"Error in {func.__name__}: {return_dict['error']}")
        return None

    return return_dict.get('result', None)

def get_solver(method, nfa_method="bmc", timeouts=(30, 30, 30)):
    match method:
        case "simplify_state_direct":
            # nfa2regex is not applicable; BMC is hardcoded in this path.
            return partial(simplify_state_direct_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), False
        case "state_direct":
            # nfa2regex is not applicable; BMC is hardcoded in this path.
            return partial(state_direct_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), False
        case "transition_selection":
            match nfa_method:
                case "bmc":
                    return partial(transition_bmc_original_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), True
                case "mny":
                    return partial(transition_mny_original_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), True
                case "_":
                    raise ValueError(f"Invalid nfa_method = {nfa_method}")
        case "simplify_transition_selection":
            match nfa_method:
                case "bmc":
                    return partial(simplify_transition_bmc_original_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), True
                case "mny":
                    return partial(simplify_transition_mny_original_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), True
                case "_":
                    raise ValueError(f"Invalid nfa_method = {nfa_method}")
        case "transition_to_state":
            match nfa_method:
                case "bmc":
                    return partial(transition_bmc_only_state_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), True
                case "mny":
                    return partial(transition_mny_only_state_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), True
                case "_":
                    raise ValueError(f"Invalid nfa_method = {nfa_method}")
        case "simplify_transition_to_state":
            match nfa_method:
                case "bmc":
                    return partial(simplify_transition_bmc_only_state_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), True
                case "mny":
                    return partial(simplify_transition_mny_only_state_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), True
                case "_":
                    raise ValueError(f"Invalid nfa_method = {nfa_method}")
        case "transition_only":
            match nfa_method:
                case "bmc":
                    return partial(transition_bmc_only_transition_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), True
                case "mny":
                    return partial(transition_mny_only_transition_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), True
                case "_":
                    raise ValueError(f"Invalid nfa_method = {nfa_method}")
        case "simplify_transition_only":
            match nfa_method:
                case "bmc":
                    return partial(simplify_transition_bmc_only_transition_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), True
                case "mny":
                    return partial(simplify_transition_mny_only_transition_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), True
                case "_":
                    raise ValueError(f"Invalid nfa_method = {nfa_method}")
        case "transition_selection2":
            match nfa_method:
                case "bmc":
                    return partial(transition_bmc_original2_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), False
                case _:
                    raise ValueError(f"Invalid nfa_method = {nfa_method}")
        case "simplify_transition_selection2":
            match nfa_method:
                case "bmc":
                    return partial(simplify_transition_bmc_original2_solver, aut_timeout=timeouts[0], regex_timeout=timeouts[1], simplify_timeout=timeouts[2]), False
                case _:
                    raise ValueError(f"Invalid nfa_method = {nfa_method}")
        
        case _:
            raise ValueError(f"Invalid method = {method}")
        
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

# Helper function to determine if a method supports the nfa2regex flag.
def method_supports_nfa2regex(method: str) -> bool:
    return method in NFA2REGEX_METHODS

def process_metric(metric: str, regex_id: int, regexs: list, i: int, metric_timeout: float) -> tuple:
    begin_time = time.time()
    
    match metric:
        case "length":
            result = run_with_timeout(len, (regexs[regex_id],), metric_timeout)
        case "size":
            result = run_with_timeout(OmegaRegex.size, (regexs[regex_id],), metric_timeout)
        case "starheight":
            result = run_with_timeout(OmegaRegex.star_height, (regexs[regex_id],), metric_timeout)
        case _:
            print("Invalid metric")
            raise ValueError(f"Invalid metric = {metric}")

    if result is None:
        print(f"Processing of formula {i} timed out when determining {metric} after {metric_timeout} seconds.")
        return None, metric_timeout
    
    metric_compute_time = time.time() - begin_time
    return result, metric_compute_time

def update_csv_line(csv_filename: str, formula_index: int, method: str, 
                    nfa_method: str, results: dict):
    
    # Read the entire CSV file
    with open(csv_filename, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)

    # Update the specific row
    for row in rows:
        if int(row['formula_index']) == formula_index:
            for key, value in results.items():
                row[f"{key}"] = value
            break

    # Write the updated data back to the CSV file
    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def process_formula(
    formula: str,
    index: int,
    length: int,
    solver: str,
    nfa2regex: str,
    metrics: list[str],
    output: str,
    timeouts: tuple[float, float, float, float],
):
    aut_timeout, regex_timeout, simplify_timeout, metric_timeout = timeouts
    uses_nfa = method_supports_nfa2regex(solver)

    row = {'formula_index': index, 'formula_length': length}
    solver_fn, _ = get_solver(solver, nfa2regex, (aut_timeout, regex_timeout, simplify_timeout))
    regex_output, timings = solver_fn(formula)

    prefix = f"{solver} {nfa2regex}" if uses_nfa else f"{solver}"

    row[f"{prefix} aut_time"] = timings[0]
    row[f"{prefix} regex_const_time"] = timings[1]
    row[f"{prefix} simplify_time"] = timings[2]

    if regex_output is not None:
        for metric in metrics:
            try:
                result, compute_time = process_metric(metric, 0, [regex_output], index, metric_timeout)
                row[f"{prefix} {metric}"] = result if result is not None else -1
                row[f"{prefix} {metric} time"] = compute_time
            except Exception as e:
                if "bad_alloc()" in str(e):
                    logging.error(f"Memory allocation error in process_metric for {prefix} {metric}: {str(e)}")
                    row[f"{prefix} {metric}"] = -2  # Use -2 to indicate memory error
                    row[f"{prefix} {metric} time"] = -2
                else:
                    logging.error(f"Unexpected error in process_metric for {prefix} {metric}: {str(e)}")
                    row[f"{prefix} {metric}"] = -3  # Use -3 to indicate other errors
                    row[f"{prefix} {metric} time"] = -3
    else:
        for metric in metrics:
            row[f"{prefix} {metric}"] = -1
            row[f"{prefix} {metric} time"] = -1
    if output is not None:
        update_csv_line(output, index, solver, nfa2regex, row)
        print("Processed formula", index, "with solver", solver)
    else:
        print("Processed formula", index, "with solver", solver, "Results:", row)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--formula', type=str, default="G(a -> Fb)", help='LTL formula to convert to regex')
    parser.add_argument('--index', type=int, default=0, help='Index of the formula')
    parser.add_argument('--solver', type=str, default="transition_only", help='Solver method (e.g., state_direct, simplify_state_direct, transition_selection, transition_to_state, transition_only)')
    parser.add_argument('--nfa2regex', type=str, default="bmc", help="Method to convert NFA to regex, choices = bmc (state-elim), mny")
    parser.add_argument('--metrics', nargs='+', default=["length", "size", "starheight"], help='List of metrics to compute')
    parser.add_argument('--output', default=None, type=str, help='Where to save results')
    parser.add_argument('--aut_timeout', type=float, default=120.0, help='Timeout for SPOT to construct the automaton')
    parser.add_argument('--regex_timeout', type=float, default=120.0, help='Timeout for constructing the expression from the automaton')
    parser.add_argument('--simplify_timeout', type=float, default=120.0, help='Timeout for post-processing to simplify the expression')
    parser.add_argument('--metric_timeout', type=float, default=60.0, help='Timeout for determining the metrics')
    
    args = parser.parse_args()

    process_formula(
        formula=args.formula,
        index=args.index,
        length=len(args.formula),
        solver=args.solver,
        nfa2regex=args.nfa2regex,
        metrics=args.metrics,
        output=args.output,
        timeouts=(args.aut_timeout, args.regex_timeout, args.simplify_timeout, args.metric_timeout),
    )

if __name__ == '__main__':
    main()
