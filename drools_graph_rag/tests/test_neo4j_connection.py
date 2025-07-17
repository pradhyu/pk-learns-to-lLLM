"""
Tests for the Neo4j connection manager.
"""
import unittest
from unittest.mock import patch, MagicMock, call
import pytest

from drools_graph_rag.graph.connection import (
    Neo4jConnection,
    Neo4jConnectionPool,
    Neo4jConnectionError,
    Neo4jQueryError,
    Neo4jRetryableError
)
from neo4j.exceptions import ServiceUnavailable, TransientError


class TestNeo4jConnection(unittest.TestCase):
    """Test cases for the Neo4jConnection class."""

    @patch('drools_graph_rag.graph.connection.GraphDatabase')
    def test_connection_initialization(self, mock_graph_db):
        """Test that the connection is initialized correctly."""
        # Setup mock
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # Create connection
        connection = Neo4jConnection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )

        # Verify
        mock_graph_db.driver.assert_called_once()
        mock_driver.session.assert_called_once()
        mock_session.run.assert_called_once_with("RETURN 1")
        self.assertEqual(connection.uri, "bolt://localhost:7687")
        self.assertEqual(connection.username, "neo4j")
        self.assertEqual(connection.password, "password")
        self.assertEqual(connection.database, "neo4j")

    @patch('drools_graph_rag.graph.connection.GraphDatabase')
    def test_connection_failure(self, mock_graph_db):
        """Test that connection failures are handled correctly."""
        # Setup mock to raise an exception
        mock_graph_db.driver.side_effect = Exception("Connection failed")

        # Verify that the exception is propagated
        with self.assertRaises(Neo4jConnectionError):
            Neo4jConnection(
                uri="bolt://localhost:7687",
                username="neo4j",
                password="password"
            )

    @patch('drools_graph_rag.graph.connection.GraphDatabase')
    def test_close_connection(self, mock_graph_db):
        """Test that the connection is closed correctly."""
        # Setup mock
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver

        # Create and close connection
        connection = Neo4jConnection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        connection.close()

        # Verify
        mock_driver.close.assert_called_once()
        self.assertIsNone(connection.driver)

    @patch('drools_graph_rag.graph.connection.GraphDatabase')
    def test_get_session(self, mock_graph_db):
        """Test that a session is retrieved correctly."""
        # Setup mock
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_driver.session.return_value = mock_session

        # Create connection and get session
        connection = Neo4jConnection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        session = connection.get_session()

        # Verify
        self.assertEqual(session, mock_session)
        mock_driver.session.assert_called_with(database="neo4j")

    @patch('drools_graph_rag.graph.connection.GraphDatabase')
    def test_execute_query(self, mock_graph_db):
        """Test that a query is executed correctly."""
        # Setup mock
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_record = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = mock_result
        mock_result.__iter__.return_value = [mock_record]
        mock_record.data.return_value = {"key": "value"}

        # Create connection and execute query
        connection = Neo4jConnection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        result = connection.execute_query("MATCH (n) RETURN n", {"param": "value"})

        # Verify
        mock_session.run.assert_called_with("MATCH (n) RETURN n", {"param": "value"})
        self.assertEqual(result, [{"key": "value"}])

    @patch('drools_graph_rag.graph.connection.GraphDatabase')
    def test_execute_write_query(self, mock_graph_db):
        """Test that a write query is executed correctly."""
        # Setup mock
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.execute_write.return_value = [{"key": "value"}]

        # Create connection and execute write query
        connection = Neo4jConnection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        result = connection.execute_write_query(
            "CREATE (n:Node {name: $name}) RETURN n",
            {"name": "test"}
        )

        # Verify
        mock_session.execute_write.assert_called_once()
        self.assertEqual(result, [{"key": "value"}])

    @patch('drools_graph_rag.graph.connection.GraphDatabase')
    def test_execute_read_query(self, mock_graph_db):
        """Test that a read query is executed correctly."""
        # Setup mock
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.execute_read.return_value = [{"key": "value"}]

        # Create connection and execute read query
        connection = Neo4jConnection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        result = connection.execute_read_query(
            "MATCH (n:Node {name: $name}) RETURN n",
            {"name": "test"}
        )

        # Verify
        mock_session.execute_read.assert_called_once()
        self.assertEqual(result, [{"key": "value"}])

    @patch('drools_graph_rag.graph.connection.GraphDatabase')
    @patch('drools_graph_rag.graph.connection.time')
    def test_retry_logic(self, mock_time, mock_graph_db):
        """Test that retry logic works correctly for transient errors."""
        # Setup mocks
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session
        
        # Make the first call fail with a transient error, then succeed
        mock_session.run.side_effect = [
            ServiceUnavailable("Service unavailable"),
            MagicMock(return_value=[MagicMock(data=lambda: {"key": "value"})])
        ]
        
        # Mock time.time() to return increasing values
        mock_time.time.side_effect = [0, 1, 2]
        
        # Create connection and execute query with retry
        connection = Neo4jConnection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password",
            max_retry_time=10,
            retry_delay=1
        )
        result = connection.execute_query("MATCH (n) RETURN n")
        
        # Verify
        self.assertEqual(mock_session.run.call_count, 2)
        self.assertEqual(result, [{"key": "value"}])
        mock_time.sleep.assert_called_once_with(1)

    @patch('drools_graph_rag.graph.connection.GraphDatabase')
    @patch('drools_graph_rag.graph.connection.time')
    def test_retry_exhaustion(self, mock_time, mock_graph_db):
        """Test that retry logic gives up after max retry time."""
        # Setup mocks
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session
        
        # Make all calls fail with a transient error
        mock_session.run.side_effect = ServiceUnavailable("Service unavailable")
        
        # Mock time.time() to simulate passing the max retry time
        mock_time.time.side_effect = [0, 5, 10, 15, 20, 25, 30, 35]
        
        # Create connection and execute query with retry
        connection = Neo4jConnection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password",
            max_retry_time=30,
            retry_delay=1
        )
        
        # Verify that Neo4jQueryError is raised after retries are exhausted
        with self.assertRaises(Neo4jQueryError):
            connection.execute_query("MATCH (n) RETURN n")

    @patch('drools_graph_rag.graph.connection.GraphDatabase')
    def test_execute_batch(self, mock_graph_db):
        """Test that batch execution works correctly."""
        # Setup mock
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_tx = MagicMock()
        mock_result1 = MagicMock()
        mock_result2 = MagicMock()
        
        mock_graph_db.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.execute_write.side_effect = lambda func: func(mock_tx)
        
        mock_tx.run.side_effect = [
            MagicMock(return_value=[MagicMock(data=lambda: {"key1": "value1"})]),
            MagicMock(return_value=[MagicMock(data=lambda: {"key2": "value2"})])
        ]
        
        # Create connection and execute batch
        connection = Neo4jConnection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        
        queries = [
            {"query": "CREATE (n:Node {id: 1}) RETURN n", "parameters": {"id": 1}},
            {"query": "CREATE (n:Node {id: 2}) RETURN n", "parameters": {"id": 2}}
        ]
        
        results = connection.execute_batch(queries)
        
        # Verify
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], [{"key1": "value1"}])
        self.assertEqual(results[1], [{"key2": "value2"}])
        mock_tx.run.assert_has_calls([
            call("CREATE (n:Node {id: 1}) RETURN n", {"id": 1}),
            call("CREATE (n:Node {id: 2}) RETURN n", {"id": 2})
        ])

    @patch('drools_graph_rag.graph.connection.GraphDatabase')
    def test_check_connection_health(self, mock_graph_db):
        """Test that connection health check works correctly."""
        # Setup mock
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = mock_result
        mock_result.single.return_value = {"n": 1}
        
        # Create connection and check health
        connection = Neo4jConnection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        
        health = connection.check_connection_health()
        
        # Verify
        self.assertTrue(health)
        mock_session.run.assert_called_with("RETURN 1 as n")

    @patch('drools_graph_rag.graph.connection.GraphDatabase')
    def test_get_server_info(self, mock_graph_db):
        """Test that server info is retrieved correctly."""
        # Setup mock
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_record = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = mock_result
        mock_result.single.return_value = {
            "name": "Neo4j",
            "versions": ["5.11.0"],
            "edition": "community"
        }
        
        # Create connection and get server info
        connection = Neo4jConnection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        
        info = connection.get_server_info()
        
        # Verify
        self.assertEqual(info, {
            "name": "Neo4j",
            "version": "5.11.0",
            "edition": "community"
        })
        mock_session.run.assert_called_with("CALL dbms.components() YIELD name, versions, edition")


class TestNeo4jConnectionPool(unittest.TestCase):
    """Test cases for the Neo4jConnectionPool class."""

    @patch('drools_graph_rag.graph.connection.Neo4jConnection')
    def test_get_connection(self, mock_connection_class):
        """Test that connections are retrieved correctly from the pool."""
        # Setup mock
        mock_connection = MagicMock()
        mock_connection_class.return_value = mock_connection
        
        # Create pool and get connection
        pool = Neo4jConnectionPool()
        connection = pool.get_connection(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        
        # Verify
        self.assertEqual(connection, mock_connection)
        mock_connection_class.assert_called_once_with(
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        
        # Get the same connection again
        connection2 = pool.get_connection()
        
        # Verify that no new connection was created
        self.assertEqual(connection2, mock_connection)
        self.assertEqual(mock_connection_class.call_count, 1)

    @patch('drools_graph_rag.graph.connection.Neo4jConnection')
    def test_close_connection(self, mock_connection_class):
        """Test that connections are closed correctly."""
        # Setup mock
        mock_connection = MagicMock()
        mock_connection_class.return_value = mock_connection
        
        # Create pool, get connection, and close it
        pool = Neo4jConnectionPool()
        pool.get_connection(
            connection_id="test",
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        pool.close_connection("test")
        
        # Verify
        mock_connection.close.assert_called_once()
        self.assertNotIn("test", pool._connections)

    @patch('drools_graph_rag.graph.connection.Neo4jConnection')
    def test_close_all_connections(self, mock_connection_class):
        """Test that all connections are closed correctly."""
        # Setup mocks
        mock_connection1 = MagicMock()
        mock_connection2 = MagicMock()
        mock_connection_class.side_effect = [mock_connection1, mock_connection2]
        
        # Create pool and get multiple connections
        pool = Neo4jConnectionPool()
        pool.get_connection(
            connection_id="test1",
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        pool.get_connection(
            connection_id="test2",
            uri="bolt://localhost:7688",
            username="neo4j",
            password="password"
        )
        
        # Close all connections
        pool.close_all_connections()
        
        # Verify
        mock_connection1.close.assert_called_once()
        mock_connection2.close.assert_called_once()
        self.assertEqual(len(pool._connections), 0)

    @patch('drools_graph_rag.graph.connection.Neo4jConnection')
    def test_get_connection_ids(self, mock_connection_class):
        """Test that connection IDs are retrieved correctly."""
        # Setup mock
        mock_connection_class.return_value = MagicMock()
        
        # Create pool and get multiple connections
        pool = Neo4jConnectionPool()
        pool.get_connection(
            connection_id="test1",
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        pool.get_connection(
            connection_id="test2",
            uri="bolt://localhost:7688",
            username="neo4j",
            password="password"
        )
        
        # Get connection IDs
        ids = pool.get_connection_ids()
        
        # Verify
        self.assertEqual(set(ids), {"test1", "test2"})

    @patch('drools_graph_rag.graph.connection.Neo4jConnection')
    def test_check_all_connections(self, mock_connection_class):
        """Test that connection health checks work correctly."""
        # Setup mocks
        mock_connection1 = MagicMock()
        mock_connection2 = MagicMock()
        mock_connection1.check_connection_health.return_value = True
        mock_connection2.check_connection_health.return_value = False
        mock_connection_class.side_effect = [mock_connection1, mock_connection2]
        
        # Create pool and get multiple connections
        pool = Neo4jConnectionPool()
        pool.get_connection(
            connection_id="test1",
            uri="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
        pool.get_connection(
            connection_id="test2",
            uri="bolt://localhost:7688",
            username="neo4j",
            password="password"
        )
        
        # Check all connections
        health = pool.check_all_connections()
        
        # Verify
        self.assertEqual(health, {"test1": True, "test2": False})
        mock_connection1.check_connection_health.assert_called_once()
        mock_connection2.check_connection_health.assert_called_once()


if __name__ == '__main__':
    unittest.main()