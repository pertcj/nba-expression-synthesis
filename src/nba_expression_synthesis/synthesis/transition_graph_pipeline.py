import spot

from nba_expression_synthesis.syntax.omega_regex import Symbol
from nba_expression_synthesis.synthesis.transition_graph_to_regex import tGraph
    
def aut_to_tgraph(aut):
    assert aut.num_sets() == 1
    bdict = aut.get_dict()
    graph = tGraph(aut.num_states(), aut.get_init_state_number())
    for t in aut.edges():
        graph.add_edge(t.src, t.dst, Symbol(
            spot.bdd_format_formula(bdict, t.cond)), t.acc.has(0)) # 0 is accepting set
    return graph