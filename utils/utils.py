from __future__ import annotations

from typing import TYPE_CHECKING

from utils.randomness import next_int, next_float
import core.statement as stmt
if TYPE_CHECKING:
    from core.chromosome import TestCaseChromosome
    from core.testcase import TestCase


def spawn_with_pattern(test_case: TestCase, ego_args: dict):
    road = test_case.road_constructors[0]
    road_method = None
    for st in test_case.road_statements:
        if isinstance(st, stmt.MethodStatement) and st.callee == road.assignee:
            road_method = st
    road_width = road.args['lane_num'] * road.args['lane_width']
    road_length = road.args['length']
    npc_init_s = next_float(max(0, ego_args['init_s'] - 20), min(road_length, ego_args['init_s'] + 20))
    npc_init_t = -road_width + 1.75
    if road_method is not None:
        if road_method.method_name == 'contract':
            npc_init_s = next_float(min(ego_args['init_s'], road_method.args['start_position']),
                                    max(ego_args['init_s'], road_method.args['start_position']))
        if road_method.method_name == 'expand':
            npc_init_t = -road_width / 2

    return {'road_id': 0, 'init_s': npc_init_s, 'init_t': npc_init_t}

def get_surrounding_point(test_case: TestCase):
    ego_args = None
    for st in test_case.statements:
        if isinstance(st, stmt.ConstructorStatement) and st.assignee == 'Ego':
            ego_args = st.args
    ego_road_id = ego_args['road_id']
    ego_road = test_case.road_constructors[ego_road_id]
    ego_road_length = ego_road.args['length']
    ego_init_s = ego_args['init_s']


    if next_float() < 0.5:
        return spawn_with_pattern(test_case, ego_args)

    # npc to sample
    dict1 = {}
    dict2 = {}
    if ego_init_s + 20 > ego_road_length:
        npc_road_id = ego_road_id + 1
        npc_road_width = test_case.road_constructors[npc_road_id].args['lane_num'] * test_case.road_constructors[npc_road_id].args['lane_width']
        npc_init_s = next_float(ego_init_s + 20 - ego_road_length, ego_init_s + 20 - ego_road_length + 20)
        npc_init_t = next_float(-npc_road_width + 1.0, -1.0)
        dict1['road_id'] = npc_road_id
        dict1['init_s'] = npc_init_s
        dict1['init_t'] = npc_init_t
    elif ego_init_s + 20 < ego_road_length:
        npc_road_id = ego_road_id
        npc_road_width = test_case.road_constructors[npc_road_id].args['lane_num'] * \
                         test_case.road_constructors[npc_road_id].args['lane_width']
        npc_init_s = next_float(ego_init_s + 20, ego_road_length)
        npc_init_t = next_float(-npc_road_width + 1.0, -1.0)
        dict1['road_id'] = npc_road_id
        dict1['init_s'] = npc_init_s
        dict1['init_t'] = npc_init_t

    if ego_init_s - 20 > 0:
        npc_road_id = ego_road_id
        npc_road_width = test_case.road_constructors[npc_road_id].args['lane_num'] * \
                         test_case.road_constructors[npc_road_id].args['lane_width']
        npc_init_s = next_float(0, ego_init_s - 20)
        npc_init_t = next_float(-npc_road_width + 1.0, -1.0)
        dict2['road_id'] = npc_road_id
        dict2['init_s'] = npc_init_s
        dict2['init_t'] = npc_init_t

    if bool(dict2) is False:
        return dict1
    else:
        if next_float() < 0.6:
            return dict1
        else:
            return dict2



def get_random_spawn_point(test_case: TestCase, position: int | None = None):
    if position is None:
        road_id = next_int(0, test_case.road_size())
    else:
        road_id = position
    road = test_case.road_constructors[road_id]
    road_method = None
    road_length = road.args['length']
    road_width = road.args['lane_num'] * road.args['lane_width']
    out_lane_position = -1 * (road.args['lane_num'] * road.args['lane_width'] - road.args['lane_width'])
    for st in test_case.road_statements:
        if isinstance(st, stmt.MethodStatement) and st.callee == road.assignee:
            road_method = st

    init_t = next_float(-road_width + 1.0, -1.0)
    # init_s = next_float(0, road_length)
    init_s = road_length / 2
    if road_method is not None:
        if road_method.method_name == 'expand' and init_t < out_lane_position:
            init_s = next_float(road_method.args['start_position'], road_length)
        elif road_method.method_name == 'contract' and init_t < out_lane_position:
            init_s = next_float(0, road_method.args['start_position'])

    return {'road_id': road_id, 'init_s': init_s, 'init_t': init_t}




