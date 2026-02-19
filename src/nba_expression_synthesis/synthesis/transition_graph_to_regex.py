import copy

from typing import List, Tuple, Optional
from nba_expression_synthesis.syntax.omega_regex import Regex, OmegaRegex, Concat, Star, Union, ConcatOmega, Repeat, UnionOmega, OmegaEmpty
from nba_expression_synthesis.synthesis.graph import Graph, Edge
from collections import defaultdict

from functools import lru_cache

from nba_expression_synthesis.syntax.regex_utils import simplify

class tGraph(Graph):
    def __init__(self, num_states: int, initial_state: int):
        super().__init__(num_states, initial_state)
        self.acc_trans = []
        self.nonacc_trans = []

    def add_edge(self, src: int, dst: int, label: Regex, accepting: bool):
        super().add_edge(src, dst, label, accepting)
        if accepting:
            self.acc_trans.append(Edge(src, dst, label, accepting))
            self.final_states.add(src)
        else:
            self.nonacc_trans.append(Edge(src, dst, label))

    def remove_edge(self, src: int, dst: int, label: Regex, accepting: bool):
        super().remove_edge(src, dst, label)
        e = Edge(src, dst, label, accepting)
        if accepting:
            # self.acc_trans = [x for x in self.acc_trans if x != Edge(src, dst, label)]
            self.acc_trans.remove(e)
        else:
            # self.nonacc_trans = [x for x in self.nonacc_trans if x != Edge(src, dst, label)]
            self.nonacc_trans.remove(e)
        if src in self.final_states:
            if len(self.get_accepting_transitions_from(src)) == 0:
            # now src is no longer an accepting state. Remove it from final states
                self.final_states.remove(src)

    def get_accepting_transitions(self):
        return self.acc_trans
    
    def get_nonaccepting_transitions(self):
        return self.nonacc_trans

    def get_accepting_transitions_from(self, src: int):
        return [e for e in self.vertices[src].out_edges if e.accepting]
    
    def get_accepting_transitions_to(self, dst: int):
        return [e for e in self.vertices[dst].in_edges if e.accepting]
    
    def get_nonaccepting_transitions_from(self, src: int):
        return [e for e in self.vertices[src].out_edges if not e.accepting]
    
    def get_nonaccepting_transitions_to(self, dst: int):
        return [e for e in self.vertices[dst].in_edges if not e.accepting]
    
    def state_pseudoaccepting(self, state: int):
        return len(self.get_nonaccepting_transitions_from(state)) > 0 and len(self.get_accepting_transitions_from(state)) > 0

def mcnaughton_yamada(tba: tGraph, i=0, j=None, acc=None) -> Optional[Regex]:
    if j is None:
        j = tba.num_states - 1

    # Precompute transitions
    transitions = {}
    for v in tba.vertices.values():
        transitions[v.number] = {}
        for e in v.out_edges:
            if e.dst not in transitions[v.number]:
                transitions[v.number][e.dst] = []
            transitions[v.number][e.dst].append(e)

    @lru_cache(maxsize=None)
    def r(i_p, j_p, k):
        if k == -1:
            trans = transitions.get(i_p, {}).get(j_p, [])
            if i_p == i:
                if acc == True:
                    trans = [x for x in trans if x.accepting]
                elif acc == False:
                    trans = [x for x in trans if not x.accepting]
            if not trans:
                return None
            elif len(trans) == 1:
                return trans[0].label
            else:
                result = trans[0].label
                for t in trans[1:]:
                    result = Union(result, t.label)
                return result
        elif k == j_p:
            return r(i_p, j_p, k-1)
        elif k == i_p:
            rep = r(i_p, i_p, k-1)
            go = r(i_p, j_p, k-1)
            if rep is None:
                return go
            if go is None:
                return None
            return Concat(Star(rep), go)
        else:
            prev = r(i_p, k, k-1)
            rep = r(k, k, k-1)
            go = r(k, j_p, k-1)
            i_j = r(i_p, j_p, k-1)
            
            if prev is None or go is None:
                return i_j
            
            if rep is None:
                result = Concat(prev, go)
            else:
                result = Concat(prev, Concat(Star(rep), go))
            
            return Union(i_j, result) if i_j is not None else result

    return r(i, j, tba.num_states - 1)


def find_path(g: tGraph, v_start: int, v_end: int) -> Optional[Regex]:
    g = copy.deepcopy(g)
    v_rip = find_rip_vertex(g, v_start, v_end)
    while v_rip is not None:
        rip(g, v_rip)
        g = combine_duplicate_edge(g)
        v_rip = find_rip_vertex(g, v_start, v_end)
    r1 = None
    r2 = None
    for e in g.vertices[v_start].out_edges:
        if e.dst == v_start:
            r1 = e.label if r1 is None else Union(r1, e.label)
        if e.dst == v_end:
            r2 = e.label if r2 is None else Union(r2, e.label)
    r3 = None
    r4 = None
    for e in g.vertices[v_end].out_edges:
        if e.dst == v_start:
            r3 = e.label if r3 is None else Union(r3, e.label)
        if e.dst == v_end:
            r4 = e.label if r4 is None else Union(r4, e.label)
    if r2 is None:
        return None
    if v_start == v_end:
        return r2
    return combine_final(r1, r2, r3, r4)
    

def find_accpath(g: tGraph, v_start: int, v_end: int) -> Optional[Regex]:
    g = copy.deepcopy(g)
    v_rip = find_rip_vertex(g, v_start, v_end)
    while v_rip is not None:
        rip(g, v_rip, acc=True, v_start=v_start, v_end=v_end)
        g = combine_duplicate_edge(g)
        v_rip = find_rip_vertex(g, v_start, v_end)
    r1 = None
    r2 = None
    for e in g.vertices[v_start].out_edges:
        if e.dst == v_start and e.dst != v_end:
            if not e.accepting:
                continue
            r1 = e.label if r1 is None else Union(r1, e.label)
        if e.dst == v_end:
            if e.src == v_start and not e.accepting:
                continue
            r2 = e.label if r2 is None else Union(r2, e.label)
    r3 = None
    r4 = None
    for e in g.vertices[v_end].out_edges:
        if e.dst == v_start:
            r3 = e.label if r3 is None else Union(r3, e.label)
        if e.dst == v_end:
            r4 = e.label if r4 is None else Union(r4, e.label)
    if r2 is None:
        return None
    if v_start == v_end:
        return r2
    return combine_final(r1, r2, r3, r4)

def find_nonaccpath(g: tGraph, v_start: int, v_end: int) -> Optional[Regex]:
    g = copy.deepcopy(g)
    v_rip = find_rip_vertex(g, v_start, v_end)
    while v_rip is not None:
        rip(g, v_rip, acc=False, v_start=v_start, v_end=v_end)
        g = combine_duplicate_edge(g)
        v_rip = find_rip_vertex(g, v_start, v_end)
    r1 = None
    r2 = None
    for e in g.vertices[v_start].out_edges:
        if e.dst == v_start and e.dst != v_end:
            if e.accepting:
                continue
            r1 = e.label if r1 is None else Union(r1, e.label)
        if e.dst == v_end:
            if e.src == v_start and e.accepting:
                continue
            r2 = e.label if r2 is None else Union(r2, e.label)
    r3 = None
    r4 = None
    for e in g.vertices[v_end].out_edges:
        if e.dst == v_start:
            r3 = e.label if r3 is None else Union(r3, e.label)
        if e.dst == v_end:
            r4 = e.label if r4 is None else Union(r4, e.label)
    if r2 is None:
        return None
    if v_start == v_end:
        return r2

    return combine_final(r1, r2, r3, r4)

def combine_final(r1: Optional[Regex], r2: Regex, r3: Optional[Regex], r4: Optional[Regex]) -> Regex:
    if r1 is None:
        return r2
    return Concat(Star(r1), r2)

def find_rip_vertex(g: tGraph, v_start: int, v_end: int) -> Optional[int]:
    states = set(g.vertices.keys())
    states.remove(v_start)
    if v_start != v_end:
        states.remove(v_end)
    if len(states) == 0:
        return None
    # sort states
    states = sorted(list(states))
    return states[0]

def contain_self_loop(g: tGraph, v: int) -> Optional[Edge]:
    for e in g.vertices[v].out_edges:
        if e.src == e.dst:
            return e
    return None

def rip(g: Graph, v_rip: int, acc=None, v_start=None, v_end=None):
    loop = contain_self_loop(g, v_rip)
    r_rip = loop.label if loop is not None else None
    added_edges: List[Tuple[int, int, Regex]] = []
    for e_in in g.vertices[v_rip].in_edges:
        for e_out in g.vertices[v_rip].out_edges:
            if e_in.src == v_rip or e_out.dst == v_rip:
                continue
            r_in = e_in.label
            r_out = e_out.label
            r = Concat(r_in, r_out) if r_rip is None else Concat(
                r_in, Concat(Star(r_rip), r_out))
            added_edges.append((e_in.src, e_out.dst, r, e_in.accepting))
    for e_in in g.vertices[v_rip].in_edges:
        g.vertices[e_in.src].out_edges.remove(e_in)
    for e_out in g.vertices[v_rip].out_edges:
        g.vertices[e_out.dst].in_edges.remove(e_out)
    for s, t, r, a in added_edges:
        g.add_edge(s, t, r, a)
    del g.vertices[v_rip]
    g.num_states -= 1

def taut_to_regex_mny(g: tGraph) -> Optional[Regex]:
    g = combine_duplicate_edge(g)
    # g = add_episilon_final_state(g)
    all_paths: List[OmegaRegex] = []
    for f in g.final_states:
        path1 = mcnaughton_yamada(g, g.initial_state, f, None) if g.initial_state != f else None
        path2 = mcnaughton_yamada(g, f, f, True)
        path3 = mcnaughton_yamada(g, f, f, False) if g.state_pseudoaccepting(f) else None
        if path1 is None and path2 is not None:
            if path3 is None:
                all_paths.append(Repeat(path2))
            else:
                all_paths.append(Repeat(Concat(Star(path3), path2)))
        elif path1 != None and path2 is not None:
                if path3 is None:
                    all_paths.append(ConcatOmega(path1, Repeat(path2)))
                else:
                    all_paths.append(ConcatOmega(path1, Repeat(Concat(Star(path3), path2))))
    if len(all_paths) == 0:
        return OmegaEmpty()
    p = all_paths[0]
    for i in range(1, len(all_paths)):
        p = UnionOmega(p, all_paths[i])

    return p

@simplify
def simp_taut_to_regex_mny(g: tGraph) -> Optional[Regex]:
    g = combine_duplicate_edge(g)
    # g = add_episilon_final_state(g)
    all_paths: List[OmegaRegex] = []
    for f in g.final_states:
        path1 = mcnaughton_yamada(g, g.initial_state, f, None) if g.initial_state != f else None
        path2 = mcnaughton_yamada(g, f, f, True)
        path3 = mcnaughton_yamada(g, f, f, False) if g.state_pseudoaccepting(f) else None
        if path1 is None and path2 is not None:
            if path3 is None:
                all_paths.append(Repeat(path2))
            else:
                all_paths.append(Repeat(Concat(Star(path3), path2)))
        elif path1 is not None and path2 is not None:
                if path3 is None:
                    all_paths.append(ConcatOmega(path1, Repeat(path2)))
                else:
                    all_paths.append(ConcatOmega(path1, Repeat(Concat(Star(path3), path2))))
    if len(all_paths) == 0:
        return OmegaEmpty()
    p = all_paths[0]
    for i in range(1, len(all_paths)):
        p = UnionOmega(p, all_paths[i])
    return p

def taut_to_regex_bmc(g: tGraph) -> Optional[OmegaRegex]:
    g = combine_duplicate_edge(g)
    # g = add_episilon_final_state(g)
    all_paths: List[OmegaRegex] = []
    for f in g.final_states:
        path1 = find_path(g, g.initial_state, f) if g.initial_state != f else None
        path2 = find_accpath(g, f, f)
        path3 = find_nonaccpath(g, f, f) if g.state_pseudoaccepting(f) else None
        if path1 is None and path2 is not None:
            if path3 is None:
                all_paths.append(Repeat(path2))
            else:
                all_paths.append(Repeat(Concat(Star(path3), path2)))
        elif path1 is not None and path2 is not None:
                if path3 is None:
                    all_paths.append(ConcatOmega(path1, Repeat(path2)))
                else:
                    all_paths.append(ConcatOmega(path1, Repeat(Concat(Star(path3), path2))))
    if len(all_paths) == 0:
        return OmegaEmpty()
    p = all_paths[0]
    for i in range(1, len(all_paths)):
        p = UnionOmega(p, all_paths[i])
    return p

@simplify
def simp_taut_to_regex_bmc(g: tGraph) -> Optional[OmegaRegex]:
    g = combine_duplicate_edge(g)
    # g = add_episilon_final_state(g)
    all_paths: List[OmegaRegex] = []
    for f in g.final_states:
        path1 = find_path(g, g.initial_state, f) if g.initial_state != f else None
        path2 = find_accpath(g, f, f)
        path3 = find_nonaccpath(g, f, f)
        if path1 is None and path2 is not None:
            if path3 is None:
                all_paths.append(Repeat(path2))
            else:
                all_paths.append(Repeat(Concat(Star(path3), path2)))
        elif path1 is not None and path2 is not None:
                if path3 is None:
                    all_paths.append(ConcatOmega(path1, Repeat(path2)))
                else:
                    all_paths.append(ConcatOmega(path1, Repeat(Concat(Star(path3), path2))))
    if len(all_paths) == 0:
        return OmegaEmpty()
    p = all_paths[0]
    for i in range(1, len(all_paths)):
        p = UnionOmega(p, all_paths[i])
    return p


def combine_duplicate_edge(g: tGraph) -> tGraph:
    edge_dict = defaultdict(list)
    for v in g.vertices.values():
        for e in v.out_edges:
            key = (e.src, e.dst, e.accepting)
            edge_dict[key].append(e)

    def combine_one_duplicate_edge() -> bool:
        for key, edges in list(edge_dict.items()):
            if len(edges) > 1:
                # Combine labels using pairwise Union
                combined_label = edges[0].label
                for e in edges[1:]:
                    combined_label = Union(combined_label, e.label)
                
                # Update the first edge's label
                edges[0].label = combined_label
                
                # Remove other edges
                for e in edges[1:]:
                    g.remove_edge(e.src, e.dst, e.label, e.accepting)
                    edge_dict[key].remove(e)
                
                # If only one edge left, remove the key from edge_dict
                if len(edge_dict[key]) == 1:
                    del edge_dict[key]
                
                return True
        return False

    while combine_one_duplicate_edge():
        pass

    return g
