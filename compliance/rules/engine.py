from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import operator
import re
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class RuleType(Enum):
    KYC = "kyc"
    AML = "aml"
    TRANSACTION_LIMIT = "transaction_limit"
    CUSTOM = "custom"


class RuleSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RuleAction(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"
    FLAG = "flag"
    ESCALATE = "escalate"


class EvaluationResult(Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class RuleMetadata:
    id: str
    name: str
    description: str
    rule_type: RuleType
    severity: RuleSeverity
    action_on_fail: RuleAction
    tags: Set[str] = field(default_factory=set)
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    enabled: bool = True
    priority: int = 0
    depends_on: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RuleCondition:
    field: str
    operator: str
    value: Any
    case_sensitive: bool = True


@dataclass(frozen=True)
class Rule:
    metadata: RuleMetadata
    conditions: List[RuleCondition] = field(default_factory=list)
    expression: Optional[str] = None
    custom_evaluator: Optional[str] = None


@dataclass
class EvaluationContext:
    entity_id: str
    entity_type: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_overrides: Dict[str, Any] = field(default_factory=dict)

    def get(self, path: str, default: Any = None) -> Any:
        keys = path.split(".")
        current = self.data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and key.isdigit():
                idx = int(key)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return default
            else:
                return default
        return current

    def set(self, path: str, value: Any) -> None:
        keys = path.split(".")
        current = self.data
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value


@dataclass
class RuleEvaluationResult:
    rule_id: str
    rule_name: str
    rule_type: RuleType
    result: EvaluationResult
    severity: RuleSeverity
    action: RuleAction
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    context_snapshot: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationSummary:
    request_id: str
    entity_id: str
    entity_type: str
    overall_result: EvaluationResult
    overall_action: RuleAction
    rule_results: List[RuleEvaluationResult]
    total_rules: int
    passed_rules: int
    failed_rules: int
    error_rules: int
    skipped_rules: int
    execution_time_ms: float
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class OperatorRegistry:
    _operators: Dict[str, Callable[[Any, Any], bool]] = {
        "eq": operator.eq,
        "ne": operator.ne,
        "gt": operator.gt,
        "gte": operator.ge,
        "lt": operator.lt,
        "lte": operator.le,
        "in": lambda a, b: a in b if isinstance(b, (list, tuple, set)) else False,
        "not_in": lambda a, b: a not in b if isinstance(b, (list, tuple, set)) else True,
        "contains": lambda a, b: b in a if isinstance(a, (str, list, tuple, set)) else False,
        "not_contains": lambda a, b: b not in a if isinstance(a, (str, list, tuple, set)) else True,
        "startswith": lambda a, b: isinstance(a, str) and a.startswith(b),
        "endswith": lambda a, b: isinstance(a, str) and a.endswith(b),
        "matches": lambda a, b: isinstance(a, str) and bool(re.match(b, a)),
        "regex": lambda a, b: isinstance(a, str) and bool(re.search(b, a)),
        "is_empty": lambda a, _: a is None or (isinstance(a, (str, list, dict, set)) and len(a) == 0),
        "is_not_empty": lambda a, _: a is not None and not (isinstance(a, (str, list, dict, set)) and len(a) == 0),
        "between": lambda a, b: isinstance(b, (list, tuple)) and len(b) == 2 and b[0] <= a <= b[1],
        "age_gt": lambda a, b: isinstance(a, (int, float)) and isinstance(b, (int, float)) and a > b,
        "age_gte": lambda a, b: isinstance(a, (int, float)) and isinstance(b, (int, float)) and a >= b,
        "age_lt": lambda a, b: isinstance(a, (int, float)) and isinstance(b, (int, float)) and a < b,
        "age_lte": lambda a, b: isinstance(a, (int, float)) and isinstance(b, (int, float)) and a <= b,
    }

    @classmethod
    def register(cls, name: str, func: Callable[[Any, Any], bool]) -> None:
        cls._operators[name] = func

    @classmethod
    def get(cls, name: str) -> Optional[Callable[[Any, Any], bool]]:
        return cls._operators.get(name)

    @classmethod
    def list_operators(cls) -> List[str]:
        return list(cls._operators.keys())


class SafeExpressionEvaluator:
    _ALLOWED_NODES = {
        "Expression", "BoolOp", "BinOp", "UnaryOp", "Compare", "Call",
        "Name", "Constant", "Attribute", "Subscript", "List", "Tuple",
        "Dict", "Set", "ListComp", "SetComp", "DictComp", "GeneratorExp",
        "IfExp", "Lambda", "JoinedStr", "FormattedValue"
    }
    _ALLOWED_OPS = {
        "Add", "Sub", "Mult", "Div", "FloorDiv", "Mod", "Pow",
        "LShift", "RShift", "BitOr", "BitXor", "BitAnd",
        "And", "Or", "Not",
        "Eq", "NotEq", "Lt", "LtE", "Gt", "GtE", "Is", "IsNot", "In", "NotIn",
        "UAdd", "USub", "Not", "Invert"
    }
    _ALLOWED_FUNCTIONS = {
        "len", "min", "max", "sum", "abs", "round", "str", "int", "float",
        "bool", "list", "dict", "set", "tuple", "sorted", "reversed",
        "any", "all", "isinstance", "hasattr", "getattr"
    }

    def __init__(self, context: EvaluationContext):
        self._context = context
        self._cache: Dict[str, Any] = {}

    def evaluate(self, expression: str) -> Any:
        cache_key = hashlib.md5(expression.encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            tree = self._parse(expression)
            self._validate(tree)
            result = self._eval(tree)
            self._cache[cache_key] = result
            return result
        except Exception as e:
            logger.error(f"Expression evaluation failed: {expression}, error: {e}")
            raise EvaluationError(f"Failed to evaluate expression: {expression}") from e

    def _parse(self, expression: str) -> ast.AST:
        import ast
        return ast.parse(expression, mode="eval")

    def _validate(self, node: ast.AST) -> None:
        import ast
        for child in ast.walk(node):
            if type(child).__name__ not in self._ALLOWED_NODES:
                raise EvaluationError(f"Disallowed AST node: {type(child).__name__}")
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    if child.func.id not in self._ALLOWED_FUNCTIONS:
                        raise EvaluationError(f"Disallowed function: {child.func.id}")
                elif isinstance(child.func, ast.Attribute):
                    raise EvaluationError("Method calls not allowed in expressions")
            if isinstance(child, ast.BinOp) and type(child.op).__name__ not in self._ALLOWED_OPS:
                raise EvaluationError(f"Disallowed binary operator: {type(child.op).__name__}")
            if isinstance(child, ast.UnaryOp) and type(child.op).__name__ not in self._ALLOWED_OPS:
                raise EvaluationError(f"Disallowed unary operator: {type(child.op).__name__}")
            if isinstance(child, ast.Compare):
                for op in child.ops:
                    if type(op).__name__ not in self._ALLOWED_OPS:
                        raise EvaluationError(f"Disallowed comparison operator: {type(op).__name__}")

    def _eval(self, node: ast.AST) -> Any:
        import ast
        if isinstance(node, ast.Expression):
            return self._eval(node.body)
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return self._context.get(node.id)
        elif isinstance(node, ast.Attribute):
            obj = self._eval(node.value)
            return getattr(obj, node.attr, None)
        elif isinstance(node, ast.Subscript):
            obj = self._eval(node.value)
            key = self._eval(node.slice) if isinstance(node.slice, ast.Index) else self._eval(node.slice)
            return obj[key] if isinstance(obj, (dict, list, tuple)) else None
        elif isinstance(node, ast.BinOp):
            left = self._eval(node.left)
            right = self._eval(node.right)
            return self._apply_binop(type(node.op).__name__, left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval(node.operand)
            return self._apply_unaryop(type(node.op).__name__, operand)
        elif isinstance(node, ast.BoolOp):
            values = [self._eval(v) for v in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            elif isinstance(node.op, ast.Or):
                return any(values)
        elif isinstance(node, ast.Compare):
            left = self._eval(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval(comparator)
                if not self._apply_compare(type(op).__name__, left, right):
                    return False
                left = right
            return True
        elif isinstance(node, ast.Call):
            func_name = node.func.id if isinstance(node.func, ast.Name) else None
            if func_name in self._ALLOWED_FUNCTIONS:
                args = [self._eval(arg) for arg in node.args]
                kwargs = {kw.arg: self._eval(kw.value) for kw in node.keywords}
                return getattr(__builtins__, func_name)(*args, **kwargs)
        elif isinstance(node, ast.List):
            return [self._eval(e) for e in node.elts]
        elif isinstance(node, ast.Tuple):
            return tuple(self._eval(e) for e in node.elts)
        elif isinstance(node, ast.Dict):
            return {self._eval(k): self._eval(v) for k, v in zip(node.keys, node.values)}
        elif isinstance(node, ast.Set):
            return {self._eval(e) for e in node.elts}
        elif isinstance(node, ast.IfExp):
            test = self._eval(node.test)
            return self._eval(node.body) if test else self._eval(node.orelse)
        elif isinstance(node, ast.Lambda):
            return lambda *args, **kwargs: None
        return None

    def _apply_binop(self, op_name: str, left: Any, right: Any) -> Any:
        ops = {
            "Add": operator.add, "Sub": operator.sub, "Mult": operator.mul,
            "Div": operator.truediv, "FloorDiv": operator.floordiv,
            "Mod": operator.mod, "Pow": operator.pow,
            "LShift": operator.lshift, "RShift": operator.rshift,
            "BitOr": operator.or_, "BitXor": operator.xor, "BitAnd": operator.and_,
        }
        return ops.get(op_name, lambda a, b: None)(left, right)

    def _apply_unaryop(self, op_name: str, operand: Any) -> Any:
        ops = {"UAdd": operator.pos, "USub": operator.neg, "Not": operator.not_, "Invert": operator.inv}
        return ops.get(op_name, lambda a: None)(operand)

    def _apply_compare(self, op_name: str, left: Any, right: Any) -> bool:
        ops = {
            "Eq": operator.eq, "NotEq": operator.ne, "Lt": operator.lt,
            "LtE": operator.le, "Gt": operator.gt, "GtE": operator.ge,
            "Is": operator.is_, "IsNot": operator.is_not,
            "In": lambda a, b: a in b, "NotIn": lambda a, b: a not in b,
        }
        return ops.get(op_name, lambda a, b: False)(left, right)


class EvaluationError(Exception):
    pass


class RuleRegistry:
    def __init__(self):
        self._rules: Dict[str, Rule] = {}
        self._by_type: Dict[RuleType, List[Rule]] = defaultdict(list)
        self._by_tag: Dict[str, List[Rule]] = defaultdict(list)
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)

    def register(self, rule: Rule) -> None:
        if rule.metadata.id in self._rules:
            raise ValueError(f"Rule with id {rule.metadata.id} already exists")
        self._rules[rule.metadata.id] = rule
        self._by_type[rule.metadata.rule_type].append(rule)
        for tag in rule.metadata.tags:
            self._by_tag[tag].append(rule)
        for dep in rule.metadata.depends_on:
            self._dependency_graph[rule.metadata.id].add(dep)
        logger.info(f"Registered rule: {rule.metadata.id} ({rule.metadata.name})")

    def unregister(self, rule_id: str) -> bool:
        rule = self._rules.pop(rule_id, None)
        if rule:
            self._by_type[rule.metadata.rule_type] = [r for r in self._by_type[rule.metadata.rule_type] if r.metadata.id != rule_id]
            for tag in rule.metadata.tags:
                self._by_tag[tag] = [r for r in self._by_tag[tag] if r.metadata.id != rule_id]
            self._dependency_graph.pop(rule_id, None)
            for deps in self._dependency_graph.values():
                deps.discard(rule_id)
            logger.info(f"Unregistered rule: {rule_id}")
            return True
        return False

    def get(self, rule_id: str) -> Optional[Rule]:
        return self._rules.get(rule_id)

    def get_by_type(self, rule_type: RuleType) -> List[Rule]:
        return self._by_type.get(rule_type, [])

    def get_by_tag(self, tag: str) -> List[Rule]: