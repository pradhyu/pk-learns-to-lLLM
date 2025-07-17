"""
Tests for the graph query engine.
"""
import unittest
from unittest.mock import MagicMock, patch
import sys

# Mock the Neo4j module
sys.modules['neo4j'] = MagicMock()
sys.modules['neo4j.exceptions'] = MagicMock()

# Mock Neo4jConnection and Neo4jQueryError
class Neo4jConnection:
    def __init__(self, *args, **kwargs):
        self.execute_read_query = MagicMock()
        self.execute_write_query = MagicMock()

class Neo4jQueryError(Exception):
    pass

# Mock the imports
sys.modules['drools_graph_rag.graph.connection'] = MagicMock()
sys.modules['drools_graph_rag.graph.connection'].Neo4jConnection = Neo4jConnection
sys.modules['drools_graph_rag.graph.connection'].Neo4jQueryError = Neo4jQueryError

# Import the GraphQueryEngine class
from drools_graph_rag.query_engine.query_engine import GraphQueryEngine


class TestGraphQueryEngine(unittest.TestCase):
    """
    Test cases for the GraphQueryEngine class.
    """

    def setUp(self):
        """
        Set up test fixtures.
        """
        self.mock_connection = MagicMock()
        self.mock_connection.execute_read_query = MagicMock()
        self.mock_connection.execute_write_query = MagicMock()
        self.query_engine = GraphQueryEngine(self.mock_connection)

    def test_find_rules_by_name(self):
        """
        Test finding rules by name pattern.
        """
        # Mock data
        expected_result = [
            {"name": "Rule1", "package": "com.example", "salience": 100, "id": 1},
            {"name": "Rule2", "package": "com.example", "salience": 90, "id": 2}
        ]
        self.mock_connection.execute_read_query.return_value = expected_result

        # Test
        result = self.query_engine.find_rules_by_name("Rule.*")

        # Verify
        self.assertEqual(result, expected_result)
        self.mock_connection.execute_read_query.assert_called_once()
        call_args = self.mock_connection.execute_read_query.call_args[0]
        self.assertIn("(?i)Rule.*", str(call_args[1]))

    def test_find_rule_by_exact_name(self):
        """
        Test finding a rule by its exact name.
        """
        # Mock data
        expected_result = [
            {"name": "Rule1", "package": "com.example", "salience": 100, "id": 1}
        ]
        self.mock_connection.execute_read_query.return_value = expected_result

        # Test
        result = self.query_engine.find_rule_by_exact_name("Rule1")

        # Verify
        self.assertEqual(result, expected_result[0])
        self.mock_connection.execute_read_query.assert_called_once()

    def test_find_rule_by_exact_name_with_package(self):
        """
        Test finding a rule by its exact name and package.
        """
        # Mock data
        expected_result = [
            {"name": "Rule1", "package": "com.example", "salience": 100, "id": 1}
        ]
        self.mock_connection.execute_read_query.return_value = expected_result

        # Test
        result = self.query_engine.find_rule_by_exact_name("Rule1", "com.example")

        # Verify
        self.assertEqual(result, expected_result[0])
        self.mock_connection.execute_read_query.assert_called_once()
        call_args = self.mock_connection.execute_read_query.call_args[0]
        self.assertIn("package", str(call_args[1]))

    def test_find_rules_by_property(self):
        """
        Test finding rules by a specific property.
        """
        # Mock data
        expected_result = [
            {"name": "Rule1", "package": "com.example", "salience": 100, "id": 1},
            {"name": "Rule3", "package": "com.example", "salience": 100, "id": 3}
        ]
        self.mock_connection.execute_read_query.return_value = expected_result

        # Test
        result = self.query_engine.find_rules_by_property("salience", 100)

        # Verify
        self.assertEqual(result, expected_result)
        self.mock_connection.execute_read_query.assert_called_once()

    def test_find_rules_by_class_reference(self):
        """
        Test finding rules that reference a specific class.
        """
        # Mock data
        expected_result = [
            {"name": "Rule1", "package": "com.example", "salience": 100, "id": 1},
            {"name": "Rule2", "package": "com.example", "salience": 90, "id": 2}
        ]
        self.mock_connection.execute_read_query.return_value = expected_result

        # Test
        result = self.query_engine.find_rules_by_class_reference("Customer")

        # Verify
        self.assertEqual(result, expected_result)
        self.mock_connection.execute_read_query.assert_called_once()

    def test_get_rule_details(self):
        """
        Test getting detailed information about a rule.
        """
        # Mock data
        expected_result = [{
            "name": "Rule1",
            "package": "com.example",
            "salience": 100,
            "conditions": [
                {
                    "variable": "$customer",
                    "type": "Customer",
                    "constraints": [
                        {"field": "age", "operator": "<", "value": "18"}
                    ]
                }
            ],
            "actions": [
                {
                    "type": "method_call",
                    "target": "validationResult",
                    "method": "addError",
                    "arguments": ["\"Customer is too young\""]
                }
            ]
        }]
        self.mock_connection.execute_read_query.return_value = expected_result

        # Test
        result = self.query_engine.get_rule_details(1)

        # Verify
        self.assertEqual(result, expected_result[0])
        self.mock_connection.execute_read_query.assert_called_once()

    def test_find_rule_dependencies(self):
        """
        Test finding dependencies of a specific rule.
        """
        # Mock data for find_rule_by_exact_name
        rule_data = {"name": "Rule1", "package": "com.example", "salience": 100, "id": 1}
        
        # Mock data for dependencies
        parents_data = [
            {"name": "BaseRule", "package": "com.example", "relationship_type": "extends"}
        ]
        
        depends_on_data = [
            {"name": "Rule2", "package": "com.example", "relationship_type": "depends_on"}
        ]
        
        dependent_rules_data = [
            {"name": "Rule3", "package": "com.example", "relationship_type": "dependent"}
        ]
        
        # Configure mock
        self.query_engine.find_rule_by_exact_name = MagicMock(return_value=rule_data)
        
        def mock_execute_read_query(query, params):
            if "EXTENDS" in query:
                return parents_data
            elif "depends_on" in query:
                return depends_on_data
            elif "dependent" in query:
                return dependent_rules_data
            return []
            
        self.mock_connection.execute_read_query.side_effect = mock_execute_read_query

        # Test
        result = self.query_engine.find_rule_dependencies("Rule1")

        # Verify
        expected_result = {
            "rule": rule_data,
            "parents": parents_data,
            "depends_on": depends_on_data,
            "dependent_rules": dependent_rules_data
        }
        self.assertEqual(result, expected_result)
        self.query_engine.find_rule_by_exact_name.assert_called_once_with("Rule1", None)

    def test_get_all_rules(self):
        """
        Test getting all rules in the graph.
        """
        # Mock data
        expected_result = [
            {"name": "Rule1", "package": "com.example", "salience": 100, "id": 1},
            {"name": "Rule2", "package": "com.example", "salience": 90, "id": 2}
        ]
        self.mock_connection.execute_read_query.return_value = expected_result

        # Test
        result = self.query_engine.get_all_rules()

        # Verify
        self.assertEqual(result, expected_result)
        self.mock_connection.execute_read_query.assert_called_once()

    def test_get_rules_by_package(self):
        """
        Test getting all rules in a specific package.
        """
        # Mock data
        expected_result = [
            {"name": "Rule1", "package": "com.example", "salience": 100, "id": 1},
            {"name": "Rule2", "package": "com.example", "salience": 90, "id": 2}
        ]
        self.mock_connection.execute_read_query.return_value = expected_result

        # Test
        result = self.query_engine.get_rules_by_package("com.example")

        # Verify
        self.assertEqual(result, expected_result)
        self.mock_connection.execute_read_query.assert_called_once()

    def test_get_all_packages(self):
        """
        Test getting all packages in the graph.
        """
        # Mock data
        mock_result = [
            {"package": "com.example"},
            {"package": "com.example.other"}
        ]
        self.mock_connection.execute_read_query.return_value = mock_result

        # Test
        result = self.query_engine.get_all_packages()

        # Verify
        self.assertEqual(result, ["com.example", "com.example.other"])
        self.mock_connection.execute_read_query.assert_called_once()

    def test_get_all_classes(self):
        """
        Test getting all classes referenced in the graph.
        """
        # Mock data
        expected_result = [
            {"name": "Customer", "package": "com.example.model", "full_name": "com.example.model.Customer"},
            {"name": "Order", "package": "com.example.model", "full_name": "com.example.model.Order"}
        ]
        self.mock_connection.execute_read_query.return_value = expected_result

        # Test
        result = self.query_engine.get_all_classes()

        # Verify
        self.assertEqual(result, expected_result)
        self.mock_connection.execute_read_query.assert_called_once()

    def test_find_unused_rules(self):
        """
        Test finding unused rules.
        """
        # Mock data
        expected_result = [
            {"name": "UnusedRule", "package": "com.example", "salience": 50, "id": 3, "reason": "unused"}
        ]
        self.mock_connection.execute_read_query.return_value = expected_result

        # Test
        result = self.query_engine.find_unused_rules()

        # Verify
        self.assertEqual(result, expected_result)
        self.mock_connection.execute_read_query.assert_called_once()
        
    def test_find_circular_dependencies(self):
        """
        Test finding circular dependencies between rules.
        """
        # Mock data
        mock_result = [
            {
                "cycle_rules": ["Rule1 (com.example)", "Rule2 (com.example)"],
                "from_rule": "Rule1",
                "from_package": "com.example",
                "to_rule": "Rule2",
                "to_package": "com.example",
                "shared_classes": ["Customer", "Order"]
            }
        ]
        
        expected_result = [
            {
                "cycle": ["Rule1 (com.example)", "Rule2 (com.example)"],
                "from_rule": {
                    "name": "Rule1",
                    "package": "com.example"
                },
                "to_rule": {
                    "name": "Rule2",
                    "package": "com.example"
                },
                "shared_classes": ["Customer", "Order"]
            }
        ]
        
        self.mock_connection.execute_read_query.return_value = mock_result

        # Test
        result = self.query_engine.find_circular_dependencies()

        # Verify
        self.assertEqual(result, expected_result)
        self.mock_connection.execute_read_query.assert_called_once()
        
    def test_find_complex_rules(self):
        """
        Test finding complex rules.
        """
        # Mock data
        expected_result = [
            {
                "name": "ComplexRule", 
                "package": "com.example", 
                "salience": 100, 
                "id": 4,
                "condition_count": 3,
                "constraint_count": 5,
                "action_count": 2,
                "class_count": 3,
                "total_complexity": 13
            }
        ]
        self.mock_connection.execute_read_query.return_value = expected_result

        # Test
        result = self.query_engine.find_complex_rules(complexity_threshold=10)

        # Verify
        self.assertEqual(result, expected_result)
        self.mock_connection.execute_read_query.assert_called_once()
        call_args = self.mock_connection.execute_read_query.call_args[0]
        self.assertEqual(call_args[1]["complexity_threshold"], 10)
        
    def test_find_rule_patterns(self):
        """
        Test identifying rule patterns.
        """
        # Mock data for different pattern queries
        high_salience_rules = [
            {"name": "HighPriorityRule", "package": "com.example", "salience": 100, "id": 5, "pattern": "high_salience"}
        ]
        
        no_conditions_rules = [
            {"name": "AlwaysFireRule", "package": "com.example", "salience": 50, "id": 6, "pattern": "no_conditions"}
        ]
        
        no_actions_rules = [
            {"name": "NoEffectRule", "package": "com.example", "salience": 40, "id": 7, "pattern": "no_actions"}
        ]
        
        broad_rules = [
            {
                "name": "BroadRule", 
                "package": "com.example", 
                "salience": 30, 
                "id": 8, 
                "pattern": "broad_rule",
                "condition_count": 4,
                "constraint_count": 2
            }
        ]
        
        specific_rules = [
            {
                "name": "SpecificRule", 
                "package": "com.example", 
                "salience": 20, 
                "id": 9, 
                "pattern": "specific_rule",
                "condition_count": 1,
                "constraint_count": 5
            }
        ]
        
        # Configure mock to return different results for different queries
        def mock_execute_read_query(query, params=None):
            if "salience IS NOT NULL AND r.salience > 50" in query:
                return high_salience_rules
            elif "NOT EXISTS" in query and "HAS_CONDITION" in query and "HAS_ACTION" not in query:
                return no_conditions_rules
            elif "NOT EXISTS" in query and "HAS_ACTION" in query:
                return no_actions_rules
            elif "condition_count > 2" in query:
                return broad_rules
            elif "condition_count <= 2" in query:
                return specific_rules
            return []
            
        self.mock_connection.execute_read_query.side_effect = mock_execute_read_query

        # Test
        result = self.query_engine.find_rule_patterns()

        # Verify
        expected_result = {
            "high_salience_rules": high_salience_rules,
            "no_conditions_rules": no_conditions_rules,
            "no_actions_rules": no_actions_rules,
            "broad_rules": broad_rules,
            "specific_rules": specific_rules
        }
        
        self.assertEqual(result, expected_result)
        self.assertEqual(self.mock_connection.execute_read_query.call_count, 5)

    def test_find_conflicting_rules(self):
        """
        Test finding conflicting rules.
        """
        # Mock data
        mock_result = [
            {
                "rule1_name": "CustomerAgeValidation",
                "rule1_package": "com.example.validation",
                "rule1_salience": 100,
                "rule2_name": "CustomerAgeCheck",
                "rule2_package": "com.example.validation",
                "rule2_salience": 90,
                "fact_type": "Customer",
                "conflict_type": "potential_condition_overlap",
                "salience_diff": 10,
                "r1_vars": ["$customer"],
                "r2_vars": ["$c"],
                "r1_constraints": [{"field": "age", "operator": "<", "value": "18"}],
                "r2_constraints": [{"field": "age", "operator": "<=", "value": "18"}],
                "r1_actions": [{"type": "method_call", "target": "validationResult", "method": "addError"}],
                "r2_actions": [{"type": "method_call", "target": "validationResult", "method": "addWarning"}]
            },
            {
                "rule1_name": "OrderTotalCalculation",
                "rule1_package": "com.example.order",
                "rule1_salience": 50,
                "rule2_name": "OrderDiscountCalculation",
                "rule2_package": "com.example.order",
                "rule2_salience": 45,
                "fact_type": "Order",
                "conflict_type": "contradictory_constraints",
                "salience_diff": 5,
                "r1_vars": ["$order"],
                "r2_vars": ["$order"],
                "r1_constraints": [{"field": "status", "operator": "==", "value": "NEW"}],
                "r2_constraints": [{"field": "status", "operator": "!=", "value": "NEW"}],
                "r1_actions": [{"type": "method_call", "target": "order", "method": "calculateTotal"}],
                "r2_actions": [{"type": "method_call", "target": "order", "method": "applyDiscount"}]
            }
        ]
        
        expected_result = [
            {
                "rule1": {
                    "name": "CustomerAgeValidation",
                    "package": "com.example.validation",
                    "salience": 100
                },
                "rule2": {
                    "name": "CustomerAgeCheck",
                    "package": "com.example.validation",
                    "salience": 90
                },
                "fact_type": "Customer",
                "conflict_type": "potential_condition_overlap",
                "salience_difference": 10,
                "details": {
                    "rule1_variables": ["$customer"],
                    "rule2_variables": ["$c"],
                    "rule1_constraints": [{"field": "age", "operator": "<", "value": "18"}],
                    "rule2_constraints": [{"field": "age", "operator": "<=", "value": "18"}],
                    "rule1_actions": [{"type": "method_call", "target": "validationResult", "method": "addError"}],
                    "rule2_actions": [{"type": "method_call", "target": "validationResult", "method": "addWarning"}]
                }
            },
            {
                "rule1": {
                    "name": "OrderTotalCalculation",
                    "package": "com.example.order",
                    "salience": 50
                },
                "rule2": {
                    "name": "OrderDiscountCalculation",
                    "package": "com.example.order",
                    "salience": 45
                },
                "fact_type": "Order",
                "conflict_type": "contradictory_constraints",
                "salience_difference": 5,
                "details": {
                    "rule1_variables": ["$order"],
                    "rule2_variables": ["$order"],
                    "rule1_constraints": [{"field": "status", "operator": "==", "value": "NEW"}],
                    "rule2_constraints": [{"field": "status", "operator": "!=", "value": "NEW"}],
                    "rule1_actions": [{"type": "method_call", "target": "order", "method": "calculateTotal"}],
                    "rule2_actions": [{"type": "method_call", "target": "order", "method": "applyDiscount"}]
                }
            }
        ]
        
        self.mock_connection.execute_read_query.return_value = mock_result

        # Test
        result = self.query_engine.find_conflicting_rules()

        # Verify
        self.assertEqual(result, expected_result)
        self.mock_connection.execute_read_query.assert_called_once()

    def test_analyze_execution_order(self):
        """
        Test analyzing execution order of rules.
        """
        # Mock data
        mock_result = [
            {
                "name": "HighPriorityRule",
                "package": "com.example",
                "original_salience": 100,
                "effective_salience": 100,
                "depends_on": [],
                "dependency_count": 0,
                "rule_type": "high_priority"
            },
            {
                "name": "MediumPriorityRule",
                "package": "com.example",
                "original_salience": 50,
                "effective_salience": 50,
                "depends_on": [
                    {"name": "HighPriorityRule", "package": "com.example"}
                ],
                "dependency_count": 1,
                "rule_type": "normal"
            },
            {
                "name": "LowPriorityRule",
                "package": "com.example",
                "original_salience": 10,
                "effective_salience": 10,
                "depends_on": [
                    {"name": "MediumPriorityRule", "package": "com.example"},
                    {"name": "HighPriorityRule", "package": "com.example"}
                ],
                "dependency_count": 2,
                "rule_type": "normal"
            }
        ]
        
        # Expected processed results with execution status
        expected_result = [
            {
                "name": "HighPriorityRule",
                "package": "com.example",
                "original_salience": 100,
                "effective_salience": 100,
                "depends_on": [],
                "dependency_count": 0,
                "rule_type": "high_priority",
                "execution_status": "ready",
                "missing_dependencies": []
            },
            {
                "name": "MediumPriorityRule",
                "package": "com.example",
                "original_salience": 50,
                "effective_salience": 50,
                "depends_on": [
                    {"name": "HighPriorityRule", "package": "com.example"}
                ],
                "dependency_count": 1,
                "rule_type": "normal",
                "execution_status": "ready",
                "missing_dependencies": []
            },
            {
                "name": "LowPriorityRule",
                "package": "com.example",
                "original_salience": 10,
                "effective_salience": 10,
                "depends_on": [
                    {"name": "MediumPriorityRule", "package": "com.example"},
                    {"name": "HighPriorityRule", "package": "com.example"}
                ],
                "dependency_count": 2,
                "rule_type": "normal",
                "execution_status": "ready",
                "missing_dependencies": []
            }
        ]
        
        self.mock_connection.execute_read_query.return_value = mock_result

        # Test
        result = self.query_engine.analyze_execution_order()

        # Verify
        self.assertEqual(result, expected_result)
        self.mock_connection.execute_read_query.assert_called_once()
        
        # Test with specific rule names
        rule_names = ["HighPriorityRule", "MediumPriorityRule"]
        self.mock_connection.execute_read_query.reset_mock()
        self.mock_connection.execute_read_query.return_value = mock_result[:2]
        
        result = self.query_engine.analyze_execution_order(rule_names)
        
        self.assertEqual(len(result), 2)
        self.mock_connection.execute_read_query.assert_called_once()
        call_args = self.mock_connection.execute_read_query.call_args[0]
        self.assertIn("rule_names", str(call_args[1]))


if __name__ == "__main__":
    unittest.main()