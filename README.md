## NBA Expression Synthesis

This repository accompanies the paper and provides tooling to:
- Convert LTL formulas to omega-regular expressions.
- Compute expression metrics at scale.
- Characterize formula sets via Spot classifications and automaton statistics.

**Setup**
The provided conda environment reproduces the environment we used in the paper. However, if you are running on a macOS M chip, Spot 2.11.6 is not available on conda-forge. We recommend using a Linux environment for exact reproduction of paper results.

```bash
conda env create -f environment.yml
conda activate exp-synth
```

**Data**
Formula files live under `formulas/`. Each line is either:
- A raw LTL formula, or
- A line starting with `LTLSPEC` followed by the formula.
Lines starting with `%` are treated as comments.

## Reproducing Experiments

**RQ1: Comparison of Transition-Based, Direct, and Converted NBAs**

To compute metrics for all formulas in `formulas/merged.ltl`, run:
```bash
python compute.py \
  --input formulas/merged.ltl \
  --output metrics.csv \
  --methods state_direct transition_to_state transition_only \
  --nfa2regex bmc
```

**RQ2: Obtaining State Counts for NBA Variants**

To compute state counts for all formulas in `formulas/merged.ltl`, run:
```bash
python scripts/count_states.py \
  --input formulas/merged.ltl \
  --output ltl_state_counts.csv
```
(Timeout here does not matter provided it is higher than the timeout for the main compute script, which is 120 seconds. It will automatically produce the same NBAs used in the main compute script.)

**RQ3: Simplification Compensation**

To compute metrics for all formulas in `formulas/merged.ltl`, run:
```bash
python compute.py \
  --input formulas/merged.ltl \
  --output simplified_metrics.csv \
  --methods simplify_state_direct simplify_transition_to_state \
  --nfa2regex bmc
```
This command will compute metrics for the simplified Direct and Transition-based NBAs, which we use to compensate for simplification in our comparisons. Assumes you have already produced the main metrics file, as that data is required to produce the compensation factor.

**RQ4: MP Class Characterization**

To characterize formulas by their MP class, run:
```bash
python scripts/ltl_properties.py \
  --input formulas/merged.ltl \
  --output ltl_properties.csv
```

**Heuristic Evaluation**

To evaluate the selection method on all formulas in `formulas/merged.ltl`, run:
```bash
python compute.py \
  --input formulas/merged.ltl \
  --output selection_metrics.csv \
  --methods transition_selection transition_selection2 \
  --nfa2regex bmc
```
The difference between `transition_selection` and `transition_selection2` is that the former compares the transition-based NBA to the Direct NBA, while the latter compares the transition-based NBA to the Converted NBA.

**Solve a Single Formula**

```bash
python solve.py \
  --formula "G(a -> Fb)" \
  --solver state_direct \
  --nfa2regex bmc
```

Solver methods:
- `state_direct`, `simplify_state_direct` (BMC is hardcoded; `--nfa2regex` ignored)
- `transition_to_state`, `simplify_transition_to_state`
- `transition_only`, `simplify_transition_only`
- `transition_selection`, `simplify_transition_selection`
- `transition_selection2`, `simplify_transition_selection2` (BMC only)

**Results**
Experimental outputs used in the paper are provided in `results/` and were generated
from `formulas/merged.ltl` using Spot 2.11.6.

**Package Layout**
```
src/nba_expression_synthesis/
  syntax/      # Omega-regex data structures and helpers
  synthesis/   # Graph and conversion utilities
  regex_methods.py
```
