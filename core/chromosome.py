from __future__ import annotations
from typing import TYPE_CHECKING
import ast
import logging
import re
import numpy as np
if TYPE_CHECKING:
    import core.testcase as tc
    import core.factory as tf
from utils import randomness
import core.statement as stmt
from configuration import configuration as config
from abc import ABCMeta, abstractmethod

class TestCaseChromosome:
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        test_case: tc.TestCase | None = None,
        test_factory: tf.TestFactory | None = None,
        orig: TestCaseChromosome | None = None,
    ):
        if orig is None:
            self._test_case = test_case
            self._test_factory = test_factory
            self._fitness = []
            self._complexity = self.calc_complexity()
            self._rank = None
            self._crowding = None
        else:
            self._test_case = orig._test_case.clone()
            self._test_factory = orig._test_factory
            self._fitness = orig._fitness
            self._complexity = orig._complexity
            self._rank = orig._rank
            self._crowding = orig._crowding

    @property
    def test_case(self):
        return self._test_case

    @property
    def test_factory(self):
        return self._test_factory

    @property
    def fitness(self):
        return self._fitness

    @property
    def complexity(self):
        return self._complexity

    @property
    def rank(self):
        return self._rank

    @property
    def crowding(self):
        return self._crowding

    @fitness.setter
    def fitness(self, fitness):
        self._fitness = fitness

    @rank.setter
    def rank(self, rank):
        self._rank = rank

    @crowding.setter
    def crowding(self, crowding):
        self._crowding = crowding

    def size(self):
        return self._test_case.size()

    def ast_node(self):
        return ast.fix_missing_locations(self._test_case.test_case_to_ast())

    def clone(self):
        return TestCaseChromosome(orig=self)

    def calc_complexity(self):
        objects_num = 0
        action_type = []
        for statement in self._test_case.statements:
            if isinstance(statement, stmt.ConstructorStatement):
                objects_num += 1
            else:
                action_type.append(statement.callee)
        action_length = len(self._test_case.statements) - objects_num
        action_type = len(set(action_type))
        return action_length / 10 + 2 * objects_num / 5 + action_type / 3

    def avfuzzer_crossover(self, other: TestCaseChromosome, npc_index: int):
        offspring = self._test_case.clone(0, self._test_case.size())
        other_methods = []
        for st in other._test_case.statements:
            if isinstance(st, stmt.MethodStatement) and st.callee == 'npc{}'.format(npc_index):
                other_methods.append(st.clone(offspring))

        for i in reversed(range(len(offspring.statements))):
            if isinstance(offspring.statements[i], stmt.MethodStatement) and offspring.statements[i].callee == 'npc{}'.format(npc_index):
                offspring.delete_method_statement(offspring.statements[i])

        for method in other_methods:
            offspring.add_statement(method, offspring.size())

        self._test_case = offspring
        for st in self._test_case.statements:
            st.stmt_to_ast()

    def avfuzzer_mutation(self):
        mutate_position = randomness.next_int(5, 15)
        statement = self._test_case.get_statement(mutate_position)
        self.logger.info("AVFuzzer mutation position: %d", mutate_position)
        if randomness.next_float() < 0.0:
            callee = statement.callee
            self._test_case.delete_method_statement(statement)
            self._test_factory.insert_random_npc_method(self._test_case, mutate_position, callee)
        else:
            statement.avfuzzer_mutate()

    def crossover(self, other: TestCaseChromosome, road_position: int, npc_positions: list):
        offspring = self._test_case.clone(0, self._test_case.size())
        # road part
        if road_position != 0:
            road = self._test_case.road_constructors[road_position]
            other_road = other._test_case.road_constructors[road_position].clone(offspring)
            other_road_method = None
            for st in other._test_case.road_statements:
                if isinstance(st, stmt.MethodStatement) and st.callee == other_road.assignee:
                    other_road_method = st.clone(offspring)

            offspring.delete_road(offspring.road_constructors[road_position])

            global_position = offspring.add_statement(other_road, road_position)
            if other_road_method is not None:
                offspring.add_statement(other_road_method, global_position + 1)

            npc_num = 0
            for st in offspring.statements:
                if isinstance(st, stmt.ConstructorStatement) and re.match('npc', st.assignee) is not None:
                    npc_num += 1

            npc_to_delete = []
            for i in reversed(range(len(offspring.road_statements) + 1, len(offspring.road_statements) + 1 + npc_num)):
                if offspring.statements[i].class_name == 'NPC' and isinstance(offspring.statements[i], stmt.ConstructorStatement) \
                        and offspring.statements[i].args['road_id'] == road_position:
                    # delete the npc
                    npc_to_delete.append(offspring.statements[i])
            for npc in npc_to_delete:
                offspring.delete_constructor_statement(npc)

            current_npc_num = 0
            for st in offspring.statements:
                if isinstance(st, stmt.ConstructorStatement) and re.match('npc', st.assignee) is not None:
                    current_npc_num += 1
                    for method in offspring.statements:
                        if isinstance(method, stmt.MethodStatement) and method.callee == st.assignee:
                            method.callee = 'npc{}'.format(current_npc_num)
                    st.assignee = 'npc{}'.format(current_npc_num)

            npc_from_other_road = []
            npc_method_from_other_road = []
            # find the npcs and methods on other_road
            for st in other._test_case.statements:
                if isinstance(st, stmt.ConstructorStatement) and st.class_name == 'NPC' and st.args['road_id'] == road_position:
                    for method in other._test_case.statements:
                        if isinstance(method, stmt.MethodStatement) and method.class_name == 'NPC' and method.callee == st.assignee:
                            method = method.clone(offspring)
                            method.callee = st.assignee + '_other'
                            npc_method_from_other_road.append(method)

                    npc = st.clone(offspring)
                    npc.assignee = npc.assignee + '_other'
                    npc_from_other_road.append(npc)
            # rename them and add to offspring
            npc_num = 0
            for st in offspring.statements:
                if isinstance(st, stmt.ConstructorStatement) and re.match('npc', st.assignee) is not None:
                    npc_num += 1
            start_name = npc_num + 1
            # rename back those npc on other_road
            for npc in npc_from_other_road:
                for method in npc_method_from_other_road:
                    if method.callee == npc.assignee:
                        method.callee = 'npc{}'.format(start_name)
                npc.assignee = 'npc{}'.format(start_name)
                start_name += 1

            for i in range(len(npc_from_other_road)):
                offspring.add_statement(npc_from_other_road[i], len(offspring.road_statements) + npc_num + 1 + i)
            for method in npc_method_from_other_road:
                offspring.add_statement(method, offspring.size())

        # npc part
        vehicle_num1 = 0
        vehicle_num2 = 0
        for statement in offspring.statements:
            if isinstance(statement, stmt.ConstructorStatement) and statement.class_name == 'NPC':
                vehicle_num1 += 1
        for statement in other.test_case.statements:
            if isinstance(statement, stmt.ConstructorStatement) and statement.class_name == 'NPC':
                vehicle_num2 += 1
        npc_position = randomness.next_int(1, min(vehicle_num1, vehicle_num2))
        self.logger.info("exchange maneuvers on npc%d", npc_position)

        other_methods = []
        for st in other._test_case.statements:
            if isinstance(st, stmt.MethodStatement) and st.callee == 'npc{}'.format(npc_position):
                other_methods.append(st.clone(offspring))

        for i in reversed(range(len(offspring.statements))):
            if isinstance(offspring.statements[i], stmt.MethodStatement) and offspring.statements[i].callee == 'npc{}'.format(npc_position):
                offspring.delete_method_statement(offspring.statements[i])
        for method in other_methods:
            offspring.add_statement(method, offspring.size())

        self._test_case = offspring
        for st in self._test_case.statements:
            st.stmt_to_ast()

    def mutate(self):
        self.logger.info("start mutate")
        if randomness.next_float() <= config.ga_config.test_insert_probability:
            self.logger.info("enter mutation_insert")
            self.mutation_insert()
        if randomness.next_float() <= config.ga_config.test_change_probability:
            self.logger.info("enter mutation_change")
            self.mutation_change()
        if randomness.next_float() <= config.ga_config.test_delete_probability:
            self.logger.info("enter mutation_delete")
            self.mutation_delete()

        self._complexity = self.calc_complexity()

    def mutation_insert(self):
        # road part
        if self.test_case.road_size() < config.ga_config.max_road_num:
            insert_position = randomness.next_int(0, self.test_case.road_size() + 1)
            print(insert_position)
            self._test_factory.mutation_insert_road(self._test_case, insert_position)

        # npc part
        if self.test_case.size() < config.ga_config.max_testcase_size:
            self._test_factory.insert_random_npc_method(self._test_case, self._test_case.size())

    def mutation_change(self):
        change_position = randomness.next_int(0, self._test_case.road_size())
        self.logger.info("prepare to change road%d", change_position)
        self._test_factory.mutation_change_road(self._test_case, change_position)

        # npc part
        prob_change = 1.0 / (self._test_case.size() - len(self._test_case.road_statements))
        position = len(self._test_case.road_statements) + 1  # from npc1
        while position < self._test_case.size():
            if randomness.next_float() < prob_change:
                statement = self._test_case.get_statement(position)
                self.logger.info("npc part, change mutation at position: %d", position)
                statement.mutate()
            position += 1

    def mutation_delete(self):
        # road part
        if self._test_case.road_size() > config.ga_config.min_road_num:
            delete_position = randomness.next_int(0, self.test_case.road_size())
            self.logger.info("road part, prepare to delete road %d", delete_position)
            self._test_factory.mutation_delete_road(self._test_case, delete_position)

        # npc part
        prob_delete = 1.0 / (self._test_case.size() - len(self._test_case.road_statements))
        for position in reversed(range(len(self._test_case.road_statements) + 1, self._test_case.size())):
            if isinstance(self._test_case.statements[position], stmt.MethodStatement):
                if position >= self.size():
                    continue
                if randomness.next_float() < prob_delete:
                    self.logger.info("npc part, delete mutation at position: %d", position)
                    self._test_factory.delete_statement(self._test_case, position)


if __name__ == '__main__':
    pass