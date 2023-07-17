from __future__ import annotations
from core.chromosome import TestCaseChromosome
from configuration import configuration as config

import core.factory as fc
from operators.selection import TournamentSelection
from operators.crossover import MultiPointCrossover
from utils import randomness, fnds, utils
import numpy as np
import logging
import ast
import time
import os
import difflib


class SearchAlgorithm:
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        chromosome_factory: fc.TestCaseChromosomeFactory
    ):

        self.chromosome_factory = chromosome_factory
        self.simulation = None
        self.iteration = 0

        self.selection = TournamentSelection()
        self.crossover = MultiPointCrossover()

        self.population: list[TestCaseChromosome] = []
        self.collisions: list[TestCaseChromosome] = []
        self.history = []

        self.start_time = round(time.time())

        self.collision_with_npc_count = 0
        self.collision_with_boundary_count = 0
        self.unique_bug = []
        self.unique_bug_count = []

        # avfuzzer
        self.avfuzzer_best_y = 999
        self.local_population = []

    def generate_tests(self):
        self.population = self.generate_random_population()
        self.eval_population()
        self.population = self.get_survivals()
        while self.iteration < config.ga_config.iteration:
            self.evolve()

            self.history.append(self.chrom2string(self.population[0]))
            self.unique_bug_count.append(len(self.unique_bug))
            # restart if needed

            if self.iteration > 2 and self.unique_bug_count[-1] == self.unique_bug_count[-2]:
                self.logger.info("restart....")
                self.population = self.generate_random_population()

            self.iteration += 1
        return self.population[0]

    def avfuzzer_generate_tests(self):
        self.population = self.avfuzzer_generate_random_population()
        self.eval_population(is_avfuzzer=True)
        while self.iteration < config.ga_config.iteration:
            self.avfuzzer_evolve()
            self.iteration += 1
            self.history.append(self.population[0].fitness)
            self.unique_bug_count.append(len(self.unique_bug))
            # restart
            if self.iteration > 5 and sum(self.history[-5:]) / 5 < self.population[0].fitness:
                self.logger.info("restart....")
                self.avfuzzer_generate_random_population()

            if self.population[0].fitness < self.avfuzzer_best_y:
                self.avfuzzer_best_y = self.population[0].fitness
                if self.iteration > 1:
                    # local fuzz
                    self.logger.info("start local fuzz")
                    self.local_population.clear()
                    for i in range(config.ga_config.population):
                        self.local_population.append(self.population[0])
                    self.population.append(self.local_fuzz())
                    self.population.sort(key=lambda x: x.fitness)
                    self.population = self.population[: config.ga_config.population]

    def local_fuzz(self):
        local_iteration = 0
        while local_iteration < 1:
            new_generation = []

            while len(new_generation) < config.ga_config.population:
                parent1 = self.selection.avfuzzer_select(self.local_population, 2)[0]
                parent2 = self.selection.avfuzzer_select(self.local_population, 2)[0]
                offspring1 = parent1.clone()
                offspring2 = parent2.clone()

                self.logger.info("parent 1: %s", self.chrom2string(parent1))
                self.logger.info("parent 2: %s", self.chrom2string(parent2))

                if randomness.next_float() <= config.ga_config.avfuzzer_crossover_rate:
                    self.crossover.avfuzzer_crossover(offspring1, offspring2)

                self.logger.info("offspring 1 after crossover: %s", self.chrom2string(offspring1))
                self.logger.info("offspring 2 after crossover: %s", self.chrom2string(offspring2))

                if randomness.next_float() <= config.ga_config.avfuzzer_mutation_rate:
                    offspring1.avfuzzer_mutation()

                if randomness.next_float() <= config.ga_config.avfuzzer_mutation_rate:
                    offspring2.avfuzzer_mutation()

                self.logger.info("offspring 1 after mutation: %s", self.chrom2string(offspring1))
                self.logger.info("offspring 2 after mutation: %s", self.chrom2string(offspring2))

                new_generation.append(offspring1)
                new_generation.append(offspring2)

            self.eval_population(new_generation, is_avfuzzer=True)
            population = self.local_population + new_generation
            population.sort(key=lambda x: x.fitness)
            self.local_population = population[: config.ga_config.population]
            local_iteration += 1
            self.iteration += 1
        return self.local_population[0]

    def avfuzzer_generate_random_population(self):
        population = []
        while len(population) < config.ga_config.population:
            chrom = self.chromosome_factory.avfuzzer_generate_chromosome()
            population.append(chrom)
        return population

    def avfuzzer_evolve(self):
        new_generation = []

        while len(new_generation) < config.ga_config.population:
            parent1 = self.selection.avfuzzer_select(self.population, 2)[0]
            parent2 = self.selection.avfuzzer_select(self.population, 2)[0]
            offspring1 = parent1.clone()
            offspring2 = parent2.clone()

            self.logger.info("parent 1: %s", self.chrom2string(parent1))
            self.logger.info("parent 2: %s", self.chrom2string(parent2))

            if randomness.next_float() <= config.ga_config.avfuzzer_crossover_rate:
                self.crossover.avfuzzer_crossover(offspring1, offspring2)

            self.logger.info("offspring 1 after crossover: %s", self.chrom2string(offspring1))
            self.logger.info("offspring 2 after crossover: %s", self.chrom2string(offspring2))

            if randomness.next_float() <= config.ga_config.avfuzzer_mutation_rate:
                offspring1.avfuzzer_mutation()
            if randomness.next_float() <= config.ga_config.avfuzzer_mutation_rate:
                offspring2.avfuzzer_mutation()

            self.logger.info("offspring 1 after mutation: %s", self.chrom2string(offspring1))
            self.logger.info("offspring 2 after mutation: %s", self.chrom2string(offspring2))

            new_generation.append(offspring1)
            new_generation.append(offspring2)

        self.eval_population(new_generation, is_avfuzzer=True)
        population = self.population + new_generation

        population.sort(key=lambda x: x.fitness)
        self.population = population[: config.ga_config.population]

    def random_generation(self):
        while self.iteration < config.ga_config.iteration:
            self.population = self.generate_random_population()
            self.eval_population(self.population)
            self.iteration += 1
        return self.population[0]

    def generate_random_population(self):
        population = []
        while len(population) < config.ga_config.population:
            chrom = self.chromosome_factory.generate_chromosome()
            population.append(chrom)
        return population

    def eval_population(self, population: None | list = None, is_avfuzzer: bool = False):
        pop = self.population if population is None else population
        for chrom in pop:
            self.logger.info("evaluate individual: %s", self.chrom2string(chrom))
            chrom.fitness = self.simulation.sim(chrom, is_avfuzzer)
            self.logger.info("its fitness score is: %s", str(chrom.fitness))
            self.record_metric(chrom, is_avfuzzer)
            if is_avfuzzer:
                chrom.fitness = chrom.fitness[1]

    def record_metric(self, chrom, is_avfuzzer: bool = False):
        # collision with NPC
        if chrom.fitness[0] == 0 and chrom.fitness[1] < 6.0:
            self.collision_with_npc_count += 1
            if len(self.unique_bug) == 0:
                self.unique_bug.append(self.chrom2string(chrom))

            else:
                unique_flag = 1
                for bug in self.unique_bug:
                    if difflib.SequenceMatcher(None, bug, self.chrom2string(chrom)).quick_ratio() > 0.8:
                        unique_flag = 0
                if unique_flag:
                    self.unique_bug.append(self.chrom2string(chrom))

        # collision with boundary
        if not is_avfuzzer:
            if chrom.fitness[-2] < 0.89:
                self.collision_with_boundary_count += 1

        # record these metrics
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../results",
                               "metric_{}.txt".format(self.start_time)), 'a') as f:
            f.write(str(self.collision_with_npc_count) + ' ' + str(self.collision_with_boundary_count) +
                    ' ' + str(len(self.unique_bug)) + '\n')

        # record each evaluation
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../results",
                               "result_{}.txt".format(self.start_time)), 'a') as f:

            info_dict = {
                'fitness': chrom.fitness,
                'scenario': self.chrom2string(chrom)
            }
            f.write(str(info_dict) + '\r\n')

    def get_survivals(self, population: None | list = None, n_survival: int = config.ga_config.population):
        pop: list[TestCaseChromosome] = self.population if population is None else population
        F = []
        for chrom in pop:
            F.append(chrom.fitness)

        F = np.array(F).astype(float, copy=False)
        self.logger.info("Population Fitness: %s", str(F))
        survivors = []
        fronts = fnds.fast_non_dominated_sort(F)
        self.logger.info("Fronts: %s", str(fronts))
        for k, front in enumerate(fronts):
            crowding_of_front = fnds.calc_crowding_distance(F[front, :])
            for j, i in enumerate(front):
                pop[i].rank = k
                pop[i].crowding = crowding_of_front[j]

            if len(survivors) + len(front) > n_survival:
                P = np.random.permutation(len(crowding_of_front))
                I = np.argsort(crowding_of_front[P], kind='quicksort')
                I = P[I]
                I = np.flip(I, axis=0)
            else:
                I = np.arange(len(front))

            survivors.extend(front[I])
        self.logger.info("Survivors: %s", str(survivors))
        return [pop[i] for i in survivors]

    def evolve(self):
        new_generation = []

        while len(new_generation) < config.ga_config.population:
            parent_1 = self.selection.select(self.population, 2)[0]
            parent_2 = self.selection.select(self.population, 2)[0]
            offspring_1 = parent_1.clone()
            offspring_2 = parent_2.clone()

            self.logger.info("parent 1: %s", self.chrom2string(parent_1))
            self.logger.info("parent 2: %s", self.chrom2string(parent_2))

            if randomness.next_float() <= config.ga_config.crossover_rate:
                self.crossover.crossover(offspring_1, offspring_2)

            self.logger.info("offspring 1 after crossover: %s", self.chrom2string(offspring_1))
            self.logger.info("offspring 2 after crossover: %s", self.chrom2string(offspring_2))

            offspring_1.mutate()
            offspring_2.mutate()

            self.logger.info("offspring 1 after mutation: %s", self.chrom2string(offspring_1))
            self.logger.info("offspring 2 after mutation: %s", self.chrom2string(offspring_2))

            new_generation.append(offspring_1)
            new_generation.append(offspring_2)

        self.eval_population(new_generation)
        population = self.population + new_generation

        self.population = self.get_survivals(population, n_survival=config.ga_config.population)
        self.logger.info("The best individual: %s \r\n its fitness score is %s",
                         self.chrom2string(self.population[0]), str(self.population[0].fitness))


    def elitism(self):
        elite = []
        for idx in range(config.ga_config.elite):
            elite.append(self.population[idx].clone())
        return elite

    @staticmethod
    def chrom2string(chrom: TestCaseChromosome):
        return ast.unparse(ast.fix_missing_locations(chrom.ast_node()))

    def record(self):
        # record each generation
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../results",
                               "result_{}.txt".format(self.start_time)), 'a') as f:
            for individual in self.population:
                info_dict = {
                    'fitness': individual.fitness,
                    'scenario': self.chrom2string(individual)
                }
                f.write(str(info_dict) + '\r\n')


if __name__ == '__main__':
    pass