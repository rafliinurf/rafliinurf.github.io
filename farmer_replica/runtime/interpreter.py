"""Interpreter AST terbatas untuk pemanggilan API game."""
import ast
import operator
from collections import ChainMap
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping


class InterpreterError(ValueError):
    """Script memakai sintaks atau API yang belum didukung."""


_STOPPED = object()
_UNBOUND = object()
_BINARY_OPERATORS = {
    ast.Add: ("+", operator.add),
    ast.Sub: ("-", operator.sub),
    ast.Mult: ("*", operator.mul),
    ast.Div: ("/", operator.truediv),
    ast.FloorDiv: ("//", operator.floordiv),
    ast.Mod: ("%", operator.mod),
    ast.Pow: ("**", operator.pow),
}
_COMPARISON_OPERATORS = {
    ast.Eq: ("==", operator.eq),
    ast.NotEq: ("!=", operator.ne),
    ast.Lt: ("<", operator.lt),
    ast.LtE: ("<=", operator.le),
    ast.Gt: (">", operator.gt),
    ast.GtE: (">=", operator.ge),
    ast.In: ("in", lambda key, collection: key in collection),
    ast.NotIn: ("not in", lambda key, collection: key not in collection),
}
_ARITHMETIC_OPERATOR_NAMES = frozenset(
    name for name, _ in _BINARY_OPERATORS.values()
)


@dataclass(frozen=True)
class ExecutionStep:
    line: int
    function: str
    args: tuple[Any, ...]
    result: Any
    column_start: int
    end_line: int
    column_end: int


@dataclass(frozen=True)
class _UserFunction:
    name: str
    definition: ast.FunctionDef
    defaults: tuple[Any, ...]


@dataclass(frozen=True)
class _ReturnSignal:
    value: Any


@dataclass(frozen=True)
class _LoopControl:
    kind: str


class Interpreter:
    def __init__(
        self,
        api: Mapping[str, Callable[..., Any]],
        statement_api: Mapping[str, Callable[..., Any]] | None = None,
        constants: Mapping[str, Any] | None = None,
        features: frozenset[str] | set[str] | None = None,
    ):
        self.api = dict(api)
        self.statement_api = dict(statement_api or {})
        self.constants = {
            name: dict(value) if isinstance(value, Mapping) else value
            for name, value in (constants or {}).items()
        }
        self.features = None if features is None else frozenset(features)
        self._function_signatures = {}

    def run(
        self,
        source: str,
        should_stop: Callable[[], bool] | None = None,
    ) -> Iterator[ExecutionStep]:
        self.source_lines = source.splitlines()
        statements = self._parse_program(source)
        yield from self._execute_statements(statements, should_stop, {})

    def _character_column(self, line, byte_column):
        source_line = self.source_lines[line - 1]
        return len(source_line.encode("utf-8")[:byte_column].decode("utf-8"))

    def _span(self, node):
        return (
            self._character_column(node.lineno, node.col_offset),
            node.end_lineno,
            self._character_column(node.end_lineno, node.end_col_offset),
        )

    def _header_span(self, node):
        end_line = node.test.end_lineno
        end_byte_column = node.test.end_col_offset + 1
        return (
            self._character_column(node.lineno, node.col_offset),
            end_line,
            self._character_column(end_line, end_byte_column),
        )

    def _for_header_span(self, node):
        end_line = node.iter.end_lineno
        end_byte_column = node.iter.end_col_offset + 1
        return (
            self._character_column(node.lineno, node.col_offset),
            end_line,
            self._character_column(end_line, end_byte_column),
        )

    def _parse_program(self, source: str) -> list[ast.stmt]:
        try:
            tree = ast.parse(source, mode="exec")
        except SyntaxError as exc:
            raise InterpreterError(str(exc)) from exc

        self._function_signatures = {}
        self._validate_statements(tree.body, set())
        return tree.body

    def _validate_statements(
        self,
        statements: list[ast.stmt],
        variables: set[str],
        in_function: bool = False,
        allow_function_definitions: bool = True,
        loop_depth: int = 0,
    ) -> set[str]:
        defined = set(variables)
        for statement in statements:
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                self._validate_call(statement.value, defined)
            elif isinstance(statement, ast.Assign):
                if len(statement.targets) != 1 or not isinstance(
                    statement.targets[0],
                    ast.Name,
                ):
                    raise InterpreterError("assignment hanya mendukung satu nama")
                if self.features is not None and "variables" not in self.features:
                    raise InterpreterError("Variables belum di-unlock")
                target = statement.targets[0]
                name = target.id
                if name in self.api or name in self.constants or name in self.statement_api:
                    raise InterpreterError("nama tersebut sudah dipakai oleh API game")
                if name in self._function_signatures:
                    raise InterpreterError("nama fungsi tidak dapat ditimpa")
                self._validate_value_expression(statement.value, defined)
                defined.add(target.id)
            elif isinstance(statement, ast.FunctionDef):
                if not allow_function_definitions:
                    raise InterpreterError("def bersarang belum didukung")
                if self.features is not None and "functions" not in self.features:
                    raise InterpreterError("Functions belum di-unlock")
                if (
                    statement.decorator_list
                    or statement.returns is not None
                    or statement.type_comment is not None
                    or statement.args.posonlyargs
                    or statement.args.kwonlyargs
                    or statement.args.vararg is not None
                    or statement.args.kwarg is not None
                    or statement.args.kw_defaults
                ):
                    raise InterpreterError(
                        "function hanya mendukung parameter positional"
                    )
                name = statement.name
                if (
                    name in self.api
                    or name in self.constants
                    or name in self.statement_api
                    or name in self._function_signatures
                    or name in defined
                ):
                    raise InterpreterError("nama fungsi sudah dipakai")
                parameters = [argument.arg for argument in statement.args.args]
                if len(parameters) != len(set(parameters)):
                    raise InterpreterError("nama parameter fungsi harus unik")
                for default in statement.args.defaults:
                    self._validate_value_expression(default, defined)
                required_parameters = len(parameters) - len(statement.args.defaults)
                self._function_signatures[name] = (
                    required_parameters,
                    len(parameters),
                )
                local_names = self._function_local_names(statement.body)
                function_variables = (defined - local_names) | set(parameters)
                self._validate_statements(
                    statement.body,
                    function_variables,
                    in_function=True,
                    allow_function_definitions=False,
                    loop_depth=0,
                )
                defined.add(name)
            elif isinstance(statement, ast.For):
                if "for" not in self.statement_api:
                    raise InterpreterError("biaya tick untuk for belum dikonfigurasi")
                if not isinstance(statement.target, ast.Name) or statement.orelse:
                    raise InterpreterError("for hanya mendukung satu nama dan tanpa else")
                if (
                    statement.target.id in self.api
                    or statement.target.id in self.constants
                    or statement.target.id in self.statement_api
                ):
                    raise InterpreterError("nama loop sudah dipakai oleh API game")
                if isinstance(statement.iter, ast.Call) and isinstance(
                    statement.iter.func, ast.Name
                ) and statement.iter.func.id == "range":
                    self._validate_call(statement.iter, defined)
                elif (
                    self.features is not None
                    and ("lists" in self.features or "dictionaries" in self.features)
                    and (
                        isinstance(statement.iter, ast.List)
                        or isinstance(statement.iter, ast.Tuple)
                        or (
                            isinstance(statement.iter, ast.Name)
                            and statement.iter.id in defined
                        )
                    )
                ):
                    self._validate_value_expression(statement.iter, defined)
                else:
                    raise InterpreterError(
                        "for hanya mendukung range() atau collection yang sudah di-unlock"
                    )
                self._validate_statements(
                    statement.body,
                    defined | {statement.target.id},
                    in_function=in_function,
                    allow_function_definitions=False,
                    loop_depth=loop_depth + 1,
                )
            elif isinstance(statement, ast.While):
                if "while" not in self.statement_api:
                    raise InterpreterError("while belum di-unlock")
                self._validate_expression(statement.test, defined)
                self._validate_statements(
                    statement.body,
                    defined,
                    in_function=in_function,
                    allow_function_definitions=False,
                    loop_depth=loop_depth + 1,
                )
                if statement.orelse:
                    raise InterpreterError("while else belum didukung")
            elif isinstance(statement, ast.If):
                if "if" not in self.statement_api:
                    raise InterpreterError("biaya tick untuk if belum dikonfigurasi")
                self._validate_expression(statement.test, defined)
                body_variables = self._validate_statements(
                    statement.body,
                    defined,
                    in_function=in_function,
                    allow_function_definitions=False,
                    loop_depth=loop_depth,
                )
                else_variables = self._validate_statements(
                    statement.orelse,
                    defined,
                    in_function=in_function,
                    allow_function_definitions=False,
                    loop_depth=loop_depth,
                )
                if statement.orelse:
                    defined.update(body_variables & else_variables)
            elif isinstance(statement, (ast.Break, ast.Continue)):
                if loop_depth == 0:
                    keyword = "break" if isinstance(statement, ast.Break) else "continue"
                    raise InterpreterError(f"{keyword} hanya boleh digunakan di dalam loop")
            elif isinstance(statement, ast.Return):
                if not in_function:
                    raise InterpreterError("return hanya boleh digunakan di dalam function")
                if statement.value is not None:
                    self._validate_value_expression(statement.value, defined)
            else:
                raise InterpreterError(
                    "statement ini belum didukung oleh interpreter"
                )
        return defined

    @staticmethod
    def _function_local_names(statements):
        names = set()
        for statement in statements:
            if isinstance(statement, ast.Assign):
                names.add(statement.targets[0].id)
            elif isinstance(statement, ast.For):
                names.add(statement.target.id)
                names.update(Interpreter._function_local_names(statement.body))
            elif isinstance(statement, (ast.If, ast.While)):
                names.update(Interpreter._function_local_names(statement.body))
                names.update(Interpreter._function_local_names(statement.orelse))
        return names

    def _validate_expression(self, expression: ast.expr, variables: set[str]) -> None:
        if isinstance(expression, ast.Call):
            self._validate_call(expression, variables)
        elif isinstance(expression, ast.Constant) and isinstance(expression.value, bool):
            return
        elif isinstance(expression, ast.Name):
            self._validate_value_expression(expression, variables)
        elif isinstance(expression, ast.UnaryOp) and isinstance(
            expression.op,
            (ast.Not, ast.UAdd, ast.USub),
        ):
            self._require_operators()
            self._validate_value_expression(expression.operand, variables)
        elif isinstance(expression, ast.BinOp) and type(expression.op) in _BINARY_OPERATORS:
            self._require_operator(_BINARY_OPERATORS[type(expression.op)][0])
            self._validate_value_expression(expression.left, variables)
            self._validate_value_expression(expression.right, variables)
        elif isinstance(expression, ast.BoolOp) and isinstance(
            expression.op,
            (ast.And, ast.Or),
        ):
            self._require_operator(
                "and" if isinstance(expression.op, ast.And) else "or"
            )
            for value in expression.values:
                self._validate_value_expression(value, variables)
        elif (
            isinstance(expression, ast.Compare)
            and len(expression.ops) == 1
            and type(expression.ops[0]) in _COMPARISON_OPERATORS
        ):
            if isinstance(expression.ops[0], (ast.In, ast.NotIn)):
                if self.features is not None and not (
                    "lists" in self.features or "dictionaries" in self.features
                ):
                    raise InterpreterError("Lists atau Dictionaries belum di-unlock")
            else:
                self._require_operator(
                    _COMPARISON_OPERATORS[type(expression.ops[0])][0]
                )
            self._validate_value_expression(expression.left, variables)
            self._validate_value_expression(expression.comparators[0], variables)
        else:
            raise InterpreterError("kondisi if tidak didukung")

    def _require_operators(self):
        if self.features is not None and "operators" not in self.features:
            raise InterpreterError("Operators belum di-unlock")

    def _require_operator(self, name):
        self._require_operators()
        if name not in self.statement_api:
            raise InterpreterError(f"biaya tick untuk {name} belum dikonfigurasi")

    def _validate_value_expression(self, expression: ast.expr, variables: set[str]) -> None:
        if isinstance(expression, ast.Call):
            self._validate_call(expression, variables)
        elif isinstance(expression, ast.Constant) and isinstance(
            expression.value, (str, int, float, bool, type(None))
        ):
            return
        elif isinstance(expression, ast.List):
            if self.features is not None and "lists" not in self.features:
                raise InterpreterError("Lists belum di-unlock")
            for element in expression.elts:
                self._validate_value_expression(element, variables)
        elif isinstance(expression, ast.Tuple):
            if self.features is not None and "lists" not in self.features:
                raise InterpreterError("Lists belum di-unlock")
            for element in expression.elts:
                self._validate_value_expression(element, variables)
        elif isinstance(expression, ast.Slice):
            if self.features is not None and "lists" not in self.features:
                raise InterpreterError("Lists belum di-unlock")
            for bound in (expression.lower, expression.upper, expression.step):
                if bound is not None:
                    self._validate_value_expression(bound, variables)
        elif isinstance(expression, ast.Dict):
            if self.features is not None and "dictionaries" not in self.features:
                raise InterpreterError("Dictionaries belum di-unlock")
            for key, value in zip(expression.keys, expression.values):
                if key is None:
                    raise InterpreterError("dictionary unpacking belum didukung")
                self._validate_value_expression(key, variables)
                self._validate_value_expression(value, variables)
        elif isinstance(expression, ast.Set):
            raise InterpreterError(
                "set literal belum didukung; gunakan set(list) yang sudah di-unlock"
            )
        elif isinstance(expression, ast.Subscript):
            if self.features is not None and not (
                "lists" in self.features or "dictionaries" in self.features
            ):
                raise InterpreterError("Lists atau Dictionaries belum di-unlock")
            self._validate_value_expression(expression.value, variables)
            self._validate_value_expression(expression.slice, variables)
        elif isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name):
            namespace = self.constants.get(expression.value.id)
            if namespace is None or expression.attr not in namespace:
                raise InterpreterError("konstanta tidak tersedia")
        elif isinstance(expression, ast.Name) and expression.id in variables:
            return
        elif isinstance(expression, ast.Name) and expression.id in self.constants and not isinstance(
            self.constants[expression.id], Mapping
        ):
            return
        elif isinstance(
            expression,
            (ast.BinOp, ast.BoolOp, ast.Compare, ast.UnaryOp),
        ):
            self._validate_expression(expression, variables)
        else:
            raise InterpreterError("nilai pembanding tidak didukung")

    def _validate_call(
        self,
        call: ast.Call,
        variables: set[str] | None = None,
    ) -> None:
        if call.keywords:
            raise InterpreterError("argumen keyword belum didukung")
        variables = variables or set()
        if isinstance(call.func, ast.Attribute):
            if (
                self.features is not None
                and "lists" not in self.features
            ):
                raise InterpreterError("Lists belum di-unlock")
            if (
                not isinstance(call.func.value, ast.Name)
                or call.func.value.id not in variables
                or call.func.attr not in {"insert", "remove"}
            ):
                raise InterpreterError("method list tidak tersedia")
            expected_args = 2 if call.func.attr == "insert" else 1
            if len(call.args) != expected_args:
                raise InterpreterError(
                    f"list.{call.func.attr}() membutuhkan {expected_args} argumen"
                )
            for argument in call.args:
                self._validate_value_expression(argument, variables)
            return
        if not isinstance(call.func, ast.Name):
            raise InterpreterError("fungsi tidak tersedia di API player")
        if call.func.id in self._function_signatures:
            minimum_args, maximum_args = self._function_signatures[call.func.id]
            if not minimum_args <= len(call.args) <= maximum_args:
                raise InterpreterError(
                    f"{call.func.id}() membutuhkan {minimum_args} sampai "
                    f"{maximum_args} argumen"
                )
            for argument in call.args:
                self._validate_value_expression(argument, variables)
            return
        if call.func.id in variables:
            for argument in call.args:
                self._validate_value_expression(argument, variables)
            return
        if call.func.id not in self.api:
            raise InterpreterError("fungsi tidak tersedia di API player")
        if call.func.id == "set" and (
            len(call.args) != 1
            or (
                self.features is not None
                and "dictionaries" not in self.features
            )
        ):
            raise InterpreterError(
                "set() membutuhkan satu list dan Dictionaries harus di-unlock"
            )
        if call.func.id == "list" and (
            len(call.args) != 1
            or (
                self.features is not None
                and "lists" not in self.features
            )
        ):
            raise InterpreterError("list() membutuhkan satu collection dan Lists harus di-unlock")
        for argument in call.args:
            if isinstance(argument, ast.Call):
                self._validate_call(argument, variables)
            else:
                self._validate_value_expression(argument, variables)
        if call.func.id == "len" and (
            len(call.args) != 1
            or (
                self.features is not None
                and "lists" not in self.features
            )
        ):
            raise InterpreterError("len() membutuhkan satu list dan Lists harus di-unlock")
        if call.func.id == "range":
            if not 1 <= len(call.args) <= 3 or any(
                not self._is_integer_expression(argument, variables)
                for argument in call.args
            ):
                raise InterpreterError("range() membutuhkan 1 sampai 3 argumen integer")

    def _is_integer_expression(self, expression, variables):
        if isinstance(expression, ast.Call):
            return expression.func.id in {
                "get_world_size",
                "get_pos_x",
                "get_pos_y",
                "num_items",
                "num_unlocked",
            }
        if isinstance(expression, ast.Name) and expression.id in variables:
            return True
        try:
            value = self._literal_argument(expression)
        except (ValueError, TypeError, KeyError):
            return False
        return isinstance(value, int) and not isinstance(value, bool)

    def _literal_argument(self, expression: ast.expr) -> Any:
        try:
            return ast.literal_eval(expression)
        except (ValueError, TypeError):
            pass
        if isinstance(expression, ast.Name):
            value = self.constants.get(expression.id)
            if value is not None and not isinstance(value, Mapping):
                return value
        if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name):
            namespace = self.constants.get(expression.value.id)
            if isinstance(namespace, Mapping) and expression.attr in namespace:
                return namespace[expression.attr]
        raise ValueError("argument must be a literal or unlocked game constant")

    def _execute_statements(
        self,
        statements: list[ast.stmt],
        should_stop: Callable[[], bool] | None,
        variables: dict[str, Any],
    ) -> Iterator[ExecutionStep]:
        for statement in statements:
            if isinstance(statement, ast.Expr):
                result = yield from self._execute_call(
                    statement.value,
                    should_stop,
                    variables,
                )
            elif isinstance(statement, ast.Assign):
                value = yield from self._evaluate_value_expression(
                    statement.value,
                    should_stop,
                    variables,
                )
                if value is _STOPPED:
                    return _STOPPED
                target = statement.targets[0]
                variables[target.id] = value
                result = None
            elif isinstance(statement, ast.FunctionDef):
                defaults = []
                for default in statement.args.defaults:
                    value = yield from self._evaluate_value_expression(
                        default,
                        should_stop,
                        variables,
                    )
                    if value is _STOPPED:
                        return _STOPPED
                    defaults.append(value)
                function = _UserFunction(statement.name, statement, tuple(defaults))
                variables[statement.name] = function
                result = yield from self._execute_operation(
                    statement.lineno,
                    "function_definition",
                    (statement.name,),
                    iter(self.statement_api["function_definition"]()),
                    should_stop,
                    *self._span(statement),
                )
            elif isinstance(statement, ast.For):
                if isinstance(statement.iter, ast.Call):
                    values = yield from self._execute_call(
                        statement.iter,
                        should_stop,
                        variables,
                    )
                else:
                    values = yield from self._evaluate_value_expression(
                        statement.iter,
                        should_stop,
                        variables,
                    )
                if values is _STOPPED:
                    return _STOPPED
                if not isinstance(values, (range, list, tuple, dict, set)):
                    raise InterpreterError("for membutuhkan range() atau collection")
                result = yield from self._execute_operation(
                    statement.lineno,
                    "for",
                    (),
                    iter(self.statement_api["for"]()),
                    should_stop,
                    *self._for_header_span(statement),
                )
                if result is _STOPPED:
                    return _STOPPED
                for value in values:
                    variables[statement.target.id] = value
                    result = yield from self._execute_statements(
                        statement.body,
                        should_stop,
                        variables,
                    )
                    if result is _STOPPED:
                        return _STOPPED
                    if isinstance(result, _ReturnSignal):
                        return result
                    if isinstance(result, _LoopControl):
                        if result.kind == "break":
                            result = None
                            break
                        continue
            elif isinstance(statement, ast.While):
                while True:
                    result = yield from self._execute_operation(
                        statement.lineno,
                        "while",
                        (),
                        iter(self.statement_api["while"]()),
                        should_stop,
                        *self._header_span(statement),
                    )
                    if result is _STOPPED:
                        return _STOPPED
                    condition = yield from self._evaluate_expression(
                        statement.test,
                        should_stop,
                        variables,
                    )
                    if condition is _STOPPED:
                        return _STOPPED
                    if not condition:
                        break
                    result = yield from self._execute_statements(
                        statement.body,
                        should_stop,
                        variables,
                    )
                    if result is _STOPPED:
                        return _STOPPED
                    if isinstance(result, _ReturnSignal):
                        return result
                    if isinstance(result, _LoopControl):
                        if result.kind == "break":
                            result = None
                            break
                        continue
            elif isinstance(statement, ast.If):
                condition = yield from self._evaluate_expression(
                    statement.test,
                    should_stop,
                    variables,
                )
                if condition is _STOPPED:
                    return _STOPPED
                result = yield from self._execute_operation(
                    statement.lineno,
                    "if",
                    (),
                    iter(self.statement_api["if"]()),
                    should_stop,
                    *self._header_span(statement),
                )
                if result is _STOPPED:
                    return _STOPPED
                branch = statement.body if condition else statement.orelse
                result = yield from self._execute_statements(branch, should_stop, variables)
            elif isinstance(statement, ast.Return):
                value = None
                if statement.value is not None:
                    value = yield from self._evaluate_value_expression(
                        statement.value,
                        should_stop,
                        variables,
                    )
                    if value is _STOPPED:
                        return _STOPPED
                return _ReturnSignal(value)
            elif isinstance(statement, ast.Break):
                return _LoopControl("break")
            elif isinstance(statement, ast.Continue):
                return _LoopControl("continue")
            if result is _STOPPED:
                return _STOPPED
            if isinstance(result, (_ReturnSignal, _LoopControl)):
                return result

    def _evaluate_expression(
        self,
        expression: ast.expr,
        should_stop: Callable[[], bool] | None,
        variables: dict[str, Any],
    ) -> Iterator[ExecutionStep]:
        if isinstance(expression, ast.Call):
            return (yield from self._execute_call(expression, should_stop, variables))
        if isinstance(expression, ast.Constant):
            return expression.value
        if isinstance(expression, ast.UnaryOp) and isinstance(
            expression.op,
            (ast.Not, ast.UAdd, ast.USub),
        ):
            value = yield from self._evaluate_expression(
                expression.operand,
                should_stop,
                variables,
            )
            if value is _STOPPED:
                return _STOPPED
            if isinstance(expression.op, ast.Not):
                return not value
            if not self._is_number(value):
                raise InterpreterError("operator unary hanya menerima angka")
            try:
                value = float(value)
            except OverflowError as exc:
                raise InterpreterError(f"operator unary gagal: {exc}") from exc
            return value if isinstance(expression.op, ast.UAdd) else -value
        if isinstance(expression, ast.Name):
            return (yield from self._evaluate_value_expression(
                expression,
                should_stop,
                variables,
            ))
        if isinstance(expression, ast.BinOp) and type(expression.op) in _BINARY_OPERATORS:
            name, operation = _BINARY_OPERATORS[type(expression.op)]
            left = yield from self._evaluate_value_expression(
                expression.left, should_stop, variables
            )
            if left is _STOPPED:
                return _STOPPED
            right = yield from self._evaluate_value_expression(
                expression.right, should_stop, variables
            )
            if right is _STOPPED:
                return _STOPPED
            if name == "+" and isinstance(left, (list, tuple, str)) and type(left) is type(right):
                if isinstance(left, (list, tuple)) and (
                    self.features is not None and "lists" not in self.features
                ):
                    raise InterpreterError("Lists belum di-unlock")
                result = left + right
                operation_result = yield from self._execute_operation(
                    expression.lineno,
                    "collection_concat",
                    (left, right),
                    iter(self.statement_api["collection_concat"](
                        result,
                        len(left),
                        length=len(right),
                    )),
                    should_stop,
                    *self._span(expression),
                )
                if operation_result is _STOPPED:
                    return _STOPPED
                return result
            if not self._is_number(left) or not self._is_number(right):
                raise InterpreterError(f"operator {name} hanya menerima angka")
            try:
                left, right = float(left), float(right)
            except OverflowError as exc:
                raise InterpreterError(f"operator {name} gagal: {exc}") from exc
            result = self._apply_operator(operation, name, left, right)
            operation_result = yield from self._execute_operation(
                expression.lineno,
                name,
                (left, right),
                iter(self.statement_api[name]()),
                should_stop,
                *self._span(expression),
            )
            if operation_result is _STOPPED:
                return _STOPPED
            return result
        if isinstance(expression, ast.BoolOp):
            values = iter(expression.values)
            result = yield from self._evaluate_expression(
                next(values),
                should_stop,
                variables,
            )
            if result is _STOPPED:
                return _STOPPED
            name = "and" if isinstance(expression.op, ast.And) else "or"
            for value_expression in values:
                if (name == "and" and not result) or (name == "or" and result):
                    operation_result = yield from self._execute_operation(
                        expression.lineno,
                        name,
                        (),
                        iter(self.statement_api[name]()),
                        should_stop,
                        *self._span(expression),
                    )
                    if operation_result is _STOPPED:
                        return _STOPPED
                    break
                right = yield from self._evaluate_expression(
                    value_expression,
                    should_stop,
                    variables,
                )
                if right is _STOPPED:
                    return _STOPPED
                result = right
                operation_result = yield from self._execute_operation(
                    expression.lineno,
                    name,
                    (),
                    iter(self.statement_api[name]()),
                    should_stop,
                    *self._span(expression),
                )
                if operation_result is _STOPPED:
                    return _STOPPED
            return result
        if (
            isinstance(expression, ast.Compare)
            and len(expression.ops) == 1
            and type(expression.ops[0]) in _COMPARISON_OPERATORS
        ):
            name, operation = _COMPARISON_OPERATORS[type(expression.ops[0])]
            left = yield from self._evaluate_value_expression(
                expression.left, should_stop, variables
            )
            if left is _STOPPED:
                return _STOPPED
            right = yield from self._evaluate_value_expression(
                expression.comparators[0], should_stop, variables
            )
            if right is _STOPPED:
                return _STOPPED
            if name in {"in", "not in"}:
                if not isinstance(right, (dict, set, list, tuple)):
                    raise InterpreterError(
                        "in hanya mendukung list, tuple, dictionary, atau set"
                    )
                try:
                    result = operation(left, right)
                    if isinstance(right, (list, tuple)):
                        try:
                            index = right.index(left)
                        except ValueError:
                            index = len(right)
                        lookup_name = "list_membership"
                        cost_args = (result, 0, index)
                    else:
                        lookup_name = (
                            "dictionary_membership"
                            if isinstance(right, dict)
                            else "dictionary_lookup"
                        )
                        cost_args = (result, 0, 0, left)
                    operation_result = yield from self._execute_operation(
                        expression.lineno,
                        lookup_name,
                        (left,),
                        iter(self.statement_api[lookup_name](*cost_args)),
                        should_stop,
                        *self._span(expression),
                    )
                except TypeError as exc:
                    raise InterpreterError(f"membership lookup gagal: {exc}") from exc
                if operation_result is _STOPPED:
                    return _STOPPED
                return result
            if name in {"<", "<=", ">", ">="} and (
                not self._is_number(left) or not self._is_number(right)
            ):
                raise InterpreterError(f"operator {name} hanya membandingkan angka")
            if isinstance(left, (list, tuple, dict, set)) or isinstance(
                right, (list, tuple, dict, set)
            ):
                raise InterpreterError("comparison collection belum didukung")
            if self._is_number(left) and self._is_number(right):
                try:
                    left, right = float(left), float(right)
                except OverflowError as exc:
                    raise InterpreterError(f"operator {name} gagal: {exc}") from exc
            result = self._apply_operator(operation, name, left, right)
            operation = yield from self._execute_operation(
                expression.lineno,
                name,
                (left, right),
                iter(self.statement_api[name]()),
                should_stop,
                *self._span(expression),
            )
            if operation is _STOPPED:
                return _STOPPED
            return result
        raise InterpreterError("kondisi if tidak didukung")

    @staticmethod
    def _is_number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    @staticmethod
    def _apply_operator(operation, name, left, right):
        try:
            result = operation(left, right)
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise InterpreterError(f"operator {name} gagal: {exc}") from exc
        if name in _ARITHMETIC_OPERATOR_NAMES and not Interpreter._is_number(result):
            raise InterpreterError(f"operator {name} harus menghasilkan angka real")
        return result

    def _evaluate_value_expression(
        self,
        expression: ast.expr,
        should_stop: Callable[[], bool] | None,
        variables: dict[str, Any],
    ) -> Iterator[ExecutionStep]:
        if isinstance(expression, ast.Call):
            return (yield from self._execute_call(expression, should_stop, variables))
        if isinstance(
            expression,
            (ast.BinOp, ast.BoolOp, ast.Compare, ast.UnaryOp),
        ):
            return (yield from self._evaluate_expression(
                expression,
                should_stop,
                variables,
            ))
        if isinstance(expression, ast.Constant):
            return expression.value
        if isinstance(expression, ast.List):
            values = []
            for element in expression.elts:
                value = yield from self._evaluate_value_expression(
                    element,
                    should_stop,
                    variables,
                )
                if value is _STOPPED:
                    return _STOPPED
                values.append(value)
            return (yield from self._execute_operation(
                expression.lineno,
                "list_literal",
                tuple(values),
                iter(self.statement_api["list_literal"](
                    values,
                    len(values),
                )),
                should_stop,
                *self._span(expression),
            ))
        if isinstance(expression, ast.Tuple):
            values = []
            for element in expression.elts:
                value = yield from self._evaluate_value_expression(
                    element,
                    should_stop,
                    variables,
                )
                if value is _STOPPED:
                    return _STOPPED
                values.append(value)
            return (yield from self._execute_operation(
                expression.lineno,
                "tuple_literal",
                tuple(values),
                iter(self.statement_api["tuple_literal"](
                    tuple(values),
                    len(values),
                )),
                should_stop,
                *self._span(expression),
            ))
        if isinstance(expression, ast.Dict):
            mapping = {}
            for key_expression, value_expression in zip(
                expression.keys,
                expression.values,
            ):
                key = yield from self._evaluate_value_expression(
                    key_expression,
                    should_stop,
                    variables,
                )
                if key is _STOPPED:
                    return _STOPPED
                value = yield from self._evaluate_value_expression(
                    value_expression,
                    should_stop,
                    variables,
                )
                if value is _STOPPED:
                    return _STOPPED
                try:
                    mapping[key] = value
                except TypeError as exc:
                    raise InterpreterError(
                        "dictionary keys must be hashable"
                    ) from exc
            return (yield from self._execute_operation(
                expression.lineno,
                "dictionary_literal",
                tuple(mapping.items()),
                iter(self.statement_api["dictionary_literal"](
                    mapping,
                    len(expression.keys),
                )),
                should_stop,
                *self._span(expression),
            ))
        if isinstance(expression, ast.Subscript):
            sequence = yield from self._evaluate_value_expression(
                expression.value,
                should_stop,
                variables,
            )
            if sequence is _STOPPED:
                return _STOPPED
            index = None
            if not isinstance(expression.slice, ast.Slice):
                index = yield from self._evaluate_value_expression(
                    expression.slice,
                    should_stop,
                    variables,
                )
                if index is _STOPPED:
                    return _STOPPED
            if isinstance(expression.slice, ast.Slice):
                if not isinstance(sequence, list):
                    raise InterpreterError("slicing hanya mendukung list")
                bounds = []
                for bound in (
                    expression.slice.lower,
                    expression.slice.upper,
                    expression.slice.step,
                ):
                    if bound is None:
                        bounds.append(None)
                        continue
                    value = yield from self._evaluate_value_expression(
                        bound,
                        should_stop,
                        variables,
                    )
                    if value is _STOPPED:
                        return _STOPPED
                    if isinstance(value, bool) or not isinstance(value, int):
                        raise InterpreterError("slice membutuhkan integer")
                    bounds.append(value)
                try:
                    result = sequence[slice(*bounds)]
                except ValueError as exc:
                    raise InterpreterError(f"slice gagal: {exc}") from exc
                return (yield from self._execute_operation(
                    expression.lineno,
                    "list_slice",
                    (result,),
                    iter(self.statement_api["list_slice"](
                        result,
                        length=len(result),
                    )),
                    should_stop,
                    *self._span(expression),
                ))
            if isinstance(sequence, (list, tuple)):
                if isinstance(index, bool) or not isinstance(index, int):
                    target = "list" if isinstance(sequence, list) else "tuple"
                    raise InterpreterError(f"indeks {target} membutuhkan integer")
                try:
                    result = sequence[index]
                except IndexError as exc:
                    raise InterpreterError(
                        f"indeks {'list' if isinstance(sequence, list) else 'tuple'} "
                        f"di luar jangkauan: {index}"
                    ) from exc
                return (yield from self._execute_operation(
                    expression.lineno,
                    "list_index",
                    (index,),
                    iter(self.statement_api["list_index"](result)),
                    should_stop,
                    *self._span(expression),
                ))
            if isinstance(sequence, dict):
                try:
                    result = sequence[index]
                    operation = self.statement_api["dictionary_lookup"]
                    return (yield from self._execute_operation(
                        expression.lineno,
                        "dictionary_lookup",
                        (index,),
                        iter(operation(result, key=index)),
                        should_stop,
                        *self._span(expression),
                    ))
                except KeyError as exc:
                    raise InterpreterError(
                        f"dictionary key tidak ditemukan: {index}"
                    ) from exc
                except TypeError as exc:
                    raise InterpreterError(f"dictionary lookup gagal: {exc}") from exc
            raise InterpreterError(
                "indexing hanya mendukung list, tuple, atau dictionary"
            )
        if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name):
            namespace = self.constants[expression.value.id]
            if not isinstance(namespace, Mapping):
                raise InterpreterError("konstanta tidak tersedia")
            return namespace[expression.attr]
        if isinstance(expression, ast.Name):
            if expression.id in variables:
                value = variables[expression.id]
                if value is _UNBOUND:
                    raise InterpreterError(
                        f"variabel lokal belum diberi nilai: {expression.id}"
                    )
                return value
            value = self.constants.get(expression.id)
            if value is not None and not isinstance(value, Mapping):
                return value
            raise InterpreterError("konstanta tidak tersedia")
        raise InterpreterError("nilai pembanding tidak didukung")

    def _execute_call(
        self,
        call: ast.Call,
        should_stop: Callable[[], bool] | None,
        variables: dict[str, Any],
    ) -> Iterator[ExecutionStep]:
        if isinstance(call.func, ast.Attribute):
            sequence = variables.get(call.func.value.id)
            if not isinstance(sequence, list):
                raise InterpreterError("method list hanya tersedia untuk list")
            args = []
            for expression in call.args:
                value = yield from self._evaluate_value_expression(
                    expression,
                    should_stop,
                    variables,
                )
                if value is _STOPPED:
                    return _STOPPED
                args.append(value)

            original_length = len(sequence)
            if call.func.attr == "insert":
                index, value = args
                if (
                    isinstance(index, bool)
                    or not isinstance(index, int)
                    or not 0 <= index <= original_length
                ):
                    raise InterpreterError(
                        "list.insert() membutuhkan indeks integer antara 0 dan panjang list"
                    )
                sequence.insert(index, value)
                operation_name = "list_insert"
            else:
                value = args[0]
                try:
                    index = sequence.index(value)
                except ValueError as exc:
                    raise InterpreterError(
                        "list.remove() tidak menemukan nilai tersebut"
                    ) from exc
                sequence.pop(index)
                operation_name = "list_remove"

            return (yield from self._execute_operation(
                call.lineno,
                operation_name,
                tuple(args),
                iter(self.statement_api[operation_name](
                    None,
                    original_length,
                    index if operation_name == "list_insert" else 0,
                )),
                should_stop,
                *self._span(call),
            ))

        name = call.func.id
        function = variables.get(name)
        if name in variables and not isinstance(function, _UserFunction):
            raise InterpreterError(f"nilai {name} bukan function yang dapat dipanggil")
        if isinstance(function, _UserFunction):
            args = []
            for expression in call.args:
                value = yield from self._evaluate_value_expression(
                    expression,
                    should_stop,
                    variables,
                )
                if value is _STOPPED:
                    return _STOPPED
                args.append(value)
            parameters = [
                argument.arg
                for argument in function.definition.args.args
            ]
            required_args = len(parameters) - len(function.defaults)
            if not required_args <= len(args) <= len(parameters):
                raise InterpreterError(
                    f"{name}() membutuhkan {required_args} sampai "
                    f"{len(parameters)} argumen"
                )
            if name != function.name:
                indirect_result = yield from self._execute_operation(
                    call.lineno,
                    "indirect_function_call",
                    (function.name,),
                    iter(self.statement_api["indirect_function_call"]()),
                    should_stop,
                    *self._span(call),
                )
                if indirect_result is _STOPPED:
                    return _STOPPED
            local_names = self._function_local_names(function.definition.body)
            local_variables = {
                local_name: _UNBOUND
                for local_name in local_names
            }
            if len(args) < len(parameters):
                missing_defaults = len(parameters) - len(args)
                args.extend(function.defaults[-missing_defaults:])
            local_variables.update(zip(parameters, args))
            function_scope = ChainMap(local_variables, variables)
            result = yield from self._execute_statements(
                function.definition.body,
                should_stop,
                function_scope,
            )
            if result is _STOPPED:
                return _STOPPED
            return result.value if isinstance(result, _ReturnSignal) else None
        args = []
        for expression in call.args:
            value = yield from self._evaluate_value_expression(
                expression,
                should_stop,
                variables,
            )
            if value is _STOPPED:
                return _STOPPED
            args.append(value)
        args = tuple(args)
        return (yield from self._execute_operation(
            call.lineno,
            name,
            args,
            iter(self.api[name](*args)),
            should_stop,
            *self._span(call),
        ))

    def _execute_operation(
        self,
        line: int,
        name: str,
        args: tuple[Any, ...],
        action: Iterator[Any],
        should_stop: Callable[[], bool] | None,
        column_start: int,
        end_line: int,
        column_end: int,
    ) -> Iterator[ExecutionStep]:
        while True:
            if should_stop is not None and should_stop():
                return _STOPPED
            try:
                progress = next(action)
            except StopIteration as stopped:
                return stopped.value.value
            yield ExecutionStep(
                line,
                name,
                args,
                progress,
                column_start,
                end_line,
                column_end,
            )