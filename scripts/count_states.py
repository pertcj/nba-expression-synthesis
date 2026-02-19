import argparse
import csv
import logging
import multiprocessing
import re
from pathlib import Path
from typing import List

import spot

from nba_expression_synthesis.synthesis.transition_graph_pipeline import aut_to_tgraph

spot.setup()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

def initialize_csv(csv_filename: str, ltllens: List[int]):
    headers = ['formula_index', 'formula_length'] 

    for method in ["transition", "state_direct", "transition_to_state"]:
        headers.append(f"{method} states")
        headers.append(f"{method} accepting_states")
        headers.append(f"{method} transitions")
        headers.append(f"{method} deterministic")

    with open(csv_filename, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        for i, ltl_len in enumerate(ltllens):
            writer.writerow({'formula_index': i, 'formula_length': ltl_len})

def update_csv_line(csv_filename: str, formula_index: int, results: dict):
    
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

def count_states_worker(ltl: str, method: str):
    aut = None
    match method:
        case "transition":
            aut = spot.translate(ltl, 'buchi')
        case "state_direct":
            aut = spot.translate(ltl, 'buchi', 'sbacc')
        case "transition_to_state":
            transition_aut = spot.translate(ltl, 'buchi')
            aut = spot.degeneralize(transition_aut)
            aut.copy_state_names_from(transition_aut)
        case _:
            raise ValueError(f"Invalid method {method}")
    tgraph = aut_to_tgraph(aut)
    num_states = len(tgraph.vertices)
    num_accepting_states = len(tgraph.final_states)
    num_transitions = len(tgraph.nonacc_trans) + len(tgraph.acc_trans)
    deterministic = aut.is_deterministic()
    return (num_states, num_accepting_states, num_transitions, deterministic)


def count_states(input_path: Path, output_path: Path, filter_length=-1, timeout=120):
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
    initialize_csv(str(output_path), ltllens)

    try:
        for i, (ltl, ltl_len) in enumerate(zip(ltls, ltllens)):
            logging.info(f"Processing formula {i} of length {ltl_len}")
            for method in ["transition", "state_direct", "transition_to_state"]:
                try:
                    result = run_with_timeout(count_states_worker, (ltl, method), timeout)
                    if result is None:
                        logging.warning(f"Timeout or error occurred for formula {i} with method {method}")
                        continue
                    num_states, num_accepting_states, num_transitions, deterministic = result
                    update_csv_line(
                        str(output_path),
                        i,
                        {
                            f"{method} states": num_states,
                            f"{method} accepting_states": num_accepting_states,
                            f"{method} transitions": num_transitions,
                            f"{method} deterministic": deterministic,
                        },
                    )
                except Exception as e:
                    logging.error(f"Exception {e} occurred while processing formula {i} with method {method}")
    except Exception as e:
        logging.error(f"Exception {e} occurred while processing formulas.")

    print(f"Processing complete. Results written to {output_path}")

def main():
    repo_root = Path(__file__).resolve().parents[1]
    default_input = repo_root / "formulas" / "merged.ltl"
    default_output = repo_root / "ltl_state_counts.csv"

    parser = argparse.ArgumentParser(description='Compute automaton information for LTL formulas.')
    parser.add_argument('--input', default=str(default_input), help='Path to .ltl file')
    parser.add_argument('--output', default=str(default_output), help='Output CSV file')
    parser.add_argument('--filter_length', type=int, default=-1, help='Filter length for LTL formulas')
    parser.add_argument('--aut_timeout', type=float, default=120.0, help='Timeout for Spot to construct the automaton')
    
    args = parser.parse_args()
    print("Beginning data collection script...")

    count_states(
        input_path=Path(args.input),
        output_path=Path(args.output),
        filter_length=args.filter_length,
        timeout=args.aut_timeout,
    )
    print("Data collection script completed.")
    exit(0)

if __name__ == "__main__":
    main()
