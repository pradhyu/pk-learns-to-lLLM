"""
Tests for the graph filtering and search capabilities.
"""
import unittest
from unittest.mock import MagicMock, patch

from drools_graph_rag.visualization.filter import GraphFilterAndSearch
from drools_graph_rag.visualization.generator import GraphVisualizationGenerator
from drools_graph_rag.query_engine.query_engine import GraphQueryEngine
from drools_graph_rag.graph.connection import Neo4jConnection


class TestGraphFilterAndSearch(unittest.TestCase):
    """Test cases for the GraphFilterAndSearch class."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock the Neo4jConnection and GraphQueryEngine
        self.mock_connection = MagicMock(spec=Neo4jConnection)
        self.mock_query_engine = MagicMock(spec=GraphQueryEngine)
        self.mock_query_engine.connection = self.mock_connection
        
        # Create the visualization generator
        self.mock_generator = MagicMock(spec=GraphVisualizationGenerator)
        self.mock_generator.query_engine = self.mock_query_engine
        self.mock_generator.connection = self.mock_connection
        
        # Create the filter and search interface
        self.filter_search = GraphFilterAndSearch(self.mock_generator)
        
        # Create test graph data
        self.test_graph = {
            "nodes": [
                {"id": 1, "name": "Rule1", "type": "rule", "salience": 100, "package": "com.example"},
                {"id": 2, "name": "Rule2", "type": "rule", "salience": 90, "package": "com.example"},
                {"id": 3, "name": "Condition1", "type": "condition", "variable": "$customer", "properties": {"type": "Customer"}},
                {"id": 4, "name": "Action1", "type": "action", "method": "addError"}
            ],
            "edges": [
                {"source": 1, "target": 2, "type": "extends", "label": "EXTENDS"},
                {"source": 1, "target": 3, "type": "has_condition", "label": "HAS_CONDITION"},
                {"source": 1, "target": 4, "type": "has_action", "label": "HAS_ACTION"}
            ]
        }

    def test_filter_graph_by_properties(self):
        """Test filtering graph by properties."""
        # Filter by node type
        filters = {"node_type": ["rule"]}
        result = self.filter_search.filter_graph_by_properties(self.test_graph, filters)
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertEqual(len(result["nodes"]), 2)  # Only rule nodes
        self.assertEqual(len(result["edges"]), 1)  # Only rule-to-rule edges
        
        # Filter by property range
        filters = {"properties": {"salience": {"min": 95}}}
        result = self.filter_search.filter_graph_by_properties(self.test_graph, filters)
        
        # Verify the result
        self.assertEqual(len(result["nodes"]), 1)  # Only Rule1 with salience 100
        
        # Filter by property pattern
        filters = {"properties": {"name": {"pattern": "Rule.*"}}}
        result = self.filter_search.filter_graph_by_properties(self.test_graph, filters)
        
        # Verify the result
        self.assertEqual(len(result["nodes"]), 2)  # Rule1 and Rule2
        
        # Filter by property values
        filters = {"properties": {"package": {"values": ["com.example"]}}}
        result = self.filter_search.filter_graph_by_properties(self.test_graph, filters)
        
        # Verify the result
        self.assertEqual(len(result["nodes"]), 2)  # Rule1 and Rule2

    def test_search_nodes(self):
        """Test searching for nodes."""
        # Mock the execute_read_query method to return test data
        self.mock_connection.execute_read_query.return_value = [
            {
                "n": {"name": "Rule1", "salience": 100, "package": "com.example"},
                "labels": ["Rule"],
                "id": 1
            }
        ]
        
        # Call the method
        result = self.filter_search.search_nodes("Rule1")
        
        # Verify the result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 1)
        self.assertEqual(result[0]["label"], "Rule")
        self.assertEqual(result[0]["properties"]["name"], "Rule1")

    def test_highlight_search_results(self):
        """Test highlighting search results."""
        # Create search results
        search_results = [
            {"id": 1, "label": "Rule", "properties": {"name": "Rule1"}}
        ]
        
        # Call the method
        result = self.filter_search.highlight_search_results(self.test_graph, search_results)
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        
        # Verify that the node is highlighted
        highlighted_node = next((node for node in result["nodes"] if node["id"] == 1), None)
        self.assertIsNotNone(highlighted_node)
        self.assertTrue(highlighted_node["highlighted"])
        
        # Verify that other nodes are not highlighted
        other_node = next((node for node in result["nodes"] if node["id"] == 2), None)
        self.assertIsNotNone(other_node)
        self.assertNotIn("highlighted", other_node)

    def test_filter_by_relationship_distance(self):
        """Test filtering by relationship distance."""
        # Mock the execute_read_query method to return test data
        self.mock_connection.execute_read_query.return_value = [
            {"related": {}, "related_id": 2},
            {"related": {}, "related_id": 3},
            {"related": {}, "related_id": 4}
        ]
        
        # Call the method
        result = self.filter_search.filter_by_relationship_distance(self.test_graph, 1, 2)
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertEqual(len(result["nodes"]), 4)  # All nodes are within distance 2
        self.assertEqual(len(result["edges"]), 3)  # All edges connect nodes within distance 2

    def test_filter_by_rule_type(self):
        """Test filtering by rule type."""
        # Add rule_type to test graph
        test_graph = self.test_graph.copy()
        test_graph["nodes"][0]["rule_type"] = "entry_point"
        test_graph["nodes"][1]["rule_type"] = "normal"
        
        # Call the method
        result = self.filter_search.filter_by_rule_type(test_graph, ["entry_point"])
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertEqual(len(result["nodes"]), 3)  # Rule1 + connected nodes (Condition1, Action1)
        self.assertEqual(len(result["edges"]), 2)  # Edges from Rule1 to Condition1 and Action1

    def test_filter_by_complexity(self):
        """Test filtering by complexity."""
        # Call the method
        result = self.filter_search.filter_by_complexity(self.test_graph, 2, None)
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertEqual(len(result["nodes"]), 4)  # Rule1 has 2 connections (complexity 2)
        self.assertEqual(len(result["edges"]), 3)  # All edges are included

    def test_search_by_text_content(self):
        """Test searching by text content."""
        # Mock the execute_read_query method to return test data
        self.mock_connection.execute_read_query.return_value = [
            {
                "n": {"name": "Rule1", "salience": 100, "package": "com.example"},
                "labels": ["Rule"],
                "id": 1
            }
        ]
        
        # Call the method
        result = self.filter_search.search_by_text_content("Rule1")
        
        # Verify the result
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 1)
        self.assertEqual(result[0]["label"], "Rule")
        self.assertEqual(result[0]["properties"]["name"], "Rule1")


if __name__ == "__main__":
    unittest.main()