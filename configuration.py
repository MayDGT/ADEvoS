from dataclasses import dataclass, field

@dataclass
class ScenarioConfiguration:
    # constructor config
    curv_start: list = field(default_factory=lambda: [-0.02, 0.02])

    curv_end: list = field(default_factory=lambda: [-0.02, 0.02])

    length: list = field(default_factory=lambda: [50, 100])

    lane_num: list = field(default_factory=lambda: [2, 5])

    lane_width: list = field(default_factory=lambda: [3.0, 4.0])

    init_s: list = field(default_factory=lambda: [100, 200])

    init_t: list = field(default_factory=lambda: [-10.0, -0.1])

    init_speed: list = field(default_factory=lambda: [0, 15])

    minD_to_ego: float = 20

    maxD_to_ego: float = 50

    # trigger config
    trigger_time: list = field(default_factory=lambda: [0, 10])

    trigger_distance: list = field(default_factory=lambda: [5, 15])

    trigger_rule: list = field(default_factory=lambda: [-1, 1])

    # speed action config
    target_speed: list = field(default_factory=lambda: [0, 20])

    rate: list = field(default_factory=lambda: [0, 5.0])

    # lane change action config
    relative_target_lane: list = field(default_factory=lambda: [-1, 1])

    target_lane_offset: list = field(default_factory=lambda: [-0.5, 0.5])

    lane_change_time: list = field(default_factory=lambda: [3, 6])

    # lane offset action config
    offset_distance: list = field(default_factory=lambda: [-1.5, 1.5])

    max_lateral_acc: list = field(default_factory=lambda: [0, 1])


@dataclass
class GAConfiguration:
    # chromosome config
    min_road_num: int = 2

    max_road_num: int = 4

    shape_change_prob = 1.0

    max_vehicle_num: int = 6

    min_action_length: int = 5

    max_action_length: int = 20

    max_testcase_size: int = 30

    min_testcase_size: int = 8

    # selection config
    tournament_size: int = 5

    # mutation config
    test_delete_probability: float = 1.0 / 3.0

    test_change_probability: float = 1.0 / 3.0

    test_insert_probability: float = 1.0 / 3.0

    polynomial_distribution: float = 5

    polynomial_prob: float = 0.5

    avfuzzer_mutation_rate: float = 0.4
    # crossover config
    crossover_rate: float = 0.8

    avfuzzer_crossover_rate: float = 0.4
    # general config
    iteration: int = 20

    elite: int = 2

    population: int = 40




@dataclass
class Configuration:
    scenario_config: ScenarioConfiguration = field(default_factory=ScenarioConfiguration)
    ga_config: GAConfiguration = field(default_factory=GAConfiguration)


configuration = Configuration()