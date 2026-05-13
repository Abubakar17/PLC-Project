"""Parser and evaluator for simple PLC boolean logic."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from timer import TonTimer


class LogicSyntaxError(Exception):
    """Syntax error that keeps track of the editor line number."""

    def __init__(self, message: str, line_no: int | None = None) -> None:
        super().__init__(message)
        self.line_no = line_no


TOKEN_RE = re.compile(r"\s*([A-Z_][A-Z0-9_\.]*|\(|\))", re.I)


class Expr:
    def eval(self, signals: Dict[str, Any]) -> bool:
        raise NotImplementedError


@dataclass
class Literal(Expr):
    value: bool

    def eval(self, signals: Dict[str, Any]) -> bool:
        return self.value


@dataclass
class Name(Expr):
    name: str

    def eval(self, signals: Dict[str, Any]) -> bool:
        return bool(signals.get(normalize(self.name), False))


@dataclass
class Unary(Expr):
    op: str
    expr: Expr

    def eval(self, signals: Dict[str, Any]) -> bool:
        if self.op == "NOT":
            return not self.expr.eval(signals)
        raise ValueError(f"Unknown unary operator {self.op}")


@dataclass
class Binary(Expr):
    op: str
    left: Expr
    right: Expr

    def eval(self, signals: Dict[str, Any]) -> bool:
        left = self.left.eval(signals)
        right = self.right.eval(signals)
        if self.op == "AND":
            return left and right
        if self.op == "OR":
            return left or right
        if self.op == "NAND":
            return not (left and right)
        if self.op == "NOR":
            return not (left or right)
        raise ValueError(f"Unknown binary operator {self.op}")


@dataclass
class Assignment:
    target: str
    expr: Expr
    line_no: int


@dataclass
class TimerAssignment:
    name: str
    input_expr: Expr
    delay_seconds: float
    line_no: int


class Parser:
    """Small recursive-descent parser for PLC boolean expressions."""

    def __init__(self, text: str, line_no: int) -> None:
        self.tokens = tokenize(text, line_no)
        self.index = 0
        self.line_no = line_no

    def parse(self) -> Expr:
        expr = self.parse_or_family()
        if self.peek() is not None:
            raise LogicSyntaxError(f"Unexpected token '{self.peek()}'", self.line_no)
        return expr

    def parse_or_family(self) -> Expr:
        expr = self.parse_and_family()
        while self.peek() in {"OR", "NOR"}:
            op = self.pop()
            expr = Binary(op, expr, self.parse_and_family())
        return expr

    def parse_and_family(self) -> Expr:
        expr = self.parse_not()
        while self.peek() in {"AND", "NAND"}:
            op = self.pop()
            expr = Binary(op, expr, self.parse_not())
        return expr

    def parse_not(self) -> Expr:
        if self.peek() == "NOT":
            return Unary(self.pop(), self.parse_not())
        return self.parse_primary()

    def parse_primary(self) -> Expr:
        token = self.peek()
        if token is None:
            raise LogicSyntaxError("Expected a signal name or expression", self.line_no)
        if token == "(":
            self.pop()
            expr = self.parse_or_family()
            self.expect(")")
            return expr
        token = self.pop()
        if token == "TRUE":
            return Literal(True)
        if token == "FALSE":
            return Literal(False)
        if re.match(r"^[A-Z_][A-Z0-9_\.]*$", token):
            return Name(token)
        raise LogicSyntaxError(f"Unexpected token '{token}'", self.line_no)

    def peek(self) -> str | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def pop(self) -> str:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def expect(self, expected: str) -> None:
        if self.peek() != expected:
            raise LogicSyntaxError(f"Expected '{expected}'", self.line_no)
        self.pop()


class LogicEngine:
    """Compiles user logic and evaluates it once per PLC scan."""

    def __init__(self) -> None:
        self.assignments: List[Assignment] = []
        self.timer_assignments: List[TimerAssignment] = []
        self.timers: Dict[str, TonTimer] = {}
        self.compiled = False

    def compile(self, program: str) -> None:
        self.compiled = False
        assignments: List[Assignment] = []
        timer_assignments: List[TimerAssignment] = []

        for line_no, raw_line in enumerate(program.splitlines(), start=1):
            line = strip_comment(raw_line).strip()
            if not line:
                continue
            if "=" not in line:
                raise LogicSyntaxError("Expected OUTPUT = EXPRESSION", line_no)
            left, right = line.split("=", 1)
            target = normalize(left)
            if not re.match(r"^[A-Z_][A-Z0-9_]*$", target):
                raise LogicSyntaxError(f"Invalid target name '{left.strip()}'", line_no)

            timer_match = re.match(r"^TIMER\s*\((.*),\s*([0-9]+(?:\.[0-9]+)?)\s*\)$", right.strip(), re.I)
            if timer_match:
                input_expr = Parser(timer_match.group(1), line_no).parse()
                delay = float(timer_match.group(2))
                if delay < 0:
                    raise LogicSyntaxError("Timer delay must be zero or greater", line_no)
                timer_assignments.append(TimerAssignment(target, input_expr, delay, line_no))
            else:
                assignments.append(Assignment(target, Parser(right, line_no).parse(), line_no))

        self.assignments = assignments
        self.timer_assignments = timer_assignments
        self._sync_timers()
        self.compiled = True

    def scan(self, signals: Dict[str, Any], dt: float) -> Dict[str, Any]:
        if not self.compiled:
            return signals

        working = {normalize(name): value for name, value in signals.items()}

        for timer_assignment in self.timer_assignments:
            timer = self.timers[timer_assignment.name]
            enabled = timer_assignment.input_expr.eval(working)
            timer.update(enabled, dt)
            working.update(timer.export_signals())

        for assignment in self.assignments:
            working[assignment.target] = assignment.expr.eval(working)

        return working

    def reset(self) -> None:
        for timer in self.timers.values():
            timer.reset()

    def timer_signal_snapshot(self) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        for timer in self.timers.values():
            values.update(timer.export_signals())
        return values

    def reset_program_signals(self) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        for assignment in self.assignments:
            values[assignment.target] = False
        for timer_assignment in self.timer_assignments:
            values[timer_assignment.name] = False
        values.update(self.timer_signal_snapshot())
        return values

    def _sync_timers(self) -> None:
        wanted = {item.name: item.delay_seconds for item in self.timer_assignments}
        self.timers = {
            name: self.timers.get(name, TonTimer(name, delay))
            for name, delay in wanted.items()
        }
        for name, delay in wanted.items():
            self.timers[name].delay_seconds = delay


def tokenize(text: str, line_no: int) -> Sequence[str]:
    tokens: list[str] = []
    position = 0
    while position < len(text):
        if text[position].isspace():
            position += 1
            continue
        match = TOKEN_RE.match(text, position)
        if not match:
            raise LogicSyntaxError(f"Could not parse near '{text[position:].strip()}'", line_no)
        tokens.append(match.group(1).upper().replace(".", "_"))
        position = match.end()
    return tokens


def strip_comment(line: str) -> str:
    return line.split("#", 1)[0]


def normalize(name: str) -> str:
    return name.strip().upper().replace(".", "_")
