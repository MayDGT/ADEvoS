from __future__ import annotations
import abc
import ast
import re
from abc import ABCMeta
from itertools import islice
from configuration import configuration as config
from typing import TYPE_CHECKING
import core.statement as stmt

if TYPE_CHECKING:
    from core.statement import Statement

class TestCase(metaclass=ABCMeta):
    def __init__(self):
        self._statements: list[Statement] = []
        self._road_statements: list[Statement] = []
        self._road_constructors: list[Statement] = []
        self._cursor: int = 0
        self._ast_node = None

    @property
    def statements(self) -> list[Statement]:
        return self._statements

    @property
    def road_statements(self) -> list[Statement]:
        return self._road_statements

    @property
    def road_constructors(self) -> list[Statement]:
        return self._road_constructors

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def ast_node(self):
        return self._ast_node

    def size(self) -> int:
        return len(self._statements)

    def road_size(self) -> int:
        return len(self._road_constructors)

    def clone(self, start: int = 0, stop: int | None = None) -> TestCase:
        test_case = TestCase()
        for statement in islice(self._statements, start, stop):
            clone_statement: stmt.Statement = statement.clone(test_case)
            clone_statement.stmt_to_ast()
            test_case._statements.append(clone_statement)

            if statement.class_name == 'Road':
                if isinstance(statement, stmt.ConstructorStatement):
                    test_case.road_constructors.append(clone_statement)
                test_case._road_statements.append(clone_statement)
        return test_case

    def get_statement(self, position: int) -> Statement:
        assert 0 <= position < len(self._statements)
        return self._statements[position]

    def add_statement(self, statement: Statement, position: int = -1):
        if statement.class_name == 'Road':
            if isinstance(statement, stmt.ConstructorStatement):

                self._road_constructors.insert(position, statement)
                global_position = 0
                pre_road_name_list = [road.assignee for road in self._road_constructors[:position]]
                for st in self._road_statements:
                    if isinstance(st, stmt.ConstructorStatement) and st.assignee in pre_road_name_list:
                        global_position += 1
                    if isinstance(st, stmt.MethodStatement) and st.callee in pre_road_name_list:
                        global_position += 1
                self._road_statements.insert(global_position, statement)
                self._statements.insert(global_position, statement)

                return global_position

            elif isinstance(statement, stmt.MethodStatement):
                self._road_statements.insert(position, statement)
                self._statements.insert(position, statement)

                return position

        elif statement.class_name == 'NPC':
            self._statements.insert(position, statement)

    def delete_road(self, statement: stmt.ConstructorStatement):

        for st in self._road_statements:
            if isinstance(st, stmt.MethodStatement) and st.callee == statement.assignee:
                self._road_statements.remove(st)
                self._statements.remove(st)

        self._road_constructors.remove(statement)
        self._road_statements.remove(statement)
        self._statements.remove(statement)

    def delete_method_statement(self, statement: stmt.MethodStatement):
        if len(self._statements) > config.ga_config.min_testcase_size:
            self._statements.remove(statement)

    def delete_constructor_statement(self, statement: stmt.ConstructorStatement):
        for other_statement in reversed(self._statements):
            if isinstance(other_statement, stmt.MethodStatement):
                if other_statement.callee == statement.assignee:
                    self.delete_method_statement(other_statement)

        if len(self._statements) > config.ga_config.min_testcase_size:
            self._statements.remove(statement)
            if statement in self._road_statements:
                self._road_statements.remove(statement)

    def get_callees(self) -> list[str]:
        callees = []
        for statement in self._statements:
            if isinstance(statement, stmt.ConstructorStatement) and re.match('npc', statement.assignee) is not None:
                callees.append(statement.assignee)
        return callees

    def test_case_to_ast(self) -> ast.Module:
        function_node_body = []
        for statement in self._statements:
            ast_node: ast.Assign = statement.ast_node
            function_node_body.append(ast_node)
        function_node = ast.FunctionDef(
                            name=f"testcase",
                            args=ast.arguments(
                                args=[ast.Name(id="self", ctx="Param")],
                                defaults=[],
                                vararg=None,
                                kwarg=None,
                                posonlyargs=[],
                                kwonlyargs=[],
                                kw_defaults=[],
                            ),
                            body=function_node_body,
                            decorator_list=[]
                            )
        self._ast_node = ast.Module(body=[function_node], type_ignores=[])
        return self._ast_node

