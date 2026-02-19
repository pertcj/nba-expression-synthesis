import argparse
from pathlib import Path

import spot

spot.setup()

def parse_ltl(input, res, errkey='parse_error', synkey='prefix_syntax'):
    env = spot.default_environment.instance()
    pf = spot.parse_infix_psl(input, env)
    f = pf.f
    if pf.errors:
        # Try the LBT parser in case someone is throwing LBT formulas at us.
        pg = spot.parse_prefix_ltl(input, env)
        if pg.errors:
            errstr = spot.ostringstream()
            pf.format_errors(errstr)
            res[errkey] = errstr.str()
        else:
            f = pg.f
            res[synkey] = True
    # starting with Spot 2.6.1 we can do "return f", but before that f is a
    # pointer into the pf/pg structure, so we cannot return it.
    if not f:
        return None
    return spot.formula(str(f))

mp_class_to_english = {
    'B': "safety and guarantee",
    'S': "safety",
    'G': "guarantee",
    'O': "obligation",
    'R': "recurrence",
    'P': "persistence",
    'T': "reactivity",
}

# Output
#
# on syntax error: { parse_error: "text" }
#
# on success:
# { mp_class: 'name',
#   pathological: true,   (absent if not pathological)
#   mp_hierarchy_svg: '<svg...'
#   acc_word: 'word',     (an example of accepting word, or null)
#   rej_word: 'word',     (an example of rejecting word, or null)
#   stutter_invariant: false,   (or true, or 'no X')
#   stutter_invariant_eq: formula,  (* see below)
#   safety_liveness: 'safety'  (or 'liveness', or 'both', or 'none')
# }
#
# stutter_invariant_eq is only given if stutter_invariant=true (not 'no X'),
# and simplifying the input ltlformula gives a syntactically stutter-invariant
# formula.
def study(ltlformula, method='GET'):
    result = {}

    f = parse_ltl(ltlformula, result)
    if not f:
        return result

    # If the formula uses a lot of atomic propositions together, it's better to
    # relabel it to restrict the size of AP.  We do it always, just in case.
    relabmap = spot.relabeling_map()
    f2 = spot.relabel_bse(f, spot.Pnn, relabmap)

    mp_class = spot.mp_class(f2)

    result['mp_class'] = mp_class
    result['mp_class_text'] = mp_class_to_english[mp_class]
    result['pathological'] = False

    print(result)

    syntactic_class = None
    if mp_class == 'R':
        syntactic_class = f2.is_syntactic_recurrence()
    if mp_class == 'P':
        syntactic_class = f2.is_syntactic_persistence()
    if mp_class == 'O':
        syntactic_class = f2.is_syntactic_obligation()
    if mp_class == 'S':
        syntactic_class = f2.is_syntactic_safety()
    if mp_class == 'G':
        syntactic_class = f2.is_syntactic_guarantee()
    if mp_class == 'B':
        syntactic_class = (f2.is_syntactic_safety() and
                           f2.is_syntactic_guarantee())
    if syntactic_class is False:
        result['pathological'] = True

    result['mp_hierarchy_svg'] = spot.mp_hierarchy_svg(mp_class)

    # This is to be done before translation, otherwise f will be simplified
    ssi = f2.is_syntactic_stutter_invariant()

    pos = spot.translate(f2, 'buchi')

    # Do this check before relabeling the automaton, to limit the 2^AP
    # explosion in is_liveness_automaton.
    if spot.is_liveness_automaton(pos):
        if mp_class in ('S', 'B'):
            result['safety_liveness'] = 'both'
        else:
            result['safety_liveness'] = 'liveness'
    else:
        if mp_class in ('S', 'B'):
            result['safety_liveness'] = 'safety'
        else:
            result['safety_liveness'] = 'none'

    # f2 was simplified by translate.
    if (ssi is False and f2.is_syntactic_stutter_invariant()):
        result['stutter_invariant_eq'] = str(spot.relabel_apply(f2, relabmap))

    neg = spot.translate(spot.formula_Not(f2), 'buchi')

    spot.relabel_here(pos, relabmap)
    spot.relabel_here(neg, relabmap)

    if ssi:
        result['stutter_invariant'] = 'syntactic stutter-invariant'
    else:
        word = spot.product(spot.closure(pos),
                            spot.closure(neg)).accepting_word()
        if word is None:
            result['stutter_invariant'] = "stutter-invariant"
        else:
            result['stutter_invariant'] = "stutter-sensitive"

    del pos
    del neg

    return result['mp_class_text'], result['safety_liveness'], result['stutter_invariant'], result['pathological']

import multiprocessing

def parse_args():
    repo_root = Path(__file__).resolve().parents[1]
    default_input = repo_root / "formulas" / "merged.ltl"
    default_output = repo_root / "ltl_formula_properties.csv"

    parser = argparse.ArgumentParser(description="Classify LTL formulas with Spot.")
    parser.add_argument(
        "--input",
        default=str(default_input),
        help="Path to .ltl file (default: formulas/merged.ltl)",
    )
    parser.add_argument(
        "--output",
        default=str(default_output),
        help="Output CSV file (default: ltl_formula_properties.csv)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Timeout in seconds per formula (default: 120)",
    )
    parser.add_argument(
        "--processes",
        type=int,
        default=4,
        help="Number of worker processes (default: 4)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as g:
        g.write("index,mp_class,safety_liveness,stutter_invariant,pathological\n")

    index = 0
    with open(output_path, 'a') as g:
        with open(input_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('%'):
                    continue
                if line.startswith("LTLSPEC"):
                    formula = line.split("LTLSPEC")[1].strip()
                else:
                    formula = line.strip()
                with multiprocessing.Pool(processes=args.processes) as pool:
                    result = pool.apply_async(study, args=(formula,))
                    try:
                        props = result.get(timeout=args.timeout)
                        g.write(f"{index},{props[0]},{props[1]},{props[2]},{props[3]}\n")
                        print(f"{index},{props[0]},{props[1]},{props[2]},{props[3]}")
                    except multiprocessing.TimeoutError:
                        g.write(f"{index},timed out\n")
                        print(f"Formula {index} timed out")
                index += 1
