"""
Tests for the interactive visualization interface.
"""
import unittest
from unittest.mock import MagicMock, patch

from drools_graph_rag.visualization.interactive import InteractiveVisualization
from drools_graph_rag.visualization.generator import GraphVisualizationGenerator
from drools_graph_rag.query_engine.query_engine import GraphQueryEngine
from drools_graph_rag.graph.connection import Neo4jConnection


class TestInteractiveVisualization(unittest.TestCase):
    """Test cases for the InteractiveVisualization class."""

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
        
        # Create the interactive visualization
        self.interactive = InteractiveVisualization(self.mock_generator)

    def test_get_node_details(self):
        """Test getting node details."""
        # Mock the execute_read_query method to return test data
        self.mock_connection.execute_read_query.side_effect = [
            # Node details
            [{"n": {"name": "Rule1", "salience": 100}, "labels": ["Rule"]}],
            # Rule file
            [{"file_path": "test.drl", "package": "com.example"}],
            # Conditions count
            [{"conditions_count": 2}],
            # Actions count
            [{"actions_count": 1}],
            # Parent rule
            [{"parent_name": "ParentRule", "parent_package": "com.example"}]
        ]
        
        # Call the method
        result = self.interactive.get_node_details(1)
        
        # Verify the result
        self.assertIn("id", result)
        self.assertIn("labels", result)
        self.assertIn("properties", result)
        self.assertIn("file_path", result)
        self.assertIn("package", result)
        self.assertIn("conditions_count", result)
        self.assertIn("actions_count", result)
        self.assertIn("parent", result)
        
        # Verify the values
        self.assertEqual(result["id"], 1)
        self.assertEqual(result["labels"], ["Rule"])
        self.assertEqual(result["properties"]["name"], "Rule1")
        self.assertEqual(result["properties"]["salience"], 100)
        self.assertEqual(result["file_path"], "test.drl")
        self.assertEqual(result["package"], "com.example")
        self.assertEqual(result["conditions_count"], 2)
        self.assertEqual(result["actions_count"], 1)
        self.assertEqual(result["parent"]["name"], "ParentRule")
        self.assertEqual(result["parent"]["package"], "com.example")

    def test_navigate_to_related_nodes(self):
        """Test navigating to related nodes."""
        # Mock the execute_read_query method to return test data
        self.mock_connection.execute_read_query.return_value = [
            {
                "n": {"name": "Rule1", "salience": 100},
                "n_labels": ["Rule"],
                "related": {"name": "Condition1", "variable": "$customer"},
                "related_labels": ["Condition"],
                "r": {},
                "rel_type": "HAS_CONDITION"
            }
        ]
        
        # Mock the get_node_id method
        self.mock_connection.get_node_id.return_value = 2
        
        # Mock the _apply_force_directed_layout method
        self.mock_generator._apply_force_directed_layout.return_value = [
            {"id": 1, "label": "Rule", "properties": {"name": "Rule1", "salience": 100}, "focus": True, "x": 100, "y": 200},
            {"id": 2, "label": "Condition", "properties": {"name": "Condition1", "variable": "$customer"}, "x": 300, "y": 400}
        ]
        
        # Call the method
        result = self.interactive.navigate_to_related_nodes(1)
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertEqual(len(result["nodes"]), 2)
        self.assertEqual(len(result["edges"]), 1)
        
        # Verify the nodes
        self.assertEqual(result["nodes"][0]["id"], 1)
        self.assertEqual(result["nodes"][0]["label"], "Rule")
        self.assertTrue(result["nodes"][0]["focus"])
        self.assertEqual(result["nodes"][1]["id"], 2)
        self.assertEqual(result["nodes"][1]["label"], "Condition")
        
        # Verify the edge
        self.assertEqual(result["edges"][0]["source"], 1)
        self.assertEqual(result["edges"][0]["target"], 2)
        self.assertEqual(result["edges"][0]["label"], "HAS_CONDITION")

    def test_zoom_to_node(self):
        """Test zooming to a node."""
        # Create test graph data
        graph_data = {
            "nodes": [
                {"id": 1, "name": "Rule1", "x": 100, "y": 200},
                {"id": 2, "name": "Rule2", "x": 300, "y": 400, "focus": True}
            ],
            "edges": [
                {"source": 1, "target": 2, "type": "extends", "label": "EXTENDS"}
            ]
        }
        
        # Call the method
        result = self.interactive.zoom_to_node(graph_data, 1)
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertIn("view", result)
        
        # Verify that the focus has changed
        self.assertTrue(result["nodes"][0]["focus"])
        self.assertNotIn("focus", result["nodes"][1])
        
        # Verify the view
        self.assertEqual(result["view"]["center"]["x"], 100)
        self.assertEqual(result["view"]["center"]["y"], 200)
        self.assertEqual(result["view"]["zoom"], 1.5)

    def test_pan_graph(self):
        """Test panning the graph."""
        # Create test graph data
        graph_data = {
            "nodes": [
                {"id": 1, "name": "Rule1", "x": 100, "y": 200},
                {"id": 2, "name": "Rule2", "x": 300, "y": 400}
            ],
            "edges": [
                {"source": 1, "target": 2, "type": "extends", "label": "EXTENDS"}
            ],
            "view": {
                "center": {"x": 200, "y": 300},
                "zoom": 1.0
            }
        }
        
        # Call the method
        result = self.interactive.pan_graph(graph_data, "right", 50)
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertIn("view", result)
        
        # Verify that the positions have changed
        self.assertEqual(result["nodes"][0]["x"], 150)
        self.assertEqual(result["nodes"][0]["y"], 200)
        self.assertEqual(result["nodes"][1]["x"], 350)
        self.assertEqual(result["nodes"][1]["y"], 400)
        
        # Verify the view
        self.assertEqual(result["view"]["center"]["x"], 250)
        self.assertEqual(result["view"]["center"]["y"], 300)

    def test_zoom_graph(self):
        """Test zooming the graph."""
        # Create test graph data
        graph_data = {
            "nodes": [
                {"id": 1, "name": "Rule1", "x": 100, "y": 200},
                {"id": 2, "name": "Rule2", "x": 300, "y": 400}
            ],
            "edges": [
                {"source": 1, "target": 2, "type": "extends", "label": "EXTENDS"}
            ],
            "view": {
                "center": {"x": 200, "y": 300},
                "zoom": 1.0
            }
        }
        
        # Call the method
        result = self.interactive.zoom_graph(graph_data, 2.0)
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertIn("view", result)
        
        # Verify the zoom level
        self.assertEqual(result["view"]["zoom"], 2.0)

    def test_reset_view(self):
        """Test resetting the view."""
        # Create test graph data
        graph_data = {
            "nodes": [
                {"id": 1, "name": "Rule1", "x": 100, "y": 200},
                {"id": 2, "name": "Rule2", "x": 300, "y": 400}
            ],
            "edges": [
                {"source": 1, "target": 2, "type": "extends", "label": "EXTENDS"}
            ],
            "view": {
                "center": {"x": 500, "y": 600},
                "zoom": 2.0
            }
        }
        
        # Call the method
        result = self.interactive.reset_view(graph_data)
        
        # Verify the result
        self.assertIn("nodes", result)
        self.assertIn("edges", result)
        self.assertIn("view", result)
        
        # Verify the view
        self.assertEqual(result["view"]["center"]["x"], 200)  # (100 + 300) / 2
        self.assertEqual(result["view"]["center"]["y"], 300)  # (200 + 400) / 2
        self.assertEqual(result["view"]["zoom"], 1.0)


if __name__ == "__main__":
    unittest.main()