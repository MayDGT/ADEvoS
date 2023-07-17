import ast
import dataclasses
import inspect
import importlib
import types
from utils.typesystem import TypeSystem, TypeInfo
import pynguin.configuration as config
import astpretty

@dataclasses.dataclass
class CallableData:
    module_name: str
    class_name: str
    method_name: str
    args: dict

class TestCluster:
    def __init__(self, module_name: str):
        self._module_name = module_name
        self._ast_node: ast.Module | None = None
        self._classes: list[ast.ClassDef] = []
        self._constructor_node: list[ast.FunctionDef] = []
        self._methods_nodes: list[ast.FunctionDef] = []
        self._constructor: dict[str: CallableData] = {}
        self._road_methods: list[CallableData] = []
        self._npc_methods: list[CallableData] = []

    @property
    def module_name(self):
        return self._module_name

    @property
    def ast_node(self):
        return self._ast_node

    @property
    def classes(self):
        return self._classes

    @property
    def constructor_node(self):
        return self._constructor_node

    @property
    def methods_nodes(self):
        return self._methods_nodes

    @property
    def constructor(self):
        return self._constructor

    @property
    def road_methods(self):
        return self._road_methods

    @property
    def npc_methods(self):
        return self._npc_methods

    def add_constructor(self, class_name: str, callable_data: CallableData):
        self._constructor[class_name] = callable_data

    def add_method(self, callable_data: CallableData):
        if callable_data.class_name == 'NPC':
            self._npc_methods.append(callable_data)
        else:
            self._road_methods.append(callable_data)

    def get_ast_nodes(self):
        module = importlib.import_module(self.module_name)
        source_code = inspect.getsource(module)
        self._ast_node = ast.parse(source_code, self.module_name)
        self._classes = [n for n in self._ast_node.body if isinstance(n, ast.ClassDef)]
        for cls in self._classes:
            methods = [n for n in cls.body if isinstance(n, ast.FunctionDef)]
            for method in methods:
                if method.name == '__init__':
                    self._constructor_node.append(method)
                else:
                    self._methods_nodes.append(method)

def analyse_class(class_type_info: TypeInfo, test_cluster: TestCluster):
    for method_name, method in inspect.getmembers(class_type_info.raw_type, inspect.isfunction):
        inferred_signature = TypeSystem().infer_type_info(method, config.TypeInferenceStrategy.TYPE_HINTS)
        if method_name == '__init__':
            method_data = CallableData(class_type_info.module, class_type_info.name, class_type_info.name, inferred_signature.original_parameters)
            test_cluster.add_constructor(method_data.method_name, method_data)
        else:
            method_data = CallableData(class_type_info.module, class_type_info.name, method_name, inferred_signature.original_parameters)
            test_cluster.add_method(method_data)

def analyse_module(module_name: str) -> TestCluster:
    test_cluster = TestCluster(module_name)
    module = importlib.import_module(module_name)
    class_list = list(filter(lambda x: inspect.isclass(x), vars(module).values()))
    for cls in class_list:
        class_type_info = TypeSystem().to_type_info(cls)
        analyse_class(class_type_info, test_cluster)
    return test_cluster


if __name__ == '__main__':
    test_cluster = analyse_module("scenario")
    print(test_cluster.road_methods)