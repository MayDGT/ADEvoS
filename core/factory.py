from __future__ import annotations
import re
from typing import TYPE_CHECKING
from core.parse_module import TestCluster, CallableData
from core.testcase import TestCase
from core.chromosome import TestCaseChromosome
from utils import randomness
import core.statement as stmt
from utils.utils import get_random_spawn_point, get_surrounding_point
from configuration import configuration as config
import logging

logger = logging.getLogger(__name__)

class TestFactory:
    logger = logging.getLogger(__name__)

    def __init__(self, test_cluster: TestCluster):
        self._test_cluster = test_cluster

    @staticmethod
    def create_variables(type_name, bounds: list):
        match type_name:
            case 'str':
                return randomness.next_string(randomness.next_int(1, 5))
            case 'int':
                return randomness.next_int(bounds[0], bounds[1])
            case 'float':
                return randomness.next_float(bounds[0], bounds[1])
            case _:
                print("unknown type")
        return None

    def insert_constructor_statement(self, test_case: TestCase, assignee: str, arg_list: list, position: int):
        constructor_data = self._test_cluster.constructor['Road'] if re.match('road', assignee) else \
                           self._test_cluster.constructor['NPC']
        args = {key: value for key, value in zip(constructor_data.args.keys(), arg_list)}
        statement = stmt.ConstructorStatement(test_case, constructor_data.module_name, constructor_data.class_name,
                                              constructor_data.method_name, args, assignee)
        statement.stmt_to_ast()
        test_case.add_statement(statement, position)

    def insert_method_statement(self, test_case: TestCase, callee: str, method_name: str, arg_list: list, position):
        method_data = next((method for method in self._test_cluster.road_methods if method.method_name == method_name), None)
        if method_data is None:
            method_data = next((method for method in self._test_cluster.npc_methods if method.method_name == method_name), None)

        args = {key: value for key, value in zip(method_data.args.keys(), arg_list)}
        if re.match('road', callee) is not None:
            statement = stmt.MethodStatement(test_case, 'Road', callee, method_name, args)
        else:
            statement = stmt.MethodStatement(test_case, 'NPC', callee, method_name, args)
        statement.stmt_to_ast()
        test_case.add_statement(statement, position)

    def insert_random_constructor_statement(self, constructor_name: str, test_case: TestCase, position: int):
        constructor_data = self._test_cluster.constructor[constructor_name]
        args = {}
        if constructor_name == 'Road':
            assignee = f"road{test_case.size()}"
            for key, value in constructor_data.args.items():
                args[key] = self.create_variables(str(value), config.scenario_config.__dict__[key])
        else:
            if test_case.size() == test_case.road_size():
                assignee = "Ego"
                for key, value in constructor_data.args.items():
                    args[key] = self.create_variables(str(value), config.scenario_config.__dict__[key])
            else:
                assignee = f"npc{test_case.size() - test_case.road_size()}"
                for key, value in constructor_data.args.items():
                    if key == 'init_speed':
                        args[key] = self.create_variables(str(value), config.scenario_config.__dict__[key])
                    else:
                        args[key] = get_random_spawn_point(test_case)[key]

        statement = stmt.ConstructorStatement(test_case, constructor_data.module_name,
                                              constructor_data.class_name, constructor_data.method_name,
                                              args, assignee)
        statement.stmt_to_ast()
        test_case.add_statement(statement, position)

    @staticmethod
    def calculate_road_lane_num(road_constructor: stmt.ConstructorStatement,
                                road_method: stmt.MethodStatement | stmt.ConstructorStatement | None = None):
        """calculate the main lane num of the last road, including the in lane and out lane"""
        if road_method is None or isinstance(road_method, stmt.ConstructorStatement):
            return [road_constructor.args['lane_num'], road_constructor.args['lane_num']]

        in_lane = road_constructor.args['lane_num']

        lane_num_change = {'contract': -1, 'expand': 1, 'merge': 0, 'split': 0}

        if road_method.method_name == 'merge':
            in_lane -= road_method.args['lanes']
        elif road_method.method_name == 'split':
            lane_num_change['split'] = -road_method.args['lanes']

        out_lane = road_constructor.args['lane_num'] + lane_num_change[road_method.method_name]

        return [in_lane, out_lane]

    def insert_random_road_constructor(self, test_case: TestCase, position):
        constructor_data: CallableData = self._test_cluster.constructor['Road']
        args = {}
        assignee = 'road{}'.format(test_case.road_size())

        if test_case.road_size() == 0:
            for key, value in constructor_data.args.items():
                args[key] = self.create_variables(str(value), config.scenario_config.__dict__[key])
        else:
            last_road = test_case.road_constructors[-1]
            last_statement = test_case.road_statements[-1]

            if isinstance(last_statement, stmt.ConstructorStatement):
                min_lane_num = max(config.scenario_config.lane_num[0], last_road.args['lane_num'] - 1)
                max_lane_num = min(config.scenario_config.lane_num[1], last_road.args['lane_num'] + 2)

                for key, value in constructor_data.args.items():
                    if key == 'lane_num':
                        args[key] = self.create_variables('int', [min_lane_num, max_lane_num])
                    else:
                        args[key] = self.create_variables(str(value), config.scenario_config.__dict__[key])
            elif isinstance(last_statement, stmt.MethodStatement):
                last_road_lane_num = self.calculate_road_lane_num(last_road, last_statement)[1]
                min_lane_num = max(config.scenario_config.lane_num[0], last_road_lane_num - 1)
                max_lane_num = min(config.scenario_config.lane_num[1], last_road_lane_num + 2)

                if last_statement.method_name in ['split', 'merge']:
                    max_lane_num = last_road_lane_num + 1

                for key, value in constructor_data.args.items():
                    if key == 'lane_num':
                        args[key] = self.create_variables('int', [min_lane_num, max_lane_num])
                    else:
                        args[key] = self.create_variables(str(value), config.scenario_config.__dict__[key])

        statement = stmt.ConstructorStatement(test_case, constructor_data.module_name, constructor_data.class_name,
                                              constructor_data.method_name, args, assignee)
        statement.stmt_to_ast()
        global_position = test_case.add_statement(statement, position)

        return global_position

    def insert_random_road_method(self, test_case: TestCase, position):
        cur_road = test_case.road_constructors[-1]
        cur_road_length = cur_road.args['length']
        cur_road_lane_num = cur_road.args['lane_num']
        cur_road_curv_start = cur_road.args['curv_start']
        cur_road_curv_end = cur_road.args['curv_end']

        callee = test_case.road_constructors[-1].assignee
        candidate_method = randomness.choice(self._test_cluster.road_methods)
        args = {}

        if test_case.road_size() == 1:
            if candidate_method.method_name == 'contract':
                if cur_road_lane_num == config.scenario_config.lane_num[0]:
                    return
                args['start_position'] = self.create_variables('float', [0.5 * cur_road_length, cur_road_length - 20])
                args['deformation_length'] = self.create_variables('float',
                                                                   [20, cur_road_length - args['start_position']])
            elif candidate_method.method_name == 'expand':
                if cur_road_lane_num == config.scenario_config.lane_num[1] - 1:
                    return
                args['start_position'] = self.create_variables('float', [2, 0.5 * cur_road_length])
                args['deformation_length'] = self.create_variables('float', [20, 0.5 * cur_road_length])
            elif candidate_method.method_name == 'merge':
                if cur_road_lane_num == 2:
                    # cur road lane num is 2, cannot merge.
                    return
                args['start_position'] = self.create_variables('float', [0.5 * cur_road_length, cur_road_length - 5])
                args['curvature'] = self.create_variables('float',
                                                          [config.scenario_config.curv_start[0], cur_road_curv_start])
                args['lanes'] = self.create_variables('int', [1, int(cur_road_lane_num / 2) + 1])
            elif candidate_method.method_name == 'split':
                if cur_road_lane_num == 2:
                    # cur road lane num is 2, cannot split.
                    return
                args['start_position'] = self.create_variables('float', [5, 0.5 * cur_road_length])
                args['curvature'] = self.create_variables('float',
                                                          [config.scenario_config.curv_end[0], cur_road_curv_end])
                args['lanes'] = self.create_variables('int', [1, int(cur_road_lane_num / 2) + 1])
        else:
            last_road = test_case.road_constructors[-2]
            last_statement = test_case.road_statements[-2]

            if candidate_method.method_name == 'contract':
                if cur_road_lane_num == config.scenario_config.lane_num[0]:
                    return
                args['start_position'] = self.create_variables('float', [0.5 * cur_road_length, cur_road_length - 20])
                args['deformation_length'] = self.create_variables('float',
                                                                   [20, cur_road_length - args['start_position']])
            elif candidate_method.method_name == 'expand':
                if cur_road_lane_num == config.scenario_config.lane_num[1] - 1:
                    return
                args['start_position'] = self.create_variables('float', [0, 0.5 * cur_road_length])
                args['deformation_length'] = self.create_variables('float', [20, 0.5 * cur_road_length])
            elif candidate_method.method_name == 'merge':
                last_road_lane_num = self.calculate_road_lane_num(last_road, last_statement)[1]

                if cur_road_lane_num <= last_road_lane_num:
                    return

                if isinstance(last_statement, stmt.MethodStatement) and (
                        last_statement.method_name == 'merge' or last_statement.method_name == 'split'):
                    return

                args['start_position'] = self.create_variables('float', [0.5 * cur_road_length, cur_road_length - 5])
                args['curvature'] = self.create_variables('float',
                                                          [config.scenario_config.curv_start[0], cur_road_curv_start])
                args['lanes'] = self.create_variables('int', [1, cur_road_lane_num - last_road_lane_num + 1])
            elif candidate_method.method_name == 'split':
                last_road_lane_num = self.calculate_road_lane_num(last_road, last_statement)[1]

                if cur_road_lane_num == 2:
                    # cur road lane num is 2, cannot split
                    return

                if cur_road_lane_num < last_road_lane_num:
                    # cur_road_lane_num < last_road_lane_num
                    return

                if cur_road_lane_num == last_road_lane_num and (
                        isinstance(last_statement, stmt.MethodStatement) and last_statement.method_name == 'contract'):
                    # contract + split is illegal
                    return

                if isinstance(last_statement, stmt.MethodStatement) and (
                        last_statement.method_name == 'merge' or last_statement.method_name == 'split'):
                    # last_statement.method_name is merge or split
                    return

                args['start_position'] = self.create_variables('float', [5, 0.5 * cur_road_length])
                args['curvature'] = self.create_variables('float',
                                                          [config.scenario_config.curv_end[0], cur_road_curv_end])
                args['lanes'] = self.create_variables('int', [1, int(cur_road_lane_num / 2) + 1])

        statement = stmt.MethodStatement(test_case, 'Road', callee, candidate_method.method_name, args)
        statement.stmt_to_ast()
        test_case.add_statement(statement, position)

    @staticmethod
    def has_shape_change(test_case: TestCase, road: stmt.ConstructorStatement):
        for statement in test_case.road_statements:
            if isinstance(statement, stmt.MethodStatement) and statement.callee == road.assignee:
                return True
        return False

    def check_validity(self, pre_road: stmt.ConstructorStatement, pre_road_method: stmt.MethodStatement | None,
                       suc_road: stmt.ConstructorStatement, suc_road_method: stmt.MethodStatement | None):
        pre_road_lane_num = self.calculate_road_lane_num(pre_road, pre_road_method)[1]
        suc_road_lane_num = self.calculate_road_lane_num(suc_road, suc_road_method)[0]
        if abs(pre_road_lane_num - suc_road_lane_num) >= 2:
            return False
        if pre_road_method is not None and suc_road_method is not None and \
                (pre_road_method.method_name == 'merge' or pre_road_method.method_name == 'split') and \
                (suc_road_method.method_name == 'merge' or suc_road_method.method_name == 'split'):
            return False

        # do not change shape before merge
        if suc_road_method is not None and suc_road_method.method_name == 'merge' and pre_road_method is not None:
            return False

        if suc_road_method is not None and suc_road_method.method_name == 'split':
            if suc_road_lane_num < pre_road_lane_num:
                return False
            if suc_road_lane_num == pre_road_lane_num and (
                    pre_road_method is not None and pre_road_method.method_name == 'contract'):
                return False

        return True

    def mutation_insert_road(self, test_case: TestCase, position: int):
        # constructor part
        pre_road = test_case.road_constructors[position - 1] if position > 0 else None
        suc_road = test_case.road_constructors[position] if position < test_case.road_size() else None
        pre_road_method = None
        suc_road_method = None
        for statement in test_case.road_statements:
            if isinstance(statement, stmt.MethodStatement) and (
                    pre_road is not None and statement.callee == pre_road.assignee):
                pre_road_method = statement
            if isinstance(statement, stmt.MethodStatement) and (
                    suc_road is not None and statement.callee == suc_road.assignee):
                suc_road_method = statement

        pre_road_lane_num = self.calculate_road_lane_num(pre_road, pre_road_method)[0] if pre_road is not None else \
            config.scenario_config.lane_num[0]
        suc_road_lane_num = self.calculate_road_lane_num(suc_road, suc_road_method)[1] if suc_road is not None else \
            config.scenario_config.lane_num[1]

        constructor_data: CallableData = self._test_cluster.constructor['Road']
        args = {}

        for key, value in constructor_data.args.items():
            if key == 'lane_num':
                if pre_road_lane_num == suc_road_lane_num and pre_road_method is None and suc_road_method is None:
                    args[key] = self.create_variables('int',
                                                      [max(config.scenario_config.lane_num[0], suc_road_lane_num - 1),
                                                       min(pre_road_lane_num + 1, config.scenario_config.lane_num[1])])
                else:
                    print('pre lane num', pre_road_lane_num)
                    print('suc lane num', suc_road_lane_num)
                    args[key] = self.create_variables('int', [min(pre_road_lane_num, suc_road_lane_num),
                                                              max(pre_road_lane_num, suc_road_lane_num) + 1])
            else:
                args[key] = self.create_variables(str(value), config.scenario_config.__dict__[key])

        # update other roads
        for other_road in reversed(test_case.road_constructors[position:]):
            print('other road', other_road.assignee)
            for i in range(len(test_case.statements)):
                if isinstance(test_case.statements[i], stmt.ConstructorStatement) and test_case.statements[i].assignee == other_road.assignee:
                    test_case.statements[i].assignee = 'road{}'.format(int(test_case.statements[i].assignee[-1]) + 1)
                    test_case.statements[i].stmt_to_ast()
                    if (i + 1) < len(test_case.statements) and isinstance(test_case.statements[i + 1], stmt.MethodStatement):
                        test_case.statements[i + 1].callee = 'road{}'.format(int(test_case.statements[i + 1].callee[-1]) + 1)
                        test_case.statements[i + 1].stmt_to_ast()

        assignee = 'road{}'.format(position)
        constructor_statement = stmt.ConstructorStatement(test_case, constructor_data.module_name,
                                                          constructor_data.class_name,
                                                          constructor_data.method_name,
                                                          args, assignee)
        constructor_statement.stmt_to_ast()

        # method part
        cur_road = constructor_statement
        cur_road_lane_num = cur_road.args['lane_num']
        cur_road_length = cur_road.args['length']
        cur_road_curv_start = cur_road.args['curv_start']
        cur_road_curv_end = cur_road.args['curv_end']
        callee = constructor_statement.assignee
        candidate_method = randomness.choice(self._test_cluster.road_methods)
        args = {}
        flag = True
        if candidate_method.method_name == 'contract':
            args['start_position'] = self.create_variables('float', [0.5 * cur_road_length, cur_road_length - 20])
            args['deformation_length'] = self.create_variables('float', [20, cur_road_length - args['start_position']])
            if cur_road_lane_num == config.scenario_config.__dict__['lane_num'][0]:
                flag = False

        elif candidate_method.method_name == 'expand':
            args['start_position'] = self.create_variables('float', [0, 0.5 * cur_road_length])
            args['deformation_length'] = self.create_variables('float', [20, 0.5 * cur_road_length])
            if cur_road_lane_num == config.scenario_config.__dict__['lane_num'][1] - 1:
                flag = False

        elif candidate_method.method_name == 'merge':
            args['start_position'] = self.create_variables('float', [0.5 * cur_road_length, cur_road_length - 10])
            args['curvature'] = self.create_variables('float', [config.scenario_config.curv_start[0], cur_road_curv_start])
            args['lanes'] = self.create_variables('int', [1, int(cur_road_lane_num / 2) + 1])
            if cur_road_lane_num == 2:
                # cur road lane num is 2, cannot merge.
                flag = False

        elif candidate_method.method_name == 'split':
            args['start_position'] = self.create_variables('float', [10, 0.5 * cur_road_length])
            args['curvature'] = self.create_variables('float', [config.scenario_config.curv_end[0], cur_road_curv_end])
            args['lanes'] = self.create_variables('int', [1, int(cur_road_lane_num / 2) + 1])
            if cur_road_lane_num == 2:
                # cur road lane num is 2, cannot split.
                flag = False

        cur_road_method = None
        if flag is True:
            cur_road_method = stmt.MethodStatement(test_case, 'Road', callee, candidate_method.method_name, args)
            cur_road_method.stmt_to_ast()

        validity = False
        if pre_road is None:
            validity = self.check_validity(cur_road, cur_road_method, suc_road, suc_road_method)
        if suc_road is None:
            self.check_validity(pre_road, pre_road_method, cur_road, cur_road_method)
        if pre_road is not None and suc_road is not None:
            validity = self.check_validity(pre_road, pre_road_method, cur_road, cur_road_method) \
                       and self.check_validity(cur_road, cur_road_method, suc_road, suc_road_method)

        global_position = test_case.add_statement(constructor_statement, position)
        if validity and flag:
            test_case.add_statement(cur_road_method, global_position + 1)

    def mutation_delete_road(self, test_case: TestCase, position: int):
        cur_road = test_case.road_constructors[position]
        pre_road = test_case.road_constructors[position - 1] if position > 0 else None
        suc_road = test_case.road_constructors[position + 1] if position + 1 < test_case.road_size() else None
        pre_road_method = None
        suc_road_method = None
        for statement in test_case.road_statements:
            if isinstance(statement, stmt.MethodStatement) and (
                    pre_road is not None and statement.callee == pre_road.assignee):
                pre_road_method = statement
            if isinstance(statement, stmt.MethodStatement) and (
                    suc_road is not None and statement.callee == suc_road.assignee):
                suc_road_method = statement

        validity = False
        if pre_road is None or suc_road is None:
            validity = True
        if pre_road is not None and suc_road is not None:
            validity = self.check_validity(pre_road, pre_road_method, suc_road, suc_road_method)

        if validity:
            if position == test_case.road_size() - 1:
                for st in test_case.statements:
                    if isinstance(st, stmt.ConstructorStatement) and st.class_name == 'NPC':
                        if st.args['road_id'] == int(cur_road.assignee[-1]):
                            self.logger.info("update road_id for %s", st.assignee)
                            st.args['road_id'] = int(cur_road.assignee[-1]) - 1
                            st.stmt_to_ast()

            test_case.delete_road(cur_road)
            self.logger.info("success delete road %d", position)

            # update other roads and npcs
            for other_road in test_case.road_constructors[position:]:
                print('other road', other_road.assignee)
                for i in range(len(test_case.statements)):
                    if isinstance(test_case.statements[i], stmt.ConstructorStatement) and test_case.statements[i].assignee == other_road.assignee:
                        # update npc on other road
                        for st in test_case.statements:
                            if isinstance(st, stmt.ConstructorStatement) and st.class_name == 'NPC':
                                if st.args['road_id'] == int(test_case.statements[i].assignee[-1]):
                                    self.logger.info("update road_id for %s", st.assignee)
                                    st.args['road_id'] = int(test_case.statements[i].assignee[-1]) - 1
                                    st.stmt_to_ast()

                        test_case.statements[i].assignee = 'road{}'.format(
                            int(test_case.statements[i].assignee[-1]) - 1)
                        test_case.statements[i].stmt_to_ast()
                        if (i + 1) < len(test_case.statements) and isinstance(test_case.statements[i + 1],
                                                                              stmt.MethodStatement):
                            test_case.statements[i + 1].callee = 'road{}'.format(
                                int(test_case.statements[i + 1].callee[-1]) - 1)
                            test_case.statements[i + 1].stmt_to_ast()
        else:
            self.logger.info("fail to delete road{}".format(position))

    def check_road_change_validity(self, test_case: TestCase, other_test_case: TestCase, position):
        other_road = other_test_case.road_constructors[position]
        other_road_method = None
        pre_road = test_case.road_constructors[position - 1] if position > 0 else None
        suc_road = test_case.road_constructors[position] if position < test_case.road_size() else None
        pre_road_method = None
        suc_road_method = None

        for statement in test_case.road_statements:
            if isinstance(statement, stmt.MethodStatement) and (
                    pre_road is not None and statement.callee == pre_road.assignee):
                pre_road_method = statement
            if isinstance(statement, stmt.MethodStatement) and (
                    suc_road is not None and statement.callee == suc_road.assignee):
                suc_road_method = statement

        for st in other_test_case.road_statements:
            if isinstance(st, stmt.MethodStatement) and st.callee == other_road.assignee:
                other_road_method = st

        road_validity = False

        if pre_road is None:
            road_validity = self.check_validity(other_road, other_road_method, suc_road, suc_road_method)
        if suc_road is None:
            road_validity = self.check_validity(pre_road, pre_road_method, other_road, other_road_method)
        if pre_road is not None and suc_road is not None:
            road_validity = self.check_validity(pre_road, pre_road_method, other_road,
                                                other_road_method) and self.check_validity(other_road,
                                                                                           other_road_method, suc_road,
                                                                                           suc_road_method)

        return road_validity

    def mutation_change_road(self, test_case: TestCase, position: int):
        self.logger.info("mutate_change road%d", position)
        road = test_case.road_constructors[position]
        road_method = None
        for statement in test_case.road_statements:
            if isinstance(statement, stmt.MethodStatement) and statement.callee == road.assignee:
                road_method = statement

        pre_road = test_case.road_constructors[position - 1] if position > 0 else None
        suc_road = test_case.road_constructors[position] if position < test_case.road_size() else None
        pre_road_method = None
        suc_road_method = None
        for statement in test_case.road_statements:
            if isinstance(statement, stmt.MethodStatement) and (
                    pre_road is not None and statement.callee == pre_road.assignee):
                pre_road_method = statement
            if isinstance(statement, stmt.MethodStatement) and (
                    suc_road is not None and statement.callee == suc_road.assignee):
                suc_road_method = statement

        clone_road: stmt.ConstructorStatement = road.clone(test_case)
        clone_road.mutate_road()

        road_validity = False
        if pre_road is None:
            road_validity = self.check_validity(road, road_method, suc_road, suc_road_method)
        if suc_road is None:
            road_validity = self.check_validity(pre_road, pre_road_method, road, road_method)
        if pre_road is not None and suc_road is not None:
            road_validity = self.check_validity(pre_road, pre_road_method, road, road_method) and \
                            self.check_validity(road, road_method, suc_road, suc_road_method)

        self.logger.info("road_validity is %s", str(road_validity))

        for name, value in road.args.items():
            if name == 'lane_num' and road_validity:
                road.args[name] = clone_road.args[name]
            road.args[name] = clone_road.args[name]

        road.stmt_to_ast()
        clone_road.stmt_to_ast()

        # method part
        road_length = road.args['length']
        road_curv_start = road.args['curv_start']
        road_curv_end = road.args['curv_end']
        if road_method is not None:
            clone_road_method = road_method.clone(test_case)

            flag = clone_road_method.mutate_road_method(road)

            if flag is False:
                # current road method could not match the mutated road
                self.logger.info("remove the road method")
                test_case.statements.remove(road_method)
                test_case.road_statements.remove(road_method)
            else:
                method_validity = False
                if pre_road is None:
                    method_validity = self.check_validity(road, clone_road_method, suc_road, suc_road_method)
                if suc_road is None:
                    method_validity = self.check_validity(pre_road, pre_road_method, road, clone_road_method)
                if pre_road is not None and suc_road is not None:
                    method_validity = self.check_validity(pre_road, pre_road_method, road, clone_road_method) and \
                                    self.check_validity(road, clone_road_method, suc_road, suc_road_method)

                self.logger.info("method_validity is %s", str(method_validity))

                for name, value in clone_road_method.args.items():
                    if name == 'lanes' and method_validity:
                        road_method.args['lanes'] = clone_road_method.args['lanes']
                    road_method.args[name] = clone_road_method.args[name]

                road_method.stmt_to_ast()

    def insert_random_npc_constructor(self, test_case: TestCase, position: int):
        constructor_data: CallableData = self._test_cluster.constructor['NPC']
        args = {}
        assignee = None
        if position == 0:
            # the first npc as ego
            position_dict = get_random_spawn_point(test_case, position)
            assignee = 'Ego'
            for key, value in constructor_data.args.items():
                if key == 'init_speed':
                    args[key] = self.create_variables(str(value), config.scenario_config.__dict__[key])
                else:
                    args[key] = position_dict[key]

        else:
            # those npc are randomly spawned around the ego
            position_dict = get_surrounding_point(test_case)
            assignee = 'npc{}'.format(position)
            for key, value in constructor_data.args.items():
                if key == 'init_speed':
                    args[key] = self.create_variables(str(value), config.scenario_config.__dict__[key])
                else:
                    args[key] = position_dict[key]

        statement = stmt.ConstructorStatement(test_case, constructor_data.module_name, constructor_data.class_name,
                                              constructor_data.method_name,
                                              args, assignee)
        statement.stmt_to_ast()
        test_case.add_statement(statement, len(test_case.road_statements) + position)

    def avfuzzer_insert_random_npc_constructor(self, test_case: TestCase, position: int):
        constructor_data: CallableData = self._test_cluster.constructor['NPC']
        args = {}

        assignee = None
        if position == 0:
            # the first npc as ego
            position_dict = {'road_id': 0, 'init_t': -11.5, 'init_s': 30.0}
            assignee = 'Ego'
            for key, value in constructor_data.args.items():
                if key == 'init_speed':
                    args[key] = self.create_variables(str(value), config.scenario_config.__dict__[key])
                else:
                    args[key] = position_dict[key]
        else:
            # those npc are randomly spawned around the ego
            assignee = 'npc{}'.format(position)
            for key, value in constructor_data.args.items():
                if key == 'init_speed':
                    args[key] = self.create_variables(str(value), config.scenario_config.__dict__[key])
                elif key == 'road_id':
                    args[key] = 0
                elif key == 'init_s':
                    args[key] = randomness.next_float(60, 80)
                else:
                    args[key] = randomness.next_float(-14.5, -6.5)

        statement = stmt.ConstructorStatement(test_case, constructor_data.module_name, constructor_data.class_name,
                                              constructor_data.method_name,
                                              args, assignee)
        statement.stmt_to_ast()
        test_case.add_statement(statement, len(test_case.road_statements) + position)

    def insert_random_npc_method(self, test_case: TestCase, position: int, fixed_callee: str | None = None):
        if fixed_callee is None:
            candidates = test_case.get_callees()
            callee = randomness.choice(candidates)
        else:
            callee = fixed_callee
        method_data: CallableData = randomness.choice(self._test_cluster.npc_methods)
        args = {}
        for key, value in method_data.args.items():
            args[key] = self.create_variables(str(value), config.scenario_config.__dict__[key])
        statement = stmt.MethodStatement(test_case, 'NPC', callee, method_data.method_name, args)
        statement.stmt_to_ast()
        test_case.add_statement(statement, position)

    @staticmethod
    def append_statement(test_case: TestCase, statement: stmt.Statement, position: int = -1):
        new_position = test_case.size() if position == -1 else position
        clone_statement: stmt.Statement = statement.clone(test_case)
        clone_statement.stmt_to_ast()
        test_case.add_statement(clone_statement, new_position)

    @staticmethod
    def delete_statement(test_case: TestCase, position: int):
        statement = test_case.get_statement(position)
        if isinstance(statement, stmt.ConstructorStatement):
            test_case.delete_constructor_statement(statement)
        elif isinstance(statement, stmt.MethodStatement):
            test_case.delete_method_statement(statement)
        else:
            raise Exception('delete error')


class TestCaseFactory:
    logger = logging.getLogger(__name__)

    def __init__(self, test_factory: TestFactory):
        self._test_factory = test_factory

    def generate_random_testcase(self) -> TestCase:
        test_case = TestCase()

        # Road
        road_num = randomness.next_int(config.ga_config.min_road_num + 1, config.ga_config.max_road_num + 1)
        for i in range(road_num):
            position = self._test_factory.insert_random_road_constructor(test_case, test_case.road_size())
            prob = randomness.next_float()
            if prob <= config.ga_config.shape_change_prob:
                self._test_factory.insert_random_road_method(test_case, position + 1)

        vehicle_num = randomness.next_int(test_case.road_size(), config.ga_config.max_vehicle_num)
        self.logger.info("road size: %d", test_case.road_size())
        for i in range(vehicle_num):
            self._test_factory.insert_random_npc_constructor(test_case, i)

        action_length = randomness.next_int(config.ga_config.min_action_length, config.ga_config.max_action_length + 1)
        for i in range(action_length):
            self._test_factory.insert_random_npc_method(test_case, test_case.size())

        return test_case


class TestCaseChromosomeFactory:

    def __init__(self, test_factory: TestFactory, test_case_factory: TestCaseFactory):
        self._test_factory = test_factory
        self._test_case_factory = test_case_factory

    def generate_chromosome(self) -> TestCaseChromosome:
        logger.info("start generate a chromosome")
        test_case = self._test_case_factory.generate_random_testcase()
        chrom = TestCaseChromosome(test_case, self._test_factory)

        return chrom

    def avfuzzer_generate_chromosome(self):
        test_case = TestCase()
        self._test_factory.insert_constructor_statement(test_case, 'road0', [-0.0000000019615, 0.000000088191864, 200.0000, 6, 3.5], test_case.size())
        self._test_factory.insert_constructor_statement(test_case, 'road1', [-0.0000000019615, 0.000000088191864, 200.0000, 6, 3.5], test_case.size())
        for i in range(3):  # one ego and  NPCs
            self._test_factory.avfuzzer_insert_random_npc_constructor(test_case, i)
        for i in range(5):
            self._test_factory.insert_random_npc_method(test_case, test_case.size(), 'npc1')
        for i in range(5):
            self._test_factory.insert_random_npc_method(test_case, test_case.size(), 'npc2')

        chrom = TestCaseChromosome(test_case, self._test_factory)
        return chrom

