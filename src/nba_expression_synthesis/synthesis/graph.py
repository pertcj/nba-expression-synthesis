from dataclasses import dataclass, field
from typing import List, Dict, Set
from nba_expression_synthesis.syntax.omega_regex import Regex


@dataclass(eq=True)
class Edge:
    src: int
    dst: int
    label: Regex
    accepting: bool = False

    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, Edge) and self.src == __value.src and self.dst == __value.dst and self.label == __value.label


@dataclass(eq=True)
class Vertex:
    number: int
    out_edges: List[Edge] = field(default_factory=list)
    in_edges: List[Edge] = field(default_factory=list)

    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, Vertex) and self.number == __value.number

@dataclass
class Graph:
    num_states: int
    initial_state: int
    final_states: Set[int] = field(default_factory=set)
    vertices: Dict[int, Vertex] = field(default_factory=dict)

    def __init__(self, num_states: int, initial_state: int):
        self.num_states = num_states
        self.initial_state = initial_state
        self.final_states = set()
        self.vertices = {i: Vertex(i) for i in range(num_states)}

    def get_init(self) -> Vertex:
        return self.vertices[self.initial_state]

    def get_finals(self) -> List[Vertex]:
        return [self.vertices[v] for v in self.final_states]

    def get_vertex(self, v: int) -> Vertex:
        return self.vertices[v]

    def add_edge(self, src: int, dst: int, label: Regex, accepting: bool = False):
        e = Edge(src, dst, label, accepting)
        self.vertices[src].out_edges.append(e)
        self.vertices[dst].in_edges.append(e)

    def remove_edge(self, src: int, dst: int, label: Regex):
        e = Edge(src, dst, label)
        self.vertices[src].out_edges.remove(e)
        self.vertices[dst].in_edges.remove(e)

    def to_rabit_form(self):
        strs = []
        strs.append(f"[{self.initial_state}]")
        for v in self.vertices:
            for e in self.vertices[v].out_edges:
                strs.append(f"{e.label},[{e.src}]->[{e.dst}]")
        for v in self.final_states:
            strs.append(f"[{v}]")
        return strs
