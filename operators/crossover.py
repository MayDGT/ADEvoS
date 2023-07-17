import logging
import ast
from utils import randomness
from core.chromosome import TestCaseChromosome
import core.statement as stmt

class MultiPointCrossover:
    logger = logging.getLogger(__name__)

    def avfuzzer_crossover(self, parent1: TestCaseChromosome, parent2: TestCaseChromosome):
        exchange_position = randomness.next_int(1, 3)
        clone1 = parent1.clone()
        clone2 = parent2.clone()

        self.logger.info("AVFuzzer crossover_position: %d", exchange_position)
        parent1.avfuzzer_crossover(clone2, exchange_position)
        parent2.avfuzzer_crossover(clone1, exchange_position)


    def crossover(self, parent1: TestCaseChromosome, parent2: TestCaseChromosome):
        vehicle_num1 = 0
        vehicle_num2 = 0
        for statement in parent1.test_case.statements:
            if isinstance(statement, stmt.ConstructorStatement) and statement.class_name == 'NPC':
                vehicle_num1 += 1

        for statement in parent2.test_case.statements:
            if isinstance(statement, stmt.ConstructorStatement) and statement.class_name == 'NPC':
                vehicle_num2 += 1

        road_positions = []
        for i in range(1, min(parent1.test_case.road_size(), parent2.test_case.road_size())):
            if parent1.test_factory.check_road_change_validity(parent1.test_case, parent2.test_case, i) and \
                    parent2.test_factory.check_road_change_validity(parent2.test_case, parent1.test_case, i):
                road_positions.append(i)

        if road_positions:
            road_position = randomness.choice(road_positions)
        else:
            road_position = 0

        npc_position = randomness.next_int(1, min(vehicle_num1, vehicle_num2))

        clone1 = parent1.clone()
        clone2 = parent2.clone()

        self.logger.info("crossover: road position: %d, npc_position: %d", road_position, npc_position)
        parent1.crossover(clone2, road_position, [npc_position])
        parent2.crossover(clone1, road_position, [npc_position])