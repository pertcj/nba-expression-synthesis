from dataclasses import dataclass

@dataclass(eq=True, frozen=True)
class Regex:
    def __str__(self) -> str:
        return regex_to_string(self)

    def __len__(self) -> int:
        return regex_tllen(self, size=False)

    def star_height(self) -> int:
        return regex_star_height(self)
    
    def size(self) -> int:
        return regex_tllen(self, size=True)


@dataclass(eq=True, frozen=True)
class Epsilon(Regex):
    pass


@dataclass(eq=True, frozen=True)
class Empty(Regex):
    pass


@dataclass(eq=True, frozen=True)
class Symbol(Regex):
    symbol: str


@dataclass(eq=True, frozen=True)
class Concat(Regex):
    left: Regex
    right: Regex


@dataclass(eq=True, frozen=True)
class Union(Regex):
    left: Regex
    right: Regex


@dataclass(eq=True, frozen=True)
class Star(Regex):
    regex: Regex


def regex_to_string(regex: Regex) -> str:
    match regex:
        case Epsilon():
            return 'ε'
        case Empty():
            return '0'
        case Symbol(s):
            return f'({s})'
        case Concat(r1, r2):
            return f'({regex_to_string(r1)}{regex_to_string(r2)})'
        case Union(r1, r2):
            return f'({regex_to_string(r1)}|{regex_to_string(r2)})'
        case Star(r):
            return f'({regex_to_string(r)})*'
        case _:
            raise TypeError(f'Unknown regex type: {type(regex)}')
        
from functools import lru_cache

# @lru_cache(maxsize=None)
# def old_tllen(regex: Regex) -> int:
#     # returns timeline length of regex
#     match regex:
#         case Epsilon():
#             return 0
#         case Empty():
#             return 0
#         case Symbol(s):
#             return 1
#         case Concat(r1, r2):
#             return old_tllen(r1) + old_tllen(r2)
#         case Union(r1, r2):
#             u1 = has_union(r1)
#             u2 = has_union(r2)
#             if not (u1 or u2):
#                 return max(num_leaves(r1), num_leaves(r2))
#             if not u1:
#                 return max(num_leaves(r1), old_tllen(r2))
#             if not u2:
#                 return max(old_tllen(r1), num_leaves(r2))
#             return max(old_tllen(r1), old_tllen(r2))
#         case Star(r):
#             return old_tllen(r) 
#         case _:
#             raise TypeError(f'Unknown regex type: {type(regex)}')
from collections import deque

def determine_size(dq: deque):
    size = 0
    while dq:
        x = dq.popleft()
        if x == "+":
            size += 1
        elif x == "?":
            size += 1
        else:
            size += x
    return size

def regex_tllen(regex, size=False):
    # print("regex", regex, size)
    pT = postorderTraversal(regex, size)
    # print("pT", pT)
    # print(pT)
    if not size:
        # print(solve_postorder(pT))
        return solve_postorder(pT)
    return determine_size(pT)
    # return solve_postorder(pT)

@lru_cache(maxsize=-1)
def postorderTraversal(regex: Regex, size=False):
        if regex is Empty or regex is Epsilon:
            return []
        if regex is Symbol:
            return [regex]
        
        stack, ret_val = list(), deque()
        stack.append(regex)
        
        while stack:
            node = stack.pop()
            match node:
                case Empty():
                    return []
                case Epsilon():
                    ret_val.appendleft(0)
                    continue
                case Symbol(s):
                    ret_val.appendleft(1)
                case Concat(r1, r2):
                    stack.append(r2)
                    stack.append(r1)
                    ret_val.appendleft("+")
                    
                case Union(r1, r2):

                    ret_val.appendleft("?")
                    stack.append(r2)
                    stack.append(r1)
                case Star(r):
                    if size:
                        ret_val.appendleft(1)
                    stack.append(r)
                    # temporary measure
                    # ret_val.appendleft(r)
        return ret_val

def solve_postorder(postorder: deque) -> int:
    stack = deque()
    for node in postorder:
        if node == "+":
            right = stack.pop()
            left = stack.pop()
            stack.appendleft(right+left)
        elif node == "?":
            right = stack.pop()
            left = stack.pop()
            if right > left:
                stack.appendleft(right)
            else:
                stack.appendleft(left)
        else:
            stack.append(node)
    if(len(stack) == 0): return 0
    return stack.pop()

def regex_star_height(regex: Regex) -> int:
    # currently returns timeline length of regex
    match regex:
        case Epsilon():
            return 0
        case Empty():
            return 0
        case Symbol(s):
            return 0
        case Concat(r1, r2):
            return max(regex_star_height(r1), regex_star_height(r2))
        case Union(r1, r2):
            return max(regex_star_height(r1), regex_star_height(r2))
        case Star(r):
            return regex_star_height(r) + 1
        case _:
            raise TypeError(f'Unknown regex type: {type(regex)}')

@dataclass(eq=True, frozen=True)
class OmegaRegex:
    def __str__(self) -> str:
        return omega_regex_to_string(self)
    def __len__(self) -> int:
        return omega_regex_tllen(self, size=False)
    def star_height(self) -> int:
        return omega_regex_star_height(self)
    def size(self) -> int:
        return omega_regex_tllen(self, size=True)
    
@dataclass(eq=True, frozen=True)
class OmegaEmpty(OmegaRegex):
    pass

@dataclass(eq=True, frozen=True)
class Repeat(OmegaRegex):
    regex: Regex

@dataclass(eq=True, frozen=True)
class ConcatOmega(OmegaRegex):
    left: Regex
    right: OmegaRegex

@dataclass(eq=True, frozen=True)
class UnionOmega(OmegaRegex):
    left: OmegaRegex
    right: OmegaRegex

def omega_regex_to_string(omega_regex: OmegaRegex) -> str:
    match omega_regex:
        case OmegaEmpty():
            return '0'
        case Repeat(r):
            return f'$({regex_to_string(r)})'
        case ConcatOmega(r1, r2):
            return f'({regex_to_string(r1)}{omega_regex_to_string(r2)})'
        case UnionOmega(r1, r2):
            return f'({omega_regex_to_string(r1)}|{omega_regex_to_string(r2)})'
        case _:
            raise TypeError(f'Unknown omega regex type: {type(omega_regex)}')

def omega_regex_tllen(omega_regex: OmegaRegex, size=False) -> int:
    # print("omega_regex args:", omega_regex)
    # match omega_regex:
    #     case Repeat(r):
    #         return regex_tllen(r)
    #     case ConcatOmega(r1, r2):
    #         return regex_tllen(r1) + omega_regex_tllen(r2)
    #     case UnionOmega(r1, r2):
    #         return max(omega_regex_tllen(r1), omega_regex_tllen(r2))
    #     case _:
    #         raise TypeError(f'Unknown omega regex type: {type(omega_regex)}')
    dq = postorderTraversalOmega(omega_regex, size)
    # print("the dq is ", dq)
    # print("debug dq", debugPostorderOmega(omega_regex, size))
    # print("DQ is ", dq)
    if not size:
        return solve_postorderOmega(dq)
    return determine_size(dq)

def debugPostorderOmega(regex: OmegaRegex, size=False):
        # cache = {}
        if regex is OmegaEmpty:
            return []
        if regex is Repeat:
            return [str(regex.regex), "$"]
            # return [regex_tllen(regex.regex, size) + 1]
        
        stack, ret_val = list(), deque()
        stack.append(regex)
        
        while stack:
            node = stack.pop()
            match node:
                case Repeat(s):
                    if size:
                        ret_val.appendleft("$")
                    ret_val.appendleft(str(s))
                case ConcatOmega(r1, r2):
                    ret_val.appendleft("+")
                    ret_val.appendleft(str(r1))
                    stack.append(r2)
                case UnionOmega(r1, r2):
                    stack.append(r2)
                    stack.append(r1)
                    ret_val.appendleft("|")
        return ret_val

@lru_cache(maxsize=-1)
def postorderTraversalOmega(regex: OmegaRegex, size=False):
        # cache = {}
        if regex is OmegaEmpty:
            return []
        if regex is Repeat:
            return [regex_tllen(regex.regex, size) + 1]
        
        stack, ret_val = list(), deque()
        stack.append(regex)
        
        while stack:
            node = stack.pop()
            match node:
                case Repeat(s):
                    if size:
                        ret_val.appendleft(1)
                    ret_val.appendleft(regex_tllen(s, size))
                case ConcatOmega(r1, r2):
                    ret_val.appendleft("+")
                    ret_val.appendleft(regex_tllen(r1, size))
                    stack.append(r2)
                case UnionOmega(r1, r2):
                    stack.append(r2)
                    stack.append(r1)
                    ret_val.appendleft("?")
        return ret_val

def solve_postorderOmega(postorder: deque) -> int:
    stack = deque()
    for node in postorder:
        if node == "+":
            right = stack.pop()
            left = stack.pop()
            stack.appendleft(right+left)
        elif node == "?":
            right = stack.pop()
            left = stack.pop()
            if right > left:
                stack.appendleft(right)
            else:
                stack.appendleft(left)
        else:
            stack.append(node)
    if(len(stack) == 0): return 0
    return stack.pop()


def omega_regex_star_height(omega_regex: OmegaRegex) -> int:
    match omega_regex:
        case OmegaEmpty():
            return 0
        case Repeat(r):
            return regex_star_height(r)
        case ConcatOmega(r1, r2):
            return max(regex_star_height(r1), omega_regex_star_height(r2))
        case UnionOmega(r1, r2):
            return max(omega_regex_star_height(r1), omega_regex_star_height(r2))
        case _:
            raise TypeError(f'Unknown omega regex type: {type(omega_regex)}')
        
if __name__ == "__main__":
    re_unit_test = Union(Symbol("a"), Concat(Star(Union(Symbol("d"), Concat(Symbol("c"), Star(Symbol("f"))))), Symbol("b")))


# 