"""
Tests for the graph visualization generator.
"""
import unittest
from unittest.mock import MagicMock, patch

from drools_graph_rag.visualization.generator import GraphVisualizationGenerator
from drools_graph_rag.query_engine.query_engine import GraphQueryEngine
from drools_graph_rag.graph.connection import Neo4jConnection


class TestGraphVisualizationGenerator(unittest.TestCase):
    """Test cases for the GraphVisualizationGenerator class."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the Neo4jConnection and GraphQueryEngine
        self.mock_connection = MagicMock(spec=Neo4jConnection)
        self.mock_query_engine = MagicMock(spec=GraphQueryEngine)
        self.mock_query_engine.connection = self.mock_connection
        
        # Create the visualization generator
        self.generator = GraphVisualizationGenerator(self.mock_query_engine)

    def test_generate_rule_graph(self):
        """Test generating a rule graph."""
        # Mock the execute_read_query method to return test data
        self.mock_connection.execute_read_query.side_effect = [
            # Rule nodes
            [{"rule_nodes": [
                {"id": 1, "label": "Rule", "name": "Rule1", "package": "com.example", "salience": 100, "type": "rule"},
                {"id": 2, "label": "Rule", "name": "Rule2", "package": "com.example", "salience": 90, "type": "rule"}
            ]}],
            # Extends edges
            [{"extends_edges": [
                {"source": 1, "target": 2, "type": "extends", "label": "EXTENDS"}
            ]}],
            # Condition nodes and edges
            [{"condition_nodes": [
                {"id": 3, "label": "Condition", "variable": "$customer", "type": "Customer", "node_type": "condition"}
            ], "condition_edges": [
                {"source": 1, "target": 3, "type": "has_condition", "label": "HAS_CONDITION"}
            ]}],
            # Constraint nodes and edges
            [{"constraint_nodes": [
                {"id": 4, "label": "Constraint", "field": "age", "operator": ">", "value": "18", "node_type": "constraint"}
            ], "constraint_edges": [
                {"source": 3, "target": 4, "type": "has_constraint", "label": "HAS_CONSTRAINT"}
            ]}],
            # Action nodes and edges
            [{"action_nodes": [
                {"id": 5, "label": "Action", "type": "method_call", "target": "validationResult", "method": "addError", "node_type": "action"}
            ], "action_edges": [
                {"source": 1, "target": 5, "type": "has_action", "label": "HAS_ACTION"}
            ]}],
            # Class nodes and edges
            [{"class_nodes": [
                {"id": 6, "label": "Class", "name": "Customer", "package": "com.example.model", "full_name": "com.example.model.Customer", "node_type": "class"}
            ], "class_edges": [
                {"source": 3, "target": 6, "type": "references", "label": "REFERENCES"}
            ]}]
        ]
        
        # Call the method
        result = self.generator.generate_rule_graph()
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertEqual(len(result["nodes"]), 6)  # 2 rules, 1 condition, 1 constraint, 1 action, 1 class
        self.assertEqual(len(result["edges"]), 5)  # 1 extends, 1 has_condition, 1 has_constraint, 1 has_action, 1 references
        
        # Verify that each node has position attributes
        for node in result["nodes"]:
            self.assertIn("x", node)
            self.assertIn("y", node)

    def test_generate_rule_dependency_graph(self):
        """Test generating a rule dependency graph."""
        # Mock the find_rule_dependencies method
        self.mock_query_engine.find_rule_dependencies.return_value = {
            "rule": {"id": 1, "name": "Rule1", "package": "com.example", "salience": 100},
            "parents": [{"name": "ParentRule", "package": "com.example"}],
            "depends_on": [{"name": "DependsOnRule", "package": "com.example"}],
            "dependent_rules": [{"name": "DependentRule", "package": "com.example"}]
        }
        
        # Mock the find_rule_by_exact_name method
        self.mock_query_engine.find_rule_by_exact_name.side_effect = [
            {"id": 2, "name": "ParentRule", "package": "com.example"},
            {"id": 3, "name": "DependsOnRule", "package": "com.example"},
            {"id": 4, "name": "DependentRule", "package": "com.example"}
        ]
        
        # Call the method
        result = self.generator.generate_rule_dependency_graph("Rule1")
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertEqual(len(result["nodes"]), 4)  # Main rule + 3 related rules
        self.assertEqual(len(result["edges"]), 3)  # 1 extends, 1 depends_on, 1 dependent
        
        # Verify that the main rule is marked as focus
        main_rule = next((node for node in result["nodes"] if node["id"] == 1), None)
        self.assertIsNotNone(main_rule)
        self.assertTrue(main_rule["focus"])

    def test_generate_execution_path_graph(self):
        """Test generating an execution path graph."""
        # Mock the analyze_execution_order method
        self.mock_query_engine.analyze_execution_order.return_value = [
            {
                "id": 1,
                "name": "Rule1",
                "package": "com.example",
                "original_salience": 100,
                "effective_salience": 100,
                "depends_on": [],
                "rule_type": "entry_point"
            },
            {
                "id": 2,
                "name": "Rule2",
                "package": "com.example",
                "original_salience": 90,
                "effective_salience": 90,
                "depends_on": [{"name": "Rule1", "package": "com.example"}],
                "rule_type": "normal"
            }
        ]
        
        # Call the method
        result = self.generator.generate_execution_path_graph(["Rule1", "Rule2"])
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertEqual(len(result["nodes"]), 2)  # 2 rules
        self.assertEqual(len(result["edges"]), 1)  # 1 depends_on edge
        
        # Verify that nodes have execution order
        for i, node in enumerate(result["nodes"]):
            self.assertIn("execution_order", node)
            self.assertEqual(node["execution_order"], i + 1)

    def test_export_graph_as_json(self):
        """Test exporting graph data as JSON."""
        # Create test graph data
        graph_data = {
            "nodes": [
                {"id": 1, "name": "Rule1", "type": "rule", "x": 100, "y": 200},
                {"id": 2, "name": "Rule2", "type": "rule", "x": 300, "y": 400}
            ],
            "edges": [
                {"source": 1, "target": 2, "type": "extends", "label": "EXTENDS"}
            ]
        }
        
        # Call the method
        result = self.generator.export_graph_as_json(graph_data)
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertEqual(len(result["nodes"]), 2)
        self.assertEqual(len(result["edges"]), 1)
        
        # Verify node format
        node = result["nodes"][0]
        self.assertEqual(node["id"], "1")
        self.assertEqual(node["label"], "Rule1")
        self.assertEqual(node["type"], "rule")
        self.assertIn("position", node)
        self.assertEqual(node["position"]["x"], 100)
        self.assertEqual(node["position"]["y"], 200)
        
        # Verify edge format
        edge = result["edges"][0]
        self.assertEqual(edge["source"], "1")
        self.assertEqual(edge["target"], "2")
        self.assertEqual(edge["type"], "extends")
        self.assertEqual(edge["label"], "EXTENDS")

    def test_apply_force_directed_layout(self):
        """Test applying force-directed layout."""
        # Create test nodes and edges
        nodes = [
            {"id": 1, "name": "Node1"},
            {"id": 2, "name": "Node2"},
            {"id": 3, "name": "Node3"}
        ]
        
        edges = [
            {"source": 1, "target": 2},
            {"source": 2, "target": 3}
        ]
        
        # Call the method
        result = self.generator._apply_force_directed_layout(nodes, edges)
        
        # Verify that positions were added
        for node in result:
            self.assertIn("x", node)
            self.assertIn("y", node)
            self.assertGreaterEqual(node["x"], 0)
            self.assertGreaterEqual(node["y"], 0)

    def test_apply_hierarchical_layout(self):
        """Test applying hierarchical layout."""
        # Create test nodes and edges
        nodes = [
            {"id": 1, "name": "Node1"},
            {"id": 2, "name": "Node2"},
            {"id": 3, "name": "Node3"}
        ]
        
        edges = [
            {"source": 1, "target": 2},
            {"source": 2, "target": 3}
        ]
        
        # Call the method
        result = self.generator._apply_hierarchical_layout(nodes, edges)
        
        # Verify that positions were added
        for node in result:
            self.assertIn("x", node)
            self.assertIn("y", node)
            self.assertGreaterEqual(node["x"], 0)
            self.assertGreaterEqual(node["y"], 0)

    def test_apply_circular_layout(self):
        """Test applying circular layout."""
        # Create test nodes
        nodes = [
            {"id": 1, "name": "Node1"},
            {"id": 2, "name": "Node2"},
            {"id": 3, "name": "Node3"}
        ]
        
        # Call the method
        result = self.generator._apply_circular_layout(nodes)
        
        # Verify that positions were added
        for node in result:
            self.assertIn("x", node)
            self.assertIn("y", node)
            self.assertGreaterEqual(node["x"], 0)
            self.assertGreaterEqual(node["y"], 0)


if __name__ == "__main__":
    unittest.main()