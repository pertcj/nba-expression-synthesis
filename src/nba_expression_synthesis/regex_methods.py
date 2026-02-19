import multiprocessing
import spot
import time
import logging

from nba_expression_synthesis.synthesis.transition_graph_pipeline import aut_to_tgraph
from nba_expression_synthesis.synthesis.transition_graph_to_regex import taut_to_regex_bmc, taut_to_regex_mny
from nba_expression_synthesis.syntax.regex_utils import omega_regex_simplifier as simplify

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

def ltl_to_aut(ltl_formula: str, conversion_fn):
    timing = time.time()
    return conversion_fn(spot.translate(ltl_formula, 'buchi', 'sbacc')), time.time() - timing

def ltl_to_transition_aut(ltl_formula: str, conversion_fn):
    timing = time.time()
    return conversion_fn(spot.translate(ltl_formula, 'buchi')), time.time() - timing

def ltl_transition_to_state_aut(ltl_formula: str, conversion_fn):
    timing = time.time()
    transition_aut = spot.translate(ltl_formula, 'buchi')
    degen_aut = spot.degeneralize(transition_aut)
    degen_aut.copy_state_names_from(transition_aut)
    return conversion_fn(degen_aut), time.time() - timing

def simplify_state_direct_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=30):
    result = run_with_timeout(ltl_to_aut, (formula, aut_to_tgraph,), aut_timeout)
    if result == None:
        return None, (aut_timeout, -1, -1)
    graph, aut_time = result
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_bmc, (graph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    simplify_time = time.time()
    result = run_with_timeout(simplify, (regex,), simplify_timeout)
    if result == None:
        return None, (aut_time, regex_const_time, simplify_timeout)
    regex = result
    simplify_time = time.time() - simplify_time
    del graph
    return regex, (aut_time, regex_const_time, simplify_time)

def state_direct_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=None):
    result = run_with_timeout(ltl_to_aut, (formula, aut_to_tgraph,), aut_timeout)
    if result == None:
        return None, (aut_timeout, -1, -1)
    graph, aut_time = result
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_bmc, (graph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    del graph
    return regex, (aut_time, regex_const_time, 0)

def transition_or_state_aut(formula, aut_timeout, conversion_fn):
    result_transition = run_with_timeout(ltl_to_transition_aut, (formula, conversion_fn, ), aut_timeout)
    result_state = run_with_timeout(ltl_to_aut, (formula, conversion_fn,), aut_timeout)
    if result_transition == None and result_state == None:
        return None, aut_timeout
    elif result_transition == None and result_state != None:
        automaton, aut_time = result_state
        return automaton, aut_time
    elif result_transition != None and result_state == None:
        automaton, aut_time = result_transition
        return automaton, aut_time
    else:
        automaton_transition, aut_time_transition = result_transition
        automaton_state, aut_time_state = result_state
        def num_accepting_states(aut):
            return len(aut.get_finals())
        def num_states(aut):
            return len(aut.vertices.keys())
        # print(num_accepting_states(aut), num_accepting_states(sbacc_aut))
        n_acc_state = num_accepting_states(automaton_state)
        n_acc_transition = num_accepting_states(automaton_transition)

        if n_acc_state > n_acc_transition or ((n_acc_state == n_acc_transition) and (num_states(automaton_transition) < num_states(automaton_state))): # we prefer the state based transition when the states are equal as this preserves the order of states.
            del automaton_state
            return automaton_transition, aut_time_transition
            # return automaton_state, aut_time_state
        del automaton_transition
        # return automaton_transition, aut_time_transition
        return automaton_state, aut_time_state
    
def transition_or_state_converted_aut(formula, aut_timeout, conversion_fn):
    result_transition = run_with_timeout(ltl_to_transition_aut, (formula, conversion_fn, ), aut_timeout)
    result_state = run_with_timeout(ltl_transition_to_state_aut, (formula, conversion_fn,), aut_timeout)
    if result_transition == None and result_state == None:
        return None, aut_timeout
    elif result_transition == None and result_state != None:
        automaton, aut_time = result_state
        return automaton, aut_time
    elif result_transition != None and result_state == None:
        automaton, aut_time = result_transition
        return automaton, aut_time
    else:
        automaton_transition, aut_time_transition = result_transition
        automaton_state, aut_time_state = result_state
        def num_accepting_states(aut):
            return len(aut.get_finals())
        def num_states(aut):
            return len(aut.vertices.keys())
        # print(num_accepting_states(aut), num_accepting_states(sbacc_aut))
        n_acc_state = num_accepting_states(automaton_state)
        n_acc_transition = num_accepting_states(automaton_transition)

        if n_acc_state > n_acc_transition or ((n_acc_state == n_acc_transition) and (num_states(automaton_transition) < num_states(automaton_state))): # we prefer the state based transition when the states are equal as this preserves the order of states.
            del automaton_state
            return automaton_transition, aut_time_transition
            # return automaton_state, aut_time_state
        del automaton_transition
        # return automaton_transition, aut_time_transition
        return automaton_state, aut_time_state

def transition_bmc_original_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=None):
    automaton, aut_time = transition_or_state_aut(formula, aut_timeout, aut_to_tgraph)
    if automaton == None:
        return None, (aut_time, -1, -1)
    tgraph = automaton
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_bmc, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    del tgraph
    return regex, (aut_time, regex_const_time, 0)

def transition_bmc_original2_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=None):
    automaton, aut_time = transition_or_state_converted_aut(formula, aut_timeout, aut_to_tgraph)
    if automaton == None:
        return None, (aut_time, -1, -1)
    tgraph = automaton
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_bmc, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    del tgraph
    return regex, (aut_time, regex_const_time, 0)

def simplify_transition_bmc_original2_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=30):
    automaton, aut_time = transition_or_state_converted_aut(formula, aut_timeout, aut_to_tgraph)
    if automaton == None:
        return None, (aut_time, -1, -1)
    tgraph = automaton
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_bmc, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    simplify_time = time.time()
    result = run_with_timeout(simplify, (regex,), simplify_timeout)
    if result == None:
        return None, (aut_time, regex_const_time, simplify_timeout)
    regex = result
    simplify_time = time.time() - simplify_time
    del tgraph
    return regex, (aut_time, regex_const_time, simplify_time)

def simplify_transition_bmc_original_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=30):
    automaton, aut_time = transition_or_state_aut(formula, aut_timeout, aut_to_tgraph)
    if automaton == None:
        return None, (aut_time, -1, -1)
    tgraph = automaton
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_bmc, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    simplify_time = time.time()
    result = run_with_timeout(simplify, (regex,), simplify_timeout)
    if result == None:
        return None, (aut_time, regex_const_time, simplify_timeout)
    regex = result
    simplify_time = time.time() - simplify_time
    del tgraph
    return regex, (aut_time, regex_const_time, simplify_time)

def transition_mny_original_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=None):
    automaton, aut_time = transition_or_state_aut(formula, aut_timeout, aut_to_tgraph)
    if automaton == None:
        return None, (aut_time, -1, -1,)
    tgraph = automaton
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_mny, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    del tgraph
    return regex, (aut_time, regex_const_time, 0)

def simplify_transition_mny_original_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=30):
    automaton, aut_time = transition_or_state_aut(formula, aut_timeout, aut_to_tgraph)
    if automaton == None:
        return None, (aut_time, -1, -1)
    tgraph = automaton
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_mny, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    simplify_time = time.time()
    result = run_with_timeout(simplify, (regex,), simplify_timeout)
    if result == None:
        return None, (aut_time, regex_const_time, simplify_timeout)
    regex = result
    simplify_time = time.time() - simplify_time
    del tgraph
    return regex, (aut_time, regex_const_time, simplify_time)

def transition_bmc_only_transition_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=None):
    result = run_with_timeout(ltl_to_transition_aut, (formula, aut_to_tgraph), aut_timeout)
    if result == None:
        return None, (aut_timeout, -1, -1)
    tgraph, aut_time = result
    # tgraph = aut_to_tgraph(automaton)
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_bmc, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    del tgraph
    return regex, (aut_time, regex_const_time, 0)

def simplify_transition_bmc_only_transition_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=30):
    result = run_with_timeout(ltl_to_transition_aut, (formula, aut_to_tgraph), aut_timeout)
    if result == None:
        return None, (aut_timeout, -1, -1)
    tgraph, aut_time = result
    # tgraph = aut_to_tgraph(automaton)
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_bmc, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    simplify_time = time.time()
    result = run_with_timeout(simplify, (regex,), simplify_timeout)
    if result == None:
        return None, (aut_time, regex_const_time, simplify_timeout, -1)
    regex = result
    simplify_time = time.time() - simplify_time
    del tgraph
    return regex, (aut_time, regex_const_time, simplify_time, 0)

def transition_mny_only_transition_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=None):
    result = run_with_timeout(ltl_to_transition_aut, (formula, aut_to_tgraph), aut_timeout)
    if result == None:
        return None, (aut_timeout, -1, -1)
    tgraph, aut_time = result
    # tgraph = aut_to_tgraph(automaton)
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_mny, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    del tgraph
    return regex, (aut_time, regex_const_time, 0)

def simplify_transition_mny_only_transition_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=30):
    result = run_with_timeout(ltl_to_transition_aut, (formula, aut_to_tgraph), aut_timeout)
    if result == None:
        return None, (aut_timeout, -1, -1)
    tgraph, aut_time = result
    # tgraph = aut_to_tgraph(automaton)
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_mny, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    simplify_time = time.time()
    result = run_with_timeout(simplify, (regex,), simplify_timeout)
    if result == None:
        return None, (aut_time, regex_const_time, simplify_timeout)
    regex = result
    simplify_time = time.time() - simplify_time
    del tgraph
    return regex, (aut_time, regex_const_time, simplify_time)

def transition_bmc_only_state_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=None):
    result = run_with_timeout(ltl_transition_to_state_aut, (formula, aut_to_tgraph), aut_timeout)
    if result == None:
        return None, (aut_timeout, -1, -1)
    tgraph, aut_time = result
    # tgraph = aut_to_tgraph(automaton)
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_bmc, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    del tgraph
    return regex, (aut_time, regex_const_time, 0)

def simplify_transition_bmc_only_state_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=30):
    result = run_with_timeout(ltl_transition_to_state_aut, (formula, aut_to_tgraph), aut_timeout)
    if result == None:
        return None, (aut_timeout, -1, -1)
    tgraph, aut_time = result
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_bmc, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    simplify_time = time.time()
    result = run_with_timeout(simplify, (regex,), simplify_timeout)
    if result == None:
        return None, (aut_time, regex_const_time, simplify_timeout)
    regex = result
    simplify_time = time.time() - simplify_time
    del tgraph
    return regex, (aut_time, regex_const_time, simplify_time)

def transition_mny_only_state_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=None):
    result = run_with_timeout(ltl_transition_to_state_aut, (formula, aut_to_tgraph), aut_timeout)
    if result == None:
        return None, (aut_timeout, -1, -1)
    tgraph, aut_time = result
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_mny, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    del tgraph
    return regex, (aut_time, regex_const_time, 0)

def simplify_transition_mny_only_state_solver(formula, aut_timeout=30, regex_timeout=30, simplify_timeout=30):
    result = run_with_timeout(ltl_transition_to_state_aut, (formula, aut_to_tgraph), aut_timeout)
    if result == None:
        return None, (aut_timeout, -1, -1)
    tgraph, aut_time = result
    regex_const_time = time.time()
    result = run_with_timeout(taut_to_regex_mny, (tgraph,), regex_timeout)
    if result == None:
        return None, (aut_time, regex_timeout, -1, -1)
    regex = result
    regex_const_time = time.time() - regex_const_time
    simplify_time = time.time()
    result = run_with_timeout(simplify, (regex,), simplify_timeout)
    if result == None:
        return None, (aut_time, regex_const_time, simplify_timeout)
    regex = result
    simplify_time = time.time() - simplify_time
    del tgraph
    return regex, (aut_time, regex_const_time, simplify_time)
