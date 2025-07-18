"""
Tests for the Neo4j MCP server.
"""
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from drools_graph_rag.mcp.neo4j_mcp_server import Neo4jMCPServer, MCPRequest, MCPResponse


class TestNeo4jMCPServer(unittest.TestCase):
    """
    Test the Neo4jMCPServer class.
    """
    
    def setUp(self):
        """
        Set up the test environment.
        """
        # Create mocks
        self.mock_neo4j_connection = MagicMock()
        self.mock_query_engine = MagicMock()
        self.mock_rag_interface = MagicMock()
        
        # Create the server
        self.server = Neo4jMCPServer(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="password",
            neo4j_database="neo4j",
            embedding_model="test-model",
            host="localhost",
            port=8000
        )
        
        # Set up mocks
        self.server.neo4j_connection = self.mock_neo4j_connection
        self.server.query_engine = self.mock_query_engine
        self.server.rag_interface = self.mock_rag_interface
        
        # Create a test client
        self.client = TestClient(self.server.app)
    
    def test_root_endpoint(self):
        """
        Test the root endpoint.
        """
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Neo4j MCP Server is running"})
    
    def test_health_endpoint_healthy(self):
        """
        Test the health endpoint when healthy.
        """
        # Set up mock
        self.mock_neo4j_connection.execute_read_query.return_value = [{"1": 1}]
        
        # Make request
        response = self.client.get("/health")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})
        
        # Verify mock calls
        self.mock_neo4j_connection.execute_read_query.assert_called_once_with("RETURN 1")
    
    def test_health_endpoint_unhealthy(self):
        """
        Test the health endpoint when unhealthy.
        """
        # Set up mock
        self.mock_neo4j_connection.execute_read_query.side_effect = Exception("Connection error")
        
        # Make request
        response = self.client.get("/health")
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "unhealthy")
        self.assertIn("Connection error", response.json()["error"])
    
    @patch("drools_graph_rag.mcp.neo4j_mcp_server.Neo4jMCPServer._handle_nl_query")
    async def test_handle_request_nl_query(self, mock_handle_nl_query):
        """
        Test handling a natural language query request.
        """
        # Set up mock
        mock_response = MCPResponse(response="Test response")
        mock_handle_nl_query.return_value = mock_response
        
        # Create request
        request = MCPRequest(query="Test query", query_type="natural_language")
        
        # Handle request
        response = await self.server._handle_request(request)
        
        # Check response
        self.assertEqual(response, mock_response)
        
        # Verify mock calls
        mock_handle_nl_query.assert_called_once_with(request)
    
    @patch("drools_graph_rag.mcp.neo4j_mcp_server.Neo4jMCPServer._handle_cypher_query")
    async def test_handle_request_cypher_query(self, mock_handle_cypher_query):
        """
        Test handling a Cypher query request.
        """
        # Set up mock
        mock_response = MCPResponse(response="Test response")
        mock_handle_cypher_query.return_value = mock_response
        
        # Create request
        request = MCPRequest(query="MATCH (n) RETURN n", query_type="cypher")
        
        # Handle request
        response = await self.server._handle_request(request)
        
        # Check response
        self.assertEqual(response, mock_response)
        
        # Verify mock calls
        mock_handle_cypher_query.assert_called_once_with(request)
    
    @patch("drools_graph_rag.mcp.neo4j_mcp_server.Neo4jMCPServer._handle_explain_rule")
    async def test_handle_request_explain_rule(self, mock_handle_explain_rule):
        """
        Test handling an explain rule request.
        """
        # Set up mock
        mock_response = MCPResponse(response="Test response")
        mock_handle_explain_rule.return_value = mock_response
        
        # Create request
        request = MCPRequest(query="Test Rule", query_type="explain_rule")
        
        # Handle request
        response = await self.server._handle_request(request)
        
        # Check response
        self.assertEqual(response, mock_response)
        
        # Verify mock calls
        mock_handle_explain_rule.assert_called_once_with(request)
    
    @patch("drools_graph_rag.mcp.neo4j_mcp_server.Neo4jMCPServer._handle_explain_conflicts")
    async def test_handle_request_explain_conflicts(self, mock_handle_explain_conflicts):
        """
        Test handling an explain conflicts request.
        """
        # Set up mock
        mock_response = MCPResponse(response="Test response")
        mock_handle_explain_conflicts.return_value = mock_response
        
        # Create request
        request = MCPRequest(query="Test Rule", query_type="explain_conflicts")
        
        # Handle request
        response = await self.server._handle_request(request)
        
        # Check response
        self.assertEqual(response, mock_response)
        
        # Verify mock calls
        mock_handle_explain_conflicts.assert_called_once_with(request)
    
    @patch("drools_graph_rag.mcp.neo4j_mcp_server.Neo4jMCPServer._handle_explain_execution_order")
    async def test_handle_request_explain_execution_order(self, mock_handle_explain_execution_order):
        """
        Test handling an explain execution order request.
        """
        # Set up mock
        mock_response = MCPResponse(response="Test response")
        mock_handle_explain_execution_order.return_value = mock_response
        
        # Create request
        request = MCPRequest(query="Test Rule", query_type="explain_execution_order")
        
        # Handle request
        response = await self.server._handle_request(request)
        
        # Check response
        self.assertEqual(response, mock_response)
        
        # Verify mock calls
        mock_handle_explain_execution_order.assert_called_once_with(request)
    
    async def test_handle_request_unsupported_type(self):
        """
        Test handling a request with an unsupported query type.
        """
        # Create request
        request = MCPRequest(query="Test query", query_type="unsupported")
        
        # Handle request
        response = await self.server._handle_request(request)
        
        # Check response
        self.assertIn("Unsupported query type", response.response)
        self.assertIn("Unsupported query type", response.error)
    
    async def test_handle_nl_query(self):
        """
        Test handling a natural language query.
        """
        # Set up mock
        self.mock_rag_interface.process_query.return_value = "Test response"
        
        # Create request
        request = MCPRequest(query="Test query", query_type="natural_language")
        
        # Handle request
        response = await self.server._handle_nl_query(request)
        
        # Check response
        self.assertEqual(response.response, "Test response")
        self.assertIsNone(response.error)
        
        # Verify mock calls
        self.mock_rag_interface.process_query.assert_called_once_with("Test query")
    
    async def test_handle_cypher_query(self):
        """
        Test handling a Cypher query.
        """
        # Set up mock
        self.mock_neo4j_connection.execute_read_query.return_value = [{"n": {"name": "Test"}}]
        
        # Create request
        request = MCPRequest(query="MATCH (n) RETURN n", query_type="cypher")
        
        # Handle request
        response = await self.server._handle_cypher_query(request)
        
        # Check response
        self.assertIn("Query executed successfully", response.response)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["results"], [{"n": {"name": "Test"}}])
        self.assertIsNone(response.error)
        
        # Verify mock calls
        self.mock_neo4j_connection.execute_read_query.assert_called_once_with("MATCH (n) RETURN n")
    
    async def test_handle_cypher_query_error(self):
        """
        Test handling a Cypher query with an error.
        """
        # Set up mock
        self.mock_neo4j_connection.execute_read_query.side_effect = Exception("Syntax error")
        
        # Create request
        request = MCPRequest(query="INVALID QUERY", query_type="cypher")
        
        # Handle request
        response = await self.server._handle_cypher_query(request)
        
        # Check response
        self.assertIn("Error executing Cypher query", response.response)
        self.assertIn("Syntax error", response.error)
    
    async def test_handle_explain_rule(self):
        """
        Test handling an explain rule request.
        """
        # Set up mock
        self.mock_rag_interface.explain_rule_context.return_value = "Rule explanation"
        
        # Create request with rule_name
        request = MCPRequest(query="", query_type="explain_rule", rule_name="Test Rule")
        
        # Handle request
        response = await self.server._handle_explain_rule(request)
        
        # Check response
        self.assertEqual(response.response, "Rule explanation")
        self.assertIsNone(response.error)
        
        # Verify mock calls
        self.mock_rag_interface.explain_rule_context.assert_called_once_with("Test Rule")
        
        # Reset mock
        self.mock_rag_interface.explain_rule_context.reset_mock()
        
        # Create request without rule_name
        request = MCPRequest(query="Test Rule", query_type="explain_rule")
        
        # Handle request
        response = await self.server._handle_explain_rule(request)
        
        # Check response
        self.assertEqual(response.response, "Rule explanation")
        self.assertIsNone(response.error)
        
        # Verify mock calls
        self.mock_rag_interface.explain_rule_context.assert_called_once_with("Test Rule")
    
    async def test_handle_explain_rule_no_name(self):
        """
        Test handling an explain rule request with no rule name.
        """
        # Create request with no rule name
        request = MCPRequest(query="", query_type="explain_rule")
        
        # Handle request
        response = await self.server._handle_explain_rule(request)
        
        # Check response
        self.assertIn("No rule name provided", response.response)
        self.assertIn("No rule name provided", response.error)
    
    async def test_handle_explain_conflicts(self):
        """
        Test handling an explain conflicts request.
        """
        # Set up mock
        self.mock_rag_interface.explain_rule_conflicts.return_value = "Conflicts explanation"
        
        # Create request with rule_name
        request = MCPRequest(query="", query_type="explain_conflicts", rule_name="Test Rule")
        
        # Handle request
        response = await self.server._handle_explain_conflicts(request)
        
        # Check response
        self.assertEqual(response.response, "Conflicts explanation")
        self.assertIsNone(response.error)
        
        # Verify mock calls
        self.mock_rag_interface.explain_rule_conflicts.assert_called_once_with("Test Rule")
        
        # Reset mock
        self.mock_rag_interface.explain_rule_conflicts.reset_mock()
        
        # Create request without rule_name
        request = MCPRequest(query="Test Rule", query_type="explain_conflicts")
        
        # Handle request
        response = await self.server._handle_explain_conflicts(request)
        
        # Check response
        self.assertEqual(response.response, "Conflicts explanation")
        self.assertIsNone(response.error)
        
        # Verify mock calls
        self.mock_rag_interface.explain_rule_conflicts.assert_called_once_with("Test Rule")
        
        # Reset mock
        self.mock_rag_interface.explain_rule_conflicts.reset_mock()
        
        # Create request with empty query
        request = MCPRequest(query="", query_type="explain_conflicts")
        
        # Handle request
        response = await self.server._handle_explain_conflicts(request)
        
        # Check response
        self.assertEqual(response.response, "Conflicts explanation")
        self.assertIsNone(response.error)
        
        # Verify mock calls
        self.mock_rag_interface.explain_rule_conflicts.assert_called_once_with(None)
    
    async def test_handle_explain_execution_order(self):
        """
        Test handling an explain execution order request.
        """
        # Set up mock
        self.mock_rag_interface.explain_execution_order.return_value = "Execution order explanation"
        
        # Create request with rule_name
        request = MCPRequest(query="", query_type="explain_execution_order", rule_name="Test Rule")
        
        # Handle request
        response = await self.server._handle_explain_execution_order(request)
        
        # Check response
        self.assertEqual(response.response, "Execution order explanation")
        self.assertIsNone(response.error)
        
        # Verify mock calls
        self.mock_rag_interface.explain_execution_order.assert_called_once_with("Test Rule")
        
        # Reset mock
        self.mock_rag_interface.explain_execution_order.reset_mock()
        
        # Create request without rule_name
        request = MCPRequest(query="Test Rule", query_type="explain_execution_order")
        
        # Handle request
        response = await self.server._handle_explain_execution_order(request)
        
        # Check response
        self.assertEqual(response.response, "Execution order explanation")
        self.assertIsNone(response.error)
        
        # Verify mock calls
        self.mock_rag_interface.explain_execution_order.assert_called_once_with("Test Rule")
        
        # Reset mock
        self.mock_rag_interface.explain_execution_order.reset_mock()
        
        # Create request with empty query
        request = MCPRequest(query="", query_type="explain_execution_order")
        
        # Handle request
        response = await self.server._handle_explain_execution_order(request)
        
        # Check response
        self.assertEqual(response.response, "Execution order explanation")
        self.assertIsNone(response.error)
        
        # Verify mock calls
        self.mock_rag_interface.explain_execution_order.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main()