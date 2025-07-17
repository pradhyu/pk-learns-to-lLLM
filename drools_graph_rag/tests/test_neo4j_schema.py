"""
Tests for the Neo4j schema manager.
"""
import unittest
from unittest.mock import patch, MagicMock, call

from drools_graph_rag.graph.connection import Neo4jConnection, Neo4jQueryError
from drools_graph_rag.graph.schema import Neo4jSchemaManager, Neo4jGraphBuilder


class TestNeo4jSchemaManager(unittest.TestCase):
    """Test cases for the Neo4jSchemaManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_connection = MagicMock(spec=Neo4jConnection)
        self.schema_manager = Neo4jSchemaManager(self.mock_connection)

    def test_create_schema(self):
        """Test that the schema is created correctly."""
        # Call the method
        self.schema_manager.create_schema()
        
        # Verify that constraints and indexes were created
        self.assertTrue(self.mock_connection.execute_write_query.called)
        
        # Count the number of constraint and index creation calls
        constraint_calls = 0
        index_calls = 0
        for call_args in self.mock_connection.execute_write_query.call_args_list:
            query = call_args[0][0]
            if "CREATE CONSTRAINT" in query:
                constraint_calls += 1
            elif "CREATE INDEX" in query:
                index_calls += 1
        
        # Verify that at least one constraint and one index were created
        self.assertGreater(constraint_calls, 0)
        self.assertGreater(index_calls, 0)

    def test_create_constraints(self):
        """Test that constraints are created correctly."""
        # Call the method
        self.schema_manager._create_constraints()
        
        # Verify that constraints were created
        self.assertTrue(self.mock_connection.execute_write_query.called)
        
        # Count the number of constraint creation calls
        constraint_calls = 0
        for call_args in self.mock_connection.execute_write_query.call_args_list:
            query = call_args[0][0]
            if "CREATE CONSTRAINT" in query:
                constraint_calls += 1
        
        # Verify that at least one constraint was created
        self.assertGreater(constraint_calls, 0)

    def test_create_indexes(self):
        """Test that indexes are created correctly."""
        # Call the method
        self.schema_manager._create_indexes()
        
        # Verify that indexes were created
        self.assertTrue(self.mock_connection.execute_write_query.called)
        
        # Count the number of index creation calls
        index_calls = 0
        for call_args in self.mock_connection.execute_write_query.call_args_list:
            query = call_args[0][0]
            if "CREATE INDEX" in query:
                index_calls += 1
        
        # Verify that at least one index was created
        self.assertGreater(index_calls, 0)

    def test_clear_schema(self):
        """Test that the schema is cleared correctly."""
        # Setup mock responses
        self.mock_connection.execute_read_query.side_effect = [
            [{"name": "constraint1"}, {"name": "constraint2"}],  # Constraints
            [{"name": "index1", "type": "INDEX"}, {"name": "index2", "type": "INDEX"}]  # Indexes
        ]
        
        # Call the method
        self.schema_manager.clear_schema()
        
        # Verify that constraints and indexes were dropped
        self.assertEqual(self.mock_connection.execute_read_query.call_count, 2)
        self.assertEqual(self.mock_connection.execute_write_query.call_count, 4)  # 2 constraints + 2 indexes
        
        # Verify the drop queries
        expected_calls = [
            call("DROP CONSTRAINT constraint1 IF EXISTS"),
            call("DROP CONSTRAINT constraint2 IF EXISTS"),
            call("DROP INDEX index1 IF EXISTS"),
            call("DROP INDEX index2 IF EXISTS")
        ]
        
        for expected_call in expected_calls:
            self.assertIn(expected_call, self.mock_connection.execute_write_query.call_args_list)

    def test_drop_constraints(self):
        """Test that constraints are dropped correctly."""
        # Setup mock response
        self.mock_connection.execute_read_query.return_value = [
            {"name": "constraint1"}, {"name": "constraint2"}
        ]
        
        # Call the method
        self.schema_manager._drop_constraints()
        
        # Verify that constraints were dropped
        self.mock_connection.execute_read_query.assert_called_once_with("SHOW CONSTRAINTS")
        self.assertEqual(self.mock_connection.execute_write_query.call_count, 2)
        
        # Verify the drop queries
        expected_calls = [
            call("DROP CONSTRAINT constraint1 IF EXISTS"),
            call("DROP CONSTRAINT constraint2 IF EXISTS")
        ]
        
        for expected_call in expected_calls:
            self.assertIn(expected_call, self.mock_connection.execute_write_query.call_args_list)

    def test_drop_indexes(self):
        """Test that indexes are dropped correctly."""
        # Setup mock response
        self.mock_connection.execute_read_query.return_value = [
            {"name": "index1", "type": "INDEX"}, 
            {"name": "index2", "type": "INDEX"},
            {"name": "constraint_index", "type": "CONSTRAINT"}  # Should be skipped
        ]
        
        # Call the method
        self.schema_manager._drop_indexes()
        
        # Verify that indexes were dropped
        self.mock_connection.execute_read_query.assert_called_once_with("SHOW INDEXES")
        self.assertEqual(self.mock_connection.execute_write_query.call_count, 2)
        
        # Verify the drop queries
        expected_calls = [
            call("DROP INDEX index1 IF EXISTS"),
            call("DROP INDEX index2 IF EXISTS")
        ]
        
        for expected_call in expected_calls:
            self.assertIn(expected_call, self.mock_connection.execute_write_query.call_args_list)
        
        # Verify that constraint index was not dropped
        unexpected_call = call("DROP INDEX constraint_index IF EXISTS")
        self.assertNotIn(unexpected_call, self.mock_connection.execute_write_query.call_args_list)

    def test_check_schema_exists_true(self):
        """Test that schema existence check returns True when schema exists."""
        # Setup mock response
        self.mock_connection.execute_read_query.return_value = [{"name": "rule_file_path_unique"}]
        
        # Call the method
        result = self.schema_manager.check_schema_exists()
        
        # Verify
        self.assertTrue(result)
        self.mock_connection.execute_read_query.assert_called_once()

    def test_check_schema_exists_false(self):
        """Test that schema existence check returns False when schema does not exist."""
        # Setup mock response
        self.mock_connection.execute_read_query.return_value = []
        
        # Call the method
        result = self.schema_manager.check_schema_exists()
        
        # Verify
        self.assertFalse(result)
        self.mock_connection.execute_read_query.assert_called_once()

    def test_get_schema_info(self):
        """Test that schema info is retrieved correctly."""
        # Setup mock responses
        self.mock_connection.execute_read_query.side_effect = [
            [{"name": "constraint1"}, {"name": "constraint2"}],  # Constraints
            [{"name": "index1"}, {"name": "index2"}]  # Indexes
        ]
        
        # Call the method
        result = self.schema_manager.get_schema_info()
        
        # Verify
        self.assertEqual(self.mock_connection.execute_read_query.call_count, 2)
        self.assertEqual(result["constraints"], [{"name": "constraint1"}, {"name": "constraint2"}])
        self.assertEqual(result["indexes"], [{"name": "index1"}, {"name": "index2"}])


class TestNeo4jGraphBuilder(unittest.TestCase):
    """Test cases for the Neo4jGraphBuilder class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_connection = MagicMock(spec=Neo4jConnection)
        self.mock_schema_manager = MagicMock(spec=Neo4jSchemaManager)
        
        # Patch the Neo4jSchemaManager constructor
        with patch('drools_graph_rag.graph.schema.Neo4jSchemaManager', return_value=self.mock_schema_manager):
            self.graph_builder = Neo4jGraphBuilder(self.mock_connection)

    def test_initialize_graph_schema_exists(self):
        """Test that graph initialization checks for schema existence."""
        # Setup mock response
        self.mock_schema_manager.check_schema_exists.return_value = True
        
        # Call the method
        self.graph_builder.initialize_graph()
        
        # Verify
        self.mock_schema_manager.check_schema_exists.assert_called_once()
        self.mock_schema_manager.create_schema.assert_not_called()

    def test_initialize_graph_schema_not_exists(self):
        """Test that graph initialization creates schema when it doesn't exist."""
        # Setup mock response
        self.mock_schema_manager.check_schema_exists.return_value = False
        
        # Call the method
        self.graph_builder.initialize_graph()
        
        # Verify
        self.mock_schema_manager.check_schema_exists.assert_called_once()
        self.mock_schema_manager.create_schema.assert_called_once()

    def test_clear_graph(self):
        """Test that the graph is cleared correctly."""
        # Call the method
        self.graph_builder.clear_graph()
        
        # Verify
        self.assertEqual(self.mock_connection.execute_write_query.call_count, 2)
        
        # Verify the queries
        expected_calls = [
            call("MATCH ()-[r]-() DELETE r"),
            call("MATCH (n) DELETE n")
        ]
        
        self.mock_connection.execute_write_query.assert_has_calls(expected_calls, any_order=False)

    def test_reset_graph(self):
        """Test that the graph is reset correctly."""
        # Call the method
        self.graph_builder.reset_graph()
        
        # Verify
        self.assertEqual(self.mock_connection.execute_write_query.call_count, 2)  # From clear_graph
        self.mock_schema_manager.clear_schema.assert_called_once()
        self.mock_schema_manager.create_schema.assert_called_once()

    def test_get_graph_statistics(self):
        """Test that graph statistics are retrieved correctly."""
        # Setup mock responses
        self.mock_connection.execute_read_query.side_effect = [
            [{"labels": {"Rule": 10, "Condition": 20}}],  # Node counts
            [{"relTypes": {"HAS_CONDITION": 15, "EXTENDS": 5}}]  # Relationship counts
        ]
        
        # Call the method
        result = self.graph_builder.get_graph_statistics()
        
        # Verify
        self.assertEqual(self.mock_connection.execute_read_query.call_count, 2)
        self.assertEqual(result["nodes"], {"Rule": 10, "Condition": 20})
        self.assertEqual(result["relationships"], {"HAS_CONDITION": 15, "EXTENDS": 5})
        self.assertEqual(result["total_nodes"], 30)
        self.assertEqual(result["total_relationships"], 20)


if __name__ == '__main__':
    unittest.main()