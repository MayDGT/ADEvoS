# EvoScenario
This project is the implementation of paper: <br />
*EvoScenario: Integrating Road Structures into Critical Scenario Generation for Autonomous Driving System Testing* <br />

**Note:** This project is originally evaluated on the ADS and simulator provided by our indutry partner. The implementation on other AD stacks will be available soon.


## Dependencies
* Pynguin
* scenariogeneration

## Run
Step 1: Clone this project <br />
Step 2: Run the search algorithm <br />
         &emsp;&emsp;&emsp; ```python3 main.py```

## Project Structure
```
.
├── core 
│   ├── algorithm.py 
│   ├── chromosome.py 
│   ├── converter.py 
│   ├── factory.py 
│   ├── __init__.py
│   ├── parse_module.py
│   ├── statement.py
│   └── testcase.py
├── operators
│   ├── crossover.py
│   └── selection.py
└── utils
    ├── fnds.py
    ├── randomness.py
    ├── typesystem.py
    └── utils.py
├── Pynguin
├── __init__.py
├── main.py
├── configuration.py 
├── scenario.py
