from utils import randomness
from core.chromosome import TestCaseChromosome
from configuration import configuration as config


class TournamentSelection:
    """Tournament selection."""
    def __init__(self):
        self._maximize = False

    def select(self, population: list[TestCaseChromosome], number: int) -> list[TestCaseChromosome]:
        selection = []
        for _ in range(number):
            selection.append(population[self._get_index(population)])
        return selection

    def avfuzzer_select(self, population: list[TestCaseChromosome], number: int) -> list[TestCaseChromosome]:
        selection: list[TestCaseChromosome] = []
        for _ in range(number):
            selection.append(population[self._get_index(population, is_avfuzzer=True)])
        return selection

    def _get_index(self, population: list[TestCaseChromosome], is_avfuzzer: bool = False) -> int:
        new_num = randomness.next_int(lower_bound=0, upper_bound=len(population))
        winner = new_num

        tournament_round = 0

        while (
            tournament_round < config.ga_config.tournament_size - 1
        ):
            new_num = randomness.next_int(lower_bound=0, upper_bound=len(population))
            selected = population[new_num]

            if self._maximize:
                if sum(selected.fitness) > sum(population[winner].fitness):
                    winner = new_num
            else:
                if not is_avfuzzer:
                    if sum(selected.fitness) < sum(population[winner].fitness):
                        winner = new_num
                else:
                    if selected.fitness < population[winner].fitness:
                        winner = new_num

            tournament_round += 1

        return winner