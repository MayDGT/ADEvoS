
class NPC:
    def __init__(self, road_id: int, init_s: float, init_t: float, init_speed: float):

        pass

    def speedAction(self, target_speed: float, rate: float, trigger_time: float):

        pass

    def laneChangeAction(self, relative_target_lane: int, target_lane_offset: float, lane_change_time: float, trigger_time: float):

        pass

    def laneOffsetAction(self, offset_distance: float, max_lateral_acc: float, trigger_time: float):

        pass


class Road:

    def __init__(self, curv_start: float, curv_end: float, length: float, lane_num: int, lane_width: float):

        pass

    def contract(self, start_position: float, deformation_length: float):

        pass

    def expand(self, start_position: float, deformation_length: float):

        pass

    def merge(self, start_position: float, curvature: float, lanes: int):

        pass

    def split(self, start_position: float, curvature: float, lanes: int):

        pass