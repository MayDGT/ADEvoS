from __future__ import annotations
import ast
import copy
import numpy as np
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING
from utils import randomness
from utils.utils import get_random_spawn_point, get_surrounding_point
from configuration import configuration as config
if TYPE_CHECKING:
    import core.testcase as tc

def polynomial_mutate(ori_var: list, lb: list, ub: list, distribution, prob):
    var = np.array(ori_var)
    mut_var = var
    lb = np.array(lb)
    ub = np.array(ub)
    prob = np.ones(var.shape) * prob
    choose_index = np.random.random(var.shape) < prob
    # if choose_index are all false, we should choose at least one var for mutation
    if ~np.any(choose_index):
        choose_index[np.random.randint(var.shape[0])] = True

    choose_var = var[choose_index]
    lb = lb[choose_index]
    ub = ub[choose_index]
    delta_1 = (choose_var - lb) / (ub - lb)
    delta_2 = (ub - choose_var) / (ub - lb)
    rand = np.random.random(choose_var.shape)
    mask = rand <= 0.5
    mask_not = np.logical_not(mask)
    delta_q = np.zeros(choose_var.shape)

    # rand <= 0.5
    q = 2 * rand + (1 - 2 * rand) * np.power(1 - delta_1, distribution + 1)
    Q = np.power(q, 1 / (distribution + 1)) - 1
    delta_q[mask] = Q[mask]

    # rand > 0.5
    q = 2 * (1 - rand) + 2 * (rand - 0.5) * (np.power(1 - delta_2, distribution + 1))
    Q = 1 - np.power(q, 1 / (distribution + 1))
    delta_q[mask_not] = Q[mask_not]

    choose_var = choose_var + delta_q * (ub - lb)

    mut_var[choose_index] = choose_var
    return mut_var.tolist()

class Statement(metaclass=ABCMeta):

    def __init__(self, test_case: tc.TestCase):
        self._test_case = test_case
        self._ast_node = None
        self._args = None
        self._assignee = None
        self._callee = None
        self._class_name = None

    @property
    def test_case(self):
        return self._test_case

    @property
    def class_name(self):
        return self._class_name

    @property
    def assignee(self):
        return self._assignee

    @assignee.setter
    def assignee(self, val):
        self._assignee = val

    @property
    def callee(self):
        return self._callee

    @callee.setter
    def callee(self, val):
        self._callee = val

    @property
    def args(self):
        return self._args

    @property
    def ast_node(self):
        return self._ast_node

    @abstractmethod
    def clone(self, test_case: tc.TestCase):
        """Deep clone a statement"""

    @abstractmethod
    def stmt_to_ast(self):
        """Translate this statement to an AST node."""

    @abstractmethod
    def mutate(self):
        """Mutate this statement"""


class ConstructorStatement(Statement):

    def __init__(self, test_case: tc.TestCase, module_name: str, class_name: str, constructor_name: str, args: dict, assignee: str):
        super().__init__(test_case)

        self._module_name = module_name
        self._class_name = class_name
        self._constructor_name = constructor_name
        self._args = args
        self._assignee = assignee
        self._ast_node = None
        self.callee = constructor_name


    def clone(self, test_case: tc.TestCase):
        clone_args = {}
        for arg_name, arg_value in self.args.items():
            clone_args[arg_name] = arg_value
        return ConstructorStatement(test_case, self._module_name, self._class_name, self._constructor_name, clone_args, copy.deepcopy(self._assignee))

    def stmt_to_ast(self):
        args = [ast.Constant(value=value) for value in self._args.values()]
        call = ast.Call(
            func=ast.Name(id=self._constructor_name, ctx=ast.Load()),
            args=args,
            keywords=[],
        )
        self._ast_node = ast.Assign(
                targets=[ast.Name(id=self._assignee, ctx=ast.Load())],
                value=call,
            )

    def mutate_road(self):
        var = []
        lb = []
        ub = []
        for arg_name, arg_value in self._args.items():
            if arg_name != 'lane_num':
                var.append(arg_value)
                lb.append(config.scenario_config.__dict__[arg_name][0])
                ub.append(config.scenario_config.__dict__[arg_name][1])

        mut_var: list = polynomial_mutate(var, lb, ub, config.ga_config.polynomial_distribution,
                                          config.ga_config.polynomial_prob)

        for name, value in self._args.items():
            if name == 'lane_num':
                self._args[name] = randomness.next_int(config.scenario_config.__dict__[name][0], config.scenario_config.__dict__[name][1])
            else:
                self._args[name] = mut_var.pop(0)

        self.stmt_to_ast()

    def mutate(self):
        if self._class_name == 'Road':
            return self.mutate_road()
        var = []
        lb = []
        ub = []

        # speed
        var.append(self._args['init_speed'])
        lb.append(config.scenario_config.__dict__['init_speed'][0])
        ub.append(config.scenario_config.__dict__['init_speed'][1])
        mut_var: list = polynomial_mutate(var, lb, ub, config.ga_config.polynomial_distribution,
                                          config.ga_config.polynomial_prob)
        self._args['init_speed'] = mut_var.pop(0)

        # position
        position_dict = get_surrounding_point(self._test_case)
        for key, value in self._args.items():
            if key in ['road_id', 'init_s', 'init_t']:
                self._args[key] = position_dict[key]

        self.stmt_to_ast()

    def original_mutate(self):
        if self._class_name == 'Road':
            return self.mutate_road()
        var = []
        lb = []
        ub = []
        mut_int_var = []
        for arg_name, arg_value in self._args.items():

            if isinstance(arg_value, float) and arg_name not in ['road_id', 'init_s', 'init_t']:
                var.append(arg_value)
                lb.append(config.scenario_config.__dict__[arg_name][0])
                ub.append(config.scenario_config.__dict__[arg_name][1])
            if arg_name == 'init_s':
                var.append(arg_value)
                lb.append(0.0)
                ub.append(self.test_case.road_constructors[self.args['road_id']].args['length'])

            if arg_name == 'init_t':
                var.append(arg_value)
                road = self.test_case.road_constructors[self.args['road_id']]
                lb.append(-1 * road.args['lane_num'] * road.args['lane_width'])
                ub.append(0.0)

        mut_var: list = polynomial_mutate(var, lb, ub, config.ga_config.polynomial_distribution,
                                          config.ga_config.polynomial_prob)

        for name, value in self._args.items():
            if name == 'road_id':
                self._args[name] = value
            elif name == 'lane_num':
                self._args[name] = randomness.next_int(config.scenario_config.__dict__[name][0], config.scenario_config.__dict__[name][1])
            else:
                self._args[name] = mut_var.pop(0)

        self.stmt_to_ast()

    def re_sample(self):
        for name, value in self._args.items():
            if name in ['road_id', 'init_s', 'init_t']:
                self._args[name] = get_random_spawn_point(self._test_case)[name]
        self.stmt_to_ast()

class MethodStatement(Statement):

    def __init__(self, test_case: tc.TestCase, class_name: str, callee: str, method_name: str, args: dict):
        super().__init__(test_case)
        self._class_name = class_name
        self._callee = callee
        self._method_name = method_name
        self._args = args
        self._ast_node = None

    @property
    def method_name(self):
        return self._method_name

    def clone(self, test_case: tc.TestCase):
        clone_args = {}
        for arg_name, arg_value in self.args.items():
            clone_args[arg_name] = arg_value
        return MethodStatement(test_case, self.class_name, copy.deepcopy(self.callee), copy.deepcopy(self.method_name), clone_args)

    def stmt_to_ast(self):
        args = [ast.Constant(value=value) for value in self._args.values()]
        call = ast.Call(
            func=ast.Attribute(attr=self._method_name,
                               ctx=ast.Load(),
                               value=ast.Name(id=self._callee, ctx=ast.Load())),
            args=args,
            keywords=[],
        )
        self._ast_node = ast.Expr(value=call)

    def mutate_road_method(self, road: ConstructorStatement):
        road_length = road.args['length']
        road_lane_num = road.args['lane_num']
        road_start_curv = road.args['curv_start']
        road_end_curv = road.args['curv_end']

        if self.method_name == 'contract':
            if road_lane_num == config.scenario_config.__dict__['lane_num'][0]:
                return False
            self.args['start_position'] = polynomial_mutate([self.args['start_position']], [0.5 * road_length],
                                                            [road_length - 20], config.ga_config.polynomial_distribution,
                                                            config.ga_config.polynomial_prob)[0]

            self.args['deformation_length'] = polynomial_mutate([self.args['deformation_length']], [20],
                                                                [road_length - float(self.args['start_position'])], config.ga_config.polynomial_distribution,
                                                                config.ga_config.polynomial_prob)[0]

        elif self.method_name == 'expand':
            if road_lane_num == config.scenario_config.__dict__['lane_num'][1] - 1:
                return False
            self.args['start_position'] = polynomial_mutate([self.args['start_position']], [0],
                                                            [0.5 * road_length], config.ga_config.polynomial_distribution,
                                                            config.ga_config.polynomial_prob)[0]

            self.args['deformation_length'] = polynomial_mutate([self.args['deformation_length']], [10.0],
                                                                [0.5 * road_length], config.ga_config.polynomial_distribution,
                                                                 config.ga_config.polynomial_prob)[0]

        elif self.method_name == 'merge':
            if road_lane_num == 2:
                print('return because cur road lane num is 2, cannot merge.')
                return False
            self.args['start_position'] = polynomial_mutate([self.args['start_position']], [0.5 * road_length],
                                                            [road_length - 10.0], config.ga_config.polynomial_distribution,
                                                            config.ga_config.polynomial_prob)[0]

            self.args['curvature'] = polynomial_mutate([self.args['curvature']], [config.scenario_config.curv_start[0]],
                                                            [road_start_curv], config.ga_config.polynomial_distribution,
                                                            config.ga_config.polynomial_prob)[0]

            self.args['lanes'] = randomness.next_int(1, int(road_lane_num / 2) + 1)

        elif self.method_name == 'split':
            if road_lane_num == 2:
                # return because cur road lane num is 2, cannot split.
                return False
            self.args['start_position'] = polynomial_mutate([self.args['start_position']], [5],
                                                            [0.5 * road_length], config.ga_config.polynomial_distribution,
                                                            config.ga_config.polynomial_prob)[0]

            self.args['curvature'] = polynomial_mutate([self.args['curvature']], [config.scenario_config.curv_end[0]],
                                                       [road_end_curv], config.ga_config.polynomial_distribution,
                                                       config.ga_config.polynomial_prob)[0]

            self.args['lanes'] = randomness.next_int(1, int(road_lane_num / 2) + 1)

        self.stmt_to_ast()
        return True

    def avfuzzer_mutate(self):
        var = []
        lb = []
        ub = []
        for arg_name, arg_value in self._args.items():
            if isinstance(arg_value, str):
                continue
            elif isinstance(arg_value, int):
                self._args[arg_name] = randomness.choice([-1, 1])
            else:
                var.append(arg_value)
                lb.append(config.scenario_config.__dict__[arg_name][0])
                ub.append(config.scenario_config.__dict__[arg_name][1])

        mut_var: list = polynomial_mutate(var, lb, ub, config.ga_config.polynomial_distribution,
                                          config.ga_config.polynomial_prob)

        for name, value in self._args.items():
            if isinstance(value, float):
                self._args[name] = mut_var.pop(0)
                print(self._args[name])

        self.stmt_to_ast()

    def mutate(self):
        var = []
        lb = []
        ub = []
        for arg_name, arg_value in self._args.items():
            if isinstance(arg_value, str):
                continue
            elif isinstance(arg_value, int):
                self._args[arg_name] = randomness.choice([-1, 1])
            else:
                var.append(arg_value)
                lb.append(config.scenario_config.__dict__[arg_name][0])
                ub.append(config.scenario_config.__dict__[arg_name][1])

        mut_var: list = polynomial_mutate(var, lb, ub, config.ga_config.polynomial_distribution,
                                          config.ga_config.polynomial_prob)

        for name, value in self._args.items():
            if isinstance(value, float):
                self._args[name] = mut_var.pop(0)
                print(self._args[name])

        # mutate the callee
        self._callee = randomness.choice(self._test_case.get_callees())
        self.stmt_to_ast()


if __name__ == '__main__':
    pass
