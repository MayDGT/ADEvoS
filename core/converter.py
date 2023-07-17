import dataclasses
import random
from typing import List
import os
from scenariogeneration import xosc, xodr
import core.chromosome as chromosome
import core.statement as stmt
import numpy as np
from utils import randomness


@dataclasses.dataclass
class Geometry:
    start_curv: float
    end_curv: float
    length: float


@dataclasses.dataclass
class Road:
    geo: Geometry
    id: int
    lane_num: int
    width: float


class RoadConverter:
    def __init__(self, test_case_chromosome: chromosome.TestCaseChromosome):
        self._test_case_chromosome = test_case_chromosome
        self.odr = xodr.OpenDrive("myroad")
        self.roads = []
        self.road_data = []
        self.common_roads: List[xodr.Road] = []
        self.junction_roads: List[xodr.Road] = []
        self.junctions = []
        self.road_lane_num = []
        self.transition_roads = []
        self.roads_for_spawn = []

    def preprocess(self):
        for i in range(len(self._test_case_chromosome.test_case.road_statements)):
            st = self._test_case_chromosome.test_case.road_statements[i]
            suc_st = self._test_case_chromosome.test_case.road_statements[i + 1] \
                if i + 1 < len(self._test_case_chromosome.test_case.road_statements) else None

            if isinstance(st, stmt.ConstructorStatement):
                road_data = Road(Geometry(st.args['curv_start'], st.args['curv_end'], st.args['length']), id=len(self.roads), lane_num=st.args['lane_num'],
                                 width=st.args['lane_width'])
                self.road_data.append(road_data)
                road = xodr.create_road(
                    geometry=[xodr.Spiral(road_data.geo.start_curv, road_data.geo.end_curv, road_data.geo.length)],
                    id=len(self.roads),
                    left_lanes=0,
                    right_lanes=road_data.lane_num,
                    lane_width=road_data.width)
                road_lane_num = self._test_case_chromosome.test_factory.calculate_road_lane_num(st, suc_st)

                self.road_lane_num.append(road_lane_num)
                if suc_st is not None and isinstance(suc_st, stmt.MethodStatement):
                    if suc_st.method_name == 'contract':
                        new_road = self.contract(road_data, road, suc_st.args['start_position'],
                                                 suc_st.args['deformation_length'])
                        self.roads.append(new_road)
                        self.roads_for_spawn.append([road_data])
                        if i > 0:
                            self.connect(self.road_data[-2], self.road_data[-1], self.roads[-2], self.roads[-1],
                                         self.road_lane_num[-2], self.road_lane_num[-1])

                    elif suc_st.method_name == 'expand':
                        new_road = self.expand(road_data, road, suc_st.args['start_position'],
                                               suc_st.args['deformation_length'])
                        self.roads.append(new_road)
                        self.roads_for_spawn.append([road_data])
                        if i > 0:
                            self.connect(self.road_data[-2], self.road_data[-1], self.roads[-2], self.roads[-1],
                                         self.road_lane_num[-2], self.road_lane_num[-1])
                    elif suc_st.method_name == 'merge':
                        new_roads, junction_roads, junction = self.merge(road_data, road, suc_st.args['start_position'],
                                                                         suc_st.args['curvature'], suc_st.args['lanes'])

                        for new_road in new_roads:
                            self.roads.append(new_road)

                        for junction_road in junction_roads:
                            self.junction_roads.append(junction_road)
                        self.junctions.append(junction)
                        if i > 0:
                            self.connect(self.road_data[-2], self.road_data[-1], self.roads[-4], self.roads[-3],
                                         self.road_lane_num[-2], self.road_lane_num[-1])
                    elif suc_st.method_name == 'split':
                        new_roads, junction_roads, junction = self.split(road_data, road, suc_st.args['start_position'],
                                                                         suc_st.args['curvature'], suc_st.args['lanes'])
                        for new_road in new_roads:
                            self.roads.append(new_road)

                        for junction_road in junction_roads:
                            self.junction_roads.append(junction_road)
                        self.junctions.append(junction)
                        if i > 0:
                            self.connect(self.road_data[-2], self.road_data[-1], self.roads[-4], self.roads[-3],
                                         self.road_lane_num[-2], self.road_lane_num[-1])
                elif suc_st is None or isinstance(suc_st, stmt.ConstructorStatement):
                    self.roads.append(road)
                    self.roads_for_spawn.append([road_data])
                    if i > 0:
                        self.connect(self.road_data[-2], self.road_data[-1], self.roads[-2], self.roads[-1],
                                     self.road_lane_num[-2], self.road_lane_num[-1])

    def connect(self, pre_road_data: Road, road_data: Road, pre_road: xodr.Road, road: xodr.Road,
                pre_road_lane_num: list, road_lane_num: list):
        pre_road_width = pre_road.lanes.lanesections[0].rightlanes[0].get_width(0)
        road_width = road.lanes.lanesections[0].rightlanes[0].get_width(0)
        transition_road = None
        if pre_road_lane_num[1] == road_lane_num[0]:
            # directly connect
            transition_road = xodr.create_road(
                geometry=[xodr.Spiral(pre_road_data.geo.end_curv, road_data.geo.start_curv, 20)],
                id=50 + len(self.transition_roads),
                left_lanes=0,
                right_lanes=pre_road_lane_num[1],
                lane_width=pre_road_data.width)
            for i in range(pre_road_lane_num[1]):
                coeff = self.get_coeff_for_poly3(20, pre_road_width, road_width)
                transition_road.lanes.lanesections[0].rightlanes[i].add_lane_width(a=coeff[0], b=coeff[1], c=coeff[2],
                                                                                   d=coeff[3])

        elif pre_road_lane_num[1] > road_lane_num[0]:
            # self-merge
            transition_road = xodr.create_road(
                geometry=[xodr.Spiral(pre_road_data.geo.end_curv, road_data.geo.start_curv, 20)],
                id=50 + len(self.transition_roads),
                left_lanes=0,
                right_lanes=pre_road_lane_num[1],
                lane_width=pre_road_data.width)
            for i in range(pre_road_lane_num[1]):
                coeff = self.get_coeff_for_poly3(20, pre_road_width, road_width)
                transition_road.lanes.lanesections[0].rightlanes[i].add_lane_width(a=coeff[0], b=coeff[1], c=coeff[2],
                                                                                   d=coeff[3])
            coeff1 = self.get_coeff_for_poly3(20, pre_road_width, 0)
            transition_road.lanes.lanesections[0].rightlanes[-1].add_lane_width(a=coeff1[0], b=coeff1[1], c=coeff1[2],
                                                                                d=coeff1[3])
        elif pre_road_lane_num[1] < road_lane_num[0]:
            # self-split
            transition_road = xodr.create_road(
                geometry=[xodr.Spiral(pre_road_data.geo.end_curv, road_data.geo.start_curv, 20)],
                id=50 + len(self.transition_roads),
                left_lanes=0,
                right_lanes=road_lane_num[0],
                lane_width=pre_road_data.width)
            for i in range(road_lane_num[0]):
                coeff = self.get_coeff_for_poly3(20, pre_road_width, road_width)
                transition_road.lanes.lanesections[0].rightlanes[i].add_lane_width(a=coeff[0], b=coeff[1], c=coeff[2],
                                                                                   d=coeff[3])
            coeff1 = self.get_coeff_for_poly3(20, 0, road_width)
            transition_road.lanes.lanesections[0].rightlanes[-1].add_lane_width(a=coeff1[0], b=coeff1[1], c=coeff1[2],
                                                                                d=coeff1[3])

        self.transition_roads.append(transition_road)

        transition_road.add_predecessor(xodr.ElementType.road, pre_road.id, xodr.ContactPoint.end)
        transition_road.add_successor(xodr.ElementType.road, road.id, xodr.ContactPoint.start)
        pre_road.add_successor(xodr.ElementType.road, transition_road.id, xodr.ContactPoint.start)
        road.add_predecessor(xodr.ElementType.road, transition_road.id, xodr.ContactPoint.end)

    def convert(self):
        self.preprocess()

        for road in self.roads:
            self.odr.add_road(road)
        for transition_road in self.transition_roads:
            self.odr.add_road(transition_road)
        for junction_road in self.junction_roads:
            self.odr.add_road(junction_road)
        for junction in self.junctions:
            self.odr.add_junction(junction)

        self.odr.adjust_startpoints()
        path = '{your_path}'
        self.odr.write_xml(path)

    def contract(self, road_data: Road, road: xodr.Road, start_position, deformation_length):
        coeff0 = self.get_coeff_for_poly3(road_data.geo.length, road_data.width, 0, deformation_length)
        road.lanes.lanesections[0].rightlanes[-1].add_lane_width(a=coeff0[0], b=coeff0[1], c=coeff0[2], d=coeff0[3],
                                                                 soffset=start_position)

        coeff1 = self.get_coeff_for_poly3(road_data.geo.length - start_position + deformation_length, 0, 0)
        road.lanes.lanesections[0].rightlanes[-1].add_lane_width(a=coeff1[0], b=coeff1[1], c=coeff1[2], d=coeff1[3],
                                                                 soffset=start_position + deformation_length)

        return road

    def expand(self, road_data: Road, road: xodr.Road, start_position, deformation_length):
        road.lanes.lanesections[0].add_right_lane(xodr.Lane(a=road_data.width))

        coeff0 = self.get_coeff_for_poly3(start_position, 0, 0)
        road.lanes.lanesections[0].rightlanes[-1].add_lane_width(a=coeff0[0], b=coeff0[1], c=coeff0[2], d=coeff0[3])

        coeff1 = self.get_coeff_for_poly3(road_data.geo.length - start_position, 0, road_data.width, deformation_length)
        road.lanes.lanesections[0].rightlanes[-1].add_lane_width(a=coeff1[0], b=coeff1[1], c=coeff1[2], d=coeff1[3],
                                                                 soffset=start_position)

        coeff2 = self.get_coeff_for_poly3(road_data.geo.length - start_position - deformation_length, road_data.width,
                                          road_data.width)
        road.lanes.lanesections[0].rightlanes[-1].add_lane_width(a=coeff2[0], b=coeff2[1], c=coeff2[2], d=coeff2[3],
                                                                 soffset=start_position + deformation_length)

        return road

    def merge(self, road_data: Road, road: xodr.Road, start_position, angle, merge_lanes: int):
        junction_length = 1

        middle_curvature1 = road_data.geo.start_curv + (
                road_data.geo.end_curv - road_data.geo.start_curv) * start_position / road_data.geo.length
        middle_curvature2 = middle_curvature1 + (road_data.geo.end_curv - middle_curvature1) * junction_length / (
                road_data.geo.length - start_position)
        pre_main_road = xodr.create_road(geometry=[xodr.Spiral(road_data.geo.start_curv,
                                                               middle_curvature1,
                                                               start_position)],
                                         id=len(self.roads),
                                         left_lanes=0,
                                         right_lanes=road_data.lane_num - merge_lanes,
                                         lane_width=road_data.width)
        pre_main_road_data = Road(Geometry(road_data.geo.start_curv, middle_curvature1, start_position),
                                    id=len(self.roads), lane_num=road_data.lane_num - merge_lanes, width=road_data.width)

        merge_road = xodr.create_road(geometry=[xodr.Spiral(angle,
                                                            middle_curvature1,
                                                            start_position)],
                                      id=len(self.roads) + 1,
                                      left_lanes=0,
                                      right_lanes=merge_lanes,
                                      lane_width=road_data.width)
        merge_road_data = Road(Geometry(angle, middle_curvature1, start_position),
                                    id=len(self.roads) + 1, lane_num=merge_lanes, width=road_data.width)

        suc_main_road = xodr.create_road(geometry=[xodr.Spiral(middle_curvature2,
                                                               road_data.geo.end_curv,
                                                               road_data.geo.length - start_position - junction_length)],
                                         id=len(self.roads) + 2,
                                         left_lanes=0,
                                         right_lanes=road_data.lane_num,
                                         lane_width=road_data.width)
        suc_main_road_data = Road(Geometry(middle_curvature2, road_data.geo.end_curv, road_data.geo.length - start_position - junction_length),
                                    id=len(self.roads) + 2, lane_num=road_data.lane_num, width=road_data.width)

        self.roads_for_spawn.append([pre_main_road_data, merge_road_data, suc_main_road_data])

        junction_id = 100 + int(len(self.junction_roads) / 2)

        junction_road1 = xodr.create_road(geometry=[xodr.Spiral(middle_curvature1,
                                                                middle_curvature2,
                                                                junction_length)],
                                          id=100 + len(self.junction_roads),
                                          left_lanes=0,
                                          right_lanes=road_data.lane_num - merge_lanes,
                                          lane_width=road_data.width,
                                          road_type=junction_id)
        junction_road2 = xodr.create_road(geometry=[xodr.Spiral(angle,
                                                                middle_curvature2,
                                                                junction_length)],
                                          id=101 + len(self.junction_roads),
                                          left_lanes=0,
                                          right_lanes=merge_lanes,
                                          lane_width=road_data.width,
                                          road_type=junction_id)

        laneoffset = -1 * (road_data.lane_num - merge_lanes)
        pre_main_road.add_successor(xodr.ElementType.junction, junction_id)
        suc_main_road.add_predecessor(xodr.ElementType.junction, junction_id)
        merge_road.add_successor(xodr.ElementType.junction, junction_id)
        junction_road1.add_successor(xodr.ElementType.road, suc_main_road.id, xodr.ContactPoint.start)
        junction_road2.add_successor(xodr.ElementType.road, suc_main_road.id, xodr.ContactPoint.start,
                                     lane_offset=laneoffset)
        junction_road1.add_predecessor(xodr.ElementType.road, pre_main_road.id, xodr.ContactPoint.end)
        junction_road2.add_predecessor(xodr.ElementType.road, merge_road.id, xodr.ContactPoint.end)

        junction = xodr.create_junction([junction_road1, junction_road2], junction_id,
                                        [pre_main_road, merge_road, suc_main_road])
        return [pre_main_road, merge_road, suc_main_road], [junction_road1, junction_road2], junction

    def split(self, road_data: Road, road: xodr.Road, start_position, angle, split_lanes: int):
        junction_length = 1

        middle_curvature1 = road_data.geo.start_curv + (road_data.geo.end_curv - road_data.geo.start_curv) * (
                start_position - junction_length) / road_data.geo.length
        middle_curvature2 = middle_curvature1 + (road_data.geo.end_curv - middle_curvature1) * junction_length / (
                road_data.geo.length - start_position + junction_length)

        pre_main_road = xodr.create_road(geometry=[xodr.Spiral(road_data.geo.start_curv,
                                                               middle_curvature1,
                                                               start_position - junction_length)],
                                         id=len(self.roads),
                                         left_lanes=0,
                                         right_lanes=road_data.lane_num,
                                         lane_width=road_data.width)
        pre_main_road_data = Road(Geometry(road_data.geo.start_curv, middle_curvature1, start_position - junction_length),
                                  id=len(self.roads), lane_num=road_data.lane_num, width=road_data.width)

        split_road = xodr.create_road(geometry=[xodr.Spiral(road_data.geo.start_curv,
                                                            angle,
                                                            road_data.geo.length - start_position)],
                                      id=1 + len(self.roads),
                                      left_lanes=0,
                                      right_lanes=split_lanes,
                                      lane_width=road_data.width)
        split_road_data = Road(Geometry(road_data.geo.start_curv, angle, road_data.geo.length - start_position),
                               id=len(self.roads) + 1, lane_num=split_lanes, width=road_data.width)

        suc_main_road = xodr.create_road(geometry=[xodr.Spiral(middle_curvature2,
                                                               road_data.geo.end_curv,
                                                               road_data.geo.length - start_position)],
                                         id=2 + len(self.roads),
                                         left_lanes=0,
                                         right_lanes=road_data.lane_num - split_lanes,
                                         lane_width=road_data.width)
        suc_main_road_data = Road(Geometry(middle_curvature2, road_data.geo.end_curv,
                                           road_data.geo.length - start_position),
                                  id=len(self.roads) + 2, lane_num=road_data.lane_num - split_lanes, width=road_data.width)

        self.roads_for_spawn.append([pre_main_road_data, split_road_data, suc_main_road_data])

        junction_id = 100 + len(self.junctions)
        junction_road1 = xodr.create_road(geometry=[xodr.Spiral(middle_curvature1,
                                                                middle_curvature2,
                                                                junction_length)],
                                          id=100 + len(self.junction_roads),
                                          left_lanes=0,
                                          right_lanes=road_data.lane_num,
                                          lane_width=road_data.width,
                                          road_type=junction_id)
        junction_road2 = xodr.create_road(geometry=[xodr.Spiral(middle_curvature1,
                                                                angle,
                                                                junction_length)],
                                          id=101 + len(self.junction_roads),
                                          left_lanes=0,
                                          right_lanes=split_lanes,
                                          lane_width=road_data.width,
                                          road_type=junction_id)

        laneoffset = -1 * (road_data.lane_num - split_lanes)
        pre_main_road.add_successor(xodr.ElementType.junction, junction_id)
        suc_main_road.add_predecessor(xodr.ElementType.junction, junction_id)
        split_road.add_predecessor(xodr.ElementType.junction, junction_id)
        junction_road1.add_successor(xodr.ElementType.road, suc_main_road.id, xodr.ContactPoint.start)
        junction_road2.add_successor(xodr.ElementType.road, split_road.id, xodr.ContactPoint.start)
        junction_road1.add_predecessor(xodr.ElementType.road, pre_main_road.id, xodr.ContactPoint.end)
        junction_road2.add_predecessor(xodr.ElementType.road, pre_main_road.id, xodr.ContactPoint.end,
                                       lane_offset=laneoffset)

        junction = xodr.create_junction([junction_road1, junction_road2], junction_id,
                                        [pre_main_road, split_road, suc_main_road])
        return [pre_main_road, split_road, suc_main_road], [junction_road1, junction_road2], junction

    def update_id(self):
        for i in range(len(self.common_roads)):
            self.common_roads[i].id = i

    def connect_without_junctions(self, index1, index2):
        """Directly connect two roads"""
        lane_num_of_road1 = self.roads[index1].lane_num
        lane_num_of_road2 = self.roads[index2].lane_num
        road1_length = self.roads[index1].geo.length
        road2_length = self.roads[index2].geo.length
        road1_width = self.roads[index1].width
        road2_width = self.roads[index2].width

        if lane_num_of_road1 < lane_num_of_road2:  # road2 split
            coeff = self.get_coeff_for_poly3(road2_length, 0, road2_width)
            self.common_roads[index2].lanes.lanesections[0].rightlanes[-1].add_lane_width(a=coeff[0], b=coeff[1],
                                                                                          c=coeff[2], d=coeff[3])
            coeff = self.get_coeff_for_poly3(road2_length, road2_width, road2_width)
            self.common_roads[index2].lanes.lanesections[0].rightlanes[-1].add_lane_width(a=coeff[0], b=coeff[1],
                                                                                          c=coeff[2], d=coeff[3],
                                                                                          soffset=20)
            if index2 == len(self.roads) - 1:  # the last road
                coeff = self.get_coeff_for_poly3(road2_length, road2_width, road2_width)
                self.common_roads[index2].lanes.lanesections[0].rightlanes[-1].add_lane_width(a=coeff[0], b=coeff[1],
                                                                                              c=coeff[2], d=coeff[3],
                                                                                              soffset=20)
        elif lane_num_of_road1 > lane_num_of_road2:  # road1 merge
            coeff = self.get_coeff_for_poly3(road1_length, road1_width, 0)
            self.common_roads[index1].lanes.lanesections[0].rightlanes[-1].add_lane_width(a=coeff[0], b=coeff[1],
                                                                                          c=coeff[2], d=coeff[3],
                                                                                          soffset=road1_length - 20)

        for i in range(min(lane_num_of_road1, lane_num_of_road2)):
            coeff = self.get_coeff_for_poly3(road1_length, road1_width, road2_width)
            if i == min(lane_num_of_road1, lane_num_of_road2) - 1 and \
                    self.common_roads[index1].lanes.lanesections[0].rightlanes[i].get_width(0) == 0:
                self.common_roads[index1].lanes.lanesections[0].rightlanes[i].add_lane_width(a=coeff[0], b=coeff[1],
                                                                                             c=coeff[2], d=coeff[3],
                                                                                             soffset=20)
            else:
                self.common_roads[index1].lanes.lanesections[0].rightlanes[i].add_lane_width(a=coeff[0], b=coeff[1],
                                                                                             c=coeff[2], d=coeff[3])

        self.common_roads[index1].add_successor(xodr.ElementType.road, index2, xodr.ContactPoint.start)
        self.common_roads[index2].add_predecessor(xodr.ElementType.road, index1, xodr.ContactPoint.end)

    def check_validity(self, index1, index2, index3):
        """check if the three segments could be linked directly.
        4 2 2 cannot be linked directly."""
        lane_num_of_road1 = self.roads[index1].lane_num
        lane_num_of_road2 = self.roads[index2].lane_num
        lane_num_of_road3 = self.roads[index3].lane_num
        if abs(lane_num_of_road1 - lane_num_of_road2) >= 2 or abs(lane_num_of_road2 - lane_num_of_road3) >= 2:
            return False
        return True

    @staticmethod
    def get_coeff_for_poly3(length, start_width, end_width, deformation_length=20):
        start_heading = 0
        end_heading = 0
        s0 = 0
        s1 = length
        s2 = deformation_length  # merge/split length

        # create the linear system
        A = np.array(
            [
                [0, 1, 2 * s0, 3 * s0 ** 2],  # derivative
                [0, 1, 2 * s1, 3 * s1 ** 2],  # derivative
                [1, s0, s0 ** 2, s0 ** 3],  # point1: (0, start_width)
            ]
        )
        B = [start_heading, end_heading, start_width, end_width]

        if (start_width != 0 and end_width != 0) or (start_width == 0 and end_width == 0):
            A = np.vstack((A, np.array([1, s1, s1 ** 2, s1 ** 3])))  # point2: (length, end_width)

        else:
            if start_width == 0:
                B[0] = 2 * end_width / deformation_length
            A = np.vstack((A, np.array([1, s2, s2 ** 2, s2 ** 3])))  # point2: (deformation_length, end_width)

        return np.linalg.solve(A, B)


class ScenarioConverter:
    def __init__(self, test_case_chromosome: chromosome.TestCaseChromosome, converted_road: RoadConverter):
        self._test_case_chromosome = test_case_chromosome
        self.catalog = xosc.Catalog()
        self.road = xosc.RoadNetwork(roadfile='{your_path}')
        self.param = xosc.ParameterDeclarations()
        self.entities = xosc.Entities()
        self.init = xosc.Init()
        self.maneuver_group_set: dict[str: xosc.ManeuverGroup] = {}
        self.act = None
        self.story = None
        self.storyboard = None
        self.scenario: xosc.Scenario | None = None

        self.roads_for_spawn: list[list[Road]] = converted_road.roads_for_spawn


    @staticmethod
    def create_vehicle(vehicle_name) -> xosc.Vehicle:
        bb = xosc.BoundingBox(width=1.785, length=4.313, height=1.52, x_center=1.3105, y_center=0, z_center=0)
        fa = xosc.Axle(maxsteer=0.6108652381980153, wheeldia=0.508, track_width=1.543, xpos=2.621, zpos=0.254)
        ra = xosc.Axle(maxsteer=0, wheeldia=0.508, track_width=1.514, xpos=0, zpos=0.254)
        vehicle = xosc.Vehicle(vehicle_name, xosc.VehicleCategory.car, bb, fa, ra, max_speed=69.44444444444444,
                               max_acceleration=4.5, max_deceleration=8.0)

        return vehicle

    def init_environment_action(self):
        weather = xosc.Weather(cloudstate=xosc.CloudState.skyOff, sun=xosc.Sun(0, 0, 0),
                               fog=xosc.Fog(0.0, xosc.BoundingBox(10, 10, 10, 0, 0, 0)),
                               precipitation=xosc.Precipitation(xosc.PrecipitationType.dry, 0))
        environment = xosc.Environment(name="Environment 1", timeofday=xosc.TimeOfDay(False, 2022, 5, 20, 12, 0, 0),
                                       weather=weather, roadcondition=xosc.RoadCondition(0.0))
        environmentAction = xosc.EnvironmentAction(environment)
        self.init.add_global_action(environmentAction)

    def init_vehicle_action(self, name, road_id, init_s, init_t, speed):
        if road_id < len(self.roads_for_spawn):
            spawn_road_list = self.roads_for_spawn[road_id]
        else:
            spawn_road_list = randomness.choice(self.roads_for_spawn)
        spawn_id, spawn_s, spawn_t = 0, 0, 0

        if len(spawn_road_list) == 1:
            spawn_id = road_id
            spawn_s = init_s
            spawn_t = init_t
        else:

            pre_road = spawn_road_list[0]
            ms_road = spawn_road_list[1]
            suc_road = spawn_road_list[2]
            # pre_main_road
            if init_s < pre_road.geo.length and init_t > -1 * (pre_road.width * pre_road.lane_num):
                spawn_id = pre_road.id
                spawn_s = init_s
                spawn_t = init_t

            # middle road
            elif init_s < ms_road.geo.length and init_t < -1 * (pre_road.width * pre_road.lane_num):
                spawn_id = ms_road.id
                spawn_s = init_s
                spawn_t = init_t + pre_road.width * pre_road.lane_num

            elif init_s > ms_road.geo.length:
                spawn_id = suc_road.id
                spawn_s = init_s - ms_road.geo.length
                spawn_t = init_t


        teleportAction = xosc.TeleportAction(xosc.RoadPosition(s=spawn_s, t=spawn_t, reference_id=spawn_id,
                                                               orientation=xosc.Orientation(h=0, p=0, r=0,
                                                                                            reference=xosc.ReferenceContext.relative)))
        longitudinalAction = xosc.AbsoluteSpeedAction(speed, xosc.TransitionDynamics(shape=xosc.DynamicsShapes.step,
                                                                                     dimension=xosc.DynamicsDimension.time,
                                                                                     value=0))
        self.init.add_init_action(name, teleportAction)
        self.init.add_init_action(name, longitudinalAction)

    def set_ego_maneuverGroup(self):
        pass

    def add_action(self, entity_name, method_name, args: dict):
        if method_name == 'speedAction':
            action = xosc.AbsoluteSpeedAction(args['target_speed'],
                                              xosc.TransitionDynamics(shape=xosc.DynamicsShapes.cubic,
                                                                      dimension=xosc.DynamicsDimension.rate,
                                                                      value=args['rate']))

        elif method_name == 'laneChangeAction':
            action = xosc.RelativeLaneChangeAction(lane=args['relative_target_lane'], entity=entity_name,
                                                   target_lane_offset=args['target_lane_offset'],
                                                   transition_dynamics=xosc.TransitionDynamics(
                                                       shape=xosc.DynamicsShapes.cubic,
                                                       dimension=xosc.DynamicsDimension.time,
                                                       value=args['lane_change_time']))
        else:
            action = xosc.RelativeLaneOffsetAction(value=args['offset_distance'], entity=entity_name,
                                                   shape=xosc.DynamicsShapes.cubic, maxlatacc=args['max_lateral_acc'])

        trigger_rule = [xosc.Rule.equalTo, xosc.Rule.greaterThan, xosc.Rule.lessThan]

        trigger = xosc.ValueTrigger(name="Simulation Time", delay=0.0, conditionedge=xosc.ConditionEdge.rising,
                          valuecondition=xosc.SimulationTimeCondition(args['trigger_time'], xosc.Rule.greaterThan))
        event = xosc.Event(entity_name + ' ' + method_name + 'event', priority=xosc.Priority.parallel, maxexecution=1)
        event.add_action('action', action)
        event.add_trigger(trigger)
        maneuver = xosc.Maneuver('Maneuver')
        maneuver.add_event(event)
        maneuver_group: xosc.ManeuverGroup = self.maneuver_group_set.get(entity_name)
        maneuver_group.add_maneuver(maneuver)

    def create_act(self):
        maneuverGroup_trigger = xosc.ValueTrigger("Start When Parent Starts", delay=0.0,
                                                  conditionedge=xosc.ConditionEdge.none,
                                                  valuecondition=xosc.StoryboardElementStateCondition(
                                                      element=xosc.StoryboardElementType.story,
                                                      reference="Story 1",
                                                      state=xosc.StoryboardElementState.runningState))
        self.act = xosc.Act('Act 1', starttrigger=maneuverGroup_trigger)
        self.set_ego_maneuverGroup()
        for maneuver_group in self.maneuver_group_set.values():
            self.act.add_maneuver_group(maneuver_group)

    def create_storyboard(self):
        self.story = xosc.Story('Story 1')
        self.story.add_act(self.act)
        self.storyboard = xosc.StoryBoard(self.init)
        self.storyboard.add_story(self.story)

    def create_scenario(self):
        self.scenario = xosc.Scenario('test scenario', 'Shuncheng Tang', self.param,
                                      self.entities, self.storyboard, self.road, self.catalog, osc_minor_version=1)

    def convert(self):
        self.init_environment_action()

        for statement in self._test_case_chromosome.test_case.statements:
            if isinstance(statement, stmt.ConstructorStatement) and statement.class_name == 'NPC':
                self.entities.add_scenario_object(statement.assignee, self.create_vehicle(statement.assignee))
                self.init_vehicle_action(statement.assignee, statement.args['road_id'], statement.args['init_s'], statement.args['init_t'],
                                         statement.args['init_speed'])
            elif isinstance(statement, stmt.MethodStatement) and statement.class_name == 'NPC':
                if self.maneuver_group_set.get(statement.callee) is None:
                    maneuver_group = xosc.ManeuverGroup(statement.callee, maxexecution=1)
                    maneuver_group.add_actor(statement.callee)
                    self.maneuver_group_set[statement.callee] = maneuver_group
                self.add_action(statement.callee, statement.method_name, statement.args)
        self.create_act()
        self.create_storyboard()
        self.create_scenario()

        # generate OpenScenario file
        path = '{your_path}'
        self.scenario.write_xml(path)


if __name__ == '__main__':
    pass
