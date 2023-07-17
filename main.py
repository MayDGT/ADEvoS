from core.parse_module import TestCluster, analyse_module
from core.factory import TestFactory, TestCaseFactory, TestCaseChromosomeFactory
from core.algorithm import SearchAlgorithm
import ast
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(filename)s : %(levelname)s  %(message)s', datefmt='%Y-%m-%d %A %H:%M:%S', filename='GA.log', filemode='w')
logger = logging.getLogger(__name__)

test_cluster = analyse_module("scenario")
test_factory = TestFactory(test_cluster)
test_case_factory = TestCaseFactory(test_factory)
chrom_factory = TestCaseChromosomeFactory(test_factory, test_case_factory)

algorithm = SearchAlgorithm(chrom_factory)

logger.info("start generate tests...")
result = algorithm.generate_tests()
