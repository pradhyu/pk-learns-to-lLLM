"""
MCP server for Neo4j integration with the Drools Graph RAG system.

This module provides a Model Context Protocol (MCP) server for integrating
the Neo4j graph database with language models.
"""
import logging
import os
import json
from typing import Dict, List, Any, Optional, Union

import fastapi
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import numpy as np

from drools_graph_rag.config import config
from drools_graph_rag.graph.connection import Neo4jConnection
from drools_graph_rag.query_engine.query_engine import GraphQueryEngine
from drools_graph_rag.rag.interface import RAGInterface

# Configure logging
logging.basicConfig(level=getattr(logging, config.log_level))
logger = logging.getLogger(__name__)


class MCPRequest(BaseModel):
    """
    Model for MCP request.
    """
    
    query: str = Field(..., description="The query to process")
    query_type: str = Field("natural_language", description="The type of query (natural_language or cypher)")
    rule_name: Optional[str] = Field(None, description="Optional rule name for specific rule queries")
    context: Optional[Dict[str, Any]] = Field(None, description="Optional context for the query")


class MCPResponse(BaseModel):
    """
    Model for MCP response.
    """
    
    response: str = Field(..., description="The response to the query")
    data: Optional[Dict[str, Any]] = Field(None, description="Optional data returned by the query")
    error: Optional[str] = Field(None, description="Error message if an error occurred")


class Neo4jMCPServer:
    """
    MCP server for Neo4j integration with the Drools Graph RAG system.
    """
    
    def __init__(
        self,
        neo4j_uri: str = None,
        neo4j_user: str = None,
        neo4j_password: str = None,
        neo4j_database: str = None,
        embedding_model: str = None,
        host: str = "0.0.0.0",
        port: int = 8000
    ) -> None:
        """
        Initialize the MCP server.
        
        Args:
            neo4j_uri: URI for the Neo4j database. Defaults to config value.
            neo4j_user: Username for the Neo4j database. Defaults to config value.
            neo4j_password: Password for the Neo4j database. Defaults to config value.
            neo4j_database: Name of the Neo4j database. Defaults to config value.
            embedding_model: Name of the embedding model. Defaults to config value.
            host: Host to run the server on. Defaults to "0.0.0.0".
            port: Port to run the server on. Defaults to 8000.
        """
        # Use provided values or defaults from config
        self.neo4j_uri = neo4j_uri or config.neo4j.uri
        self.neo4j_user = neo4j_user or config.neo4j.username
        self.neo4j_password = neo4j_password or config.neo4j.password
        self.neo4j_database = neo4j_database or config.neo4j.database
        self.embedding_model = embedding_model or config.embedding.model_name
        
        self.host = host
        self.port = port
        
        # Initialize components
        self.neo4j_connection = None
        self.query_engine = None
        self.rag_interface = None
        self.vector_store = None
        
        # Initialize FastAPI app
        self.app = FastAPI(title="Neo4j MCP Server", description="MCP server for Neo4j integration")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Register routes
        self.register_routes()
    
    def initialize(self) -> None:
        """
        Initialize the server components.
        """
        try:
            # Initialize Neo4j connection
            logger.info(f"Connecting to Neo4j at {self.neo4j_uri}")
            self.neo4j_connection = Neo4jConnection(
                uri=self.neo4j_uri,
                username=self.neo4j_user,
                password=self.neo4j_password,
                database=self.neo4j_database
            )
            
            # Initialize query engine
            self.query_engine = GraphQueryEngine(self.neo4j_connection)
            
            # Initialize RAG interface
            self.rag_interface = RAGInterface(self.neo4j_connection)
            
            # Initialize vector store
            self._initialize_vector_store()
            
            logger.info("Neo4j MCP Server initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Neo4j MCP Server: {e}")
            raise
    
    def _initialize_vector_store(self) -> None:
        """
        Initialize the vector store with embeddings from the graph.
        """
        try:
            # Import LangChain components
            try:
                from langchain.vectorstores import FAISS
                from langchain.embeddings import HuggingFaceEmbeddings
                from langchain.schema import Document
            except ImportError:
                logger.warning("LangChain not available. Vector store will not be initialized.")
                return
            
            logger.info(f"Initializing vector store with embedding model: {self.embedding_model}")
            
            # Initialize embedding model
            embeddings = HuggingFaceEmbeddings(
                model_name=self.embedding_model,
                model_kwargs={"device": config.embedding.device},
                encode_kwargs={"batch_size": config.embedding.batch_size}
            )
            
            # Get graph data for embeddings
            rules = self.query_engine.get_all_rules()
            
            # Create documents for vector store
            documents = []
            for rule in rules:
                # Get rule details
                rule_details = self.query_engine.get_rule_details(rule["id"])
                
                # Create document content
                content = f"Rule: {rule['name']}\nPackage: {rule['package']}\n"
                if rule.get('salience') is not None:
                    content += f"Salience: {rule['salience']}\n"
                
                # Add conditions
                conditions = rule_details.get('conditions', [])
                if conditions:
                    content += "\nConditions:\n"
                    for condition in conditions:
                        if condition.get('variable'):
                            content += f"- Variable: {condition['variable']}, Type: {condition['type']}\n"
                            constraints = condition.get('constraints', [])
                            for constraint in constraints:
                                if constraint.get('field'):
                                    content += f"  - {constraint['field']} {constraint['operator']} {constraint['value']}\n"
                
                # Add actions
                actions = rule_details.get('actions', [])
                if actions:
                    content += "\nActions:\n"
                    for action in actions:
                        if action.get('type') == 'method_call':
                            content += f"- Call method: {action['method']} on {action['target']}\n"
                            if action.get('arguments'):
                                content += f"  Arguments: {action['arguments']}\n"
                        elif action.get('type') == 'assignment':
                            content += f"- Assign to: {action['target']}\n"
                        else:
                            content += f"- {action['type']}: {action.get('target', '')}\n"
                
                # Create document
                document = Document(
                    page_content=content,
                    metadata={
                        "rule_id": rule["id"],
                        "rule_name": rule["name"],
                        "package": rule["package"],
                        "salience": rule.get("salience")
                    }
                )
                documents.append(document)
            
            # Create vector store
            if documents:
                logger.info(f"Creating vector store with {len(documents)} documents")
                self.vector_store = FAISS.from_documents(documents, embeddings)
                logger.info("Vector store initialized successfully")
            else:
                logger.warning("No documents found for vector store")
        except Exception as e:
            logger.error(f"Error initializing vector store: {e}")
            logger.warning("Vector store will not be available")
    
    def register_routes(self) -> None:
        """
        Register routes for the FastAPI app.
        """
        @self.app.get("/")
        async def root():
            return {"message": "Neo4j MCP Server is running"}
        
        @self.app.get("/health")
        async def health():
            if not self.neo4j_connection:
                return {"status": "not_initialized"}
            
            try:
                # Check Neo4j connection
                self.neo4j_connection.execute_read_query("RETURN 1")
                return {"status": "healthy"}
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return {"status": "unhealthy", "error": str(e)}
        
        @self.app.post("/api/mcp", response_model=MCPResponse)
        async def handle_mcp_request(request: MCPRequest):
            if not self.neo4j_connection:
                try:
                    self.initialize()
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to initialize server: {str(e)}")
            
            try:
                return await self._handle_request(request)
            except Exception as e:
                logger.error(f"Error handling request: {e}")
                return MCPResponse(
                    response=f"Error processing request: {str(e)}",
                    error=str(e)
                )
    
    async def _handle_request(self, request: MCPRequest) -> MCPResponse:
        """
        Handle an MCP request.
        
        Args:
            request: The MCP request.
            
        Returns:
            An MCP response.
        """
        query_type = request.query_type.lower()
        
        if query_type == "natural_language":
            return await self._handle_nl_query(request)
        elif query_type == "cypher":
            return await self._handle_cypher_query(request)
        elif query_type == "explain_rule":
            return await self._handle_explain_rule(request)
        elif query_type == "explain_conflicts":
            return await self._handle_explain_conflicts(request)
        elif query_type == "explain_execution_order":
            return await self._handle_explain_execution_order(request)
        else:
            return MCPResponse(
                response=f"Unsupported query type: {query_type}",
                error=f"Unsupported query type: {query_type}"
            )
    
    async def _handle_nl_query(self, request: MCPRequest) -> MCPResponse:
        """
        Handle a natural language query.
        
        Args:
            request: The MCP request.
            
        Returns:
            An MCP response.
        """
        query = request.query
        
        # Process the query using the RAG interface
        response = self.rag_interface.process_query(query)
        
        return MCPResponse(response=response)
    
    async def _handle_cypher_query(self, request: MCPRequest) -> MCPResponse:
        """
        Handle a Cypher query.
        
        Args:
            request: The MCP request.
            
        Returns:
            An MCP response.
        """
        query = request.query
        
        try:
            # Execute the Cypher query
            results = self.neo4j_connection.execute_read_query(query)
            
            # Format the results
            formatted_results = json.dumps(results, indent=2)
            
            return MCPResponse(
                response=f"Query executed successfully. {len(results)} results returned.",
                data={"results": results}
            )
        except Exception as e:
            logger.error(f"Error executing Cypher query: {e}")
            return MCPResponse(
                response=f"Error executing Cypher query: {str(e)}",
                error=str(e)
            )
    
    async def _handle_explain_rule(self, request: MCPRequest) -> MCPResponse:
        """
        Handle a request to explain a rule.
        
        Args:
            request: The MCP request.
            
        Returns:
            An MCP response.
        """
        rule_name = request.rule_name or request.query
        
        if not rule_name:
            return MCPResponse(
                response="No rule name provided",
                error="No rule name provided"
            )
        
        # Explain the rule
        explanation = self.rag_interface.explain_rule_context(rule_name)
        
        return MCPResponse(response=explanation)
    
    async def _handle_explain_conflicts(self, request: MCPRequest) -> MCPResponse:
        """
        Handle a request to explain rule conflicts.
        
        Args:
            request: The MCP request.
            
        Returns:
            An MCP response.
        """
        rule_name = request.rule_name or request.query
        
        # Explain conflicts
        explanation = self.rag_interface.explain_rule_conflicts(rule_name if rule_name else None)
        
        return MCPResponse(response=explanation)
    
    async def _handle_explain_execution_order(self, request: MCPRequest) -> MCPResponse:
        """
        Handle a request to explain rule execution order.
        
        Args:
            request: The MCP request.
            
        Returns:
            An MCP response.
        """
        rule_name = request.rule_name or request.query
        
        # Explain execution order
        explanation = self.rag_interface.explain_execution_order(rule_name if rule_name else None)
        
        return MCPResponse(response=explanation)
    
    def start(self) -> None:
        """
        Start the MCP server.
        """
        # Initialize the server
        try:
            self.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize server: {e}")
            logger.info("Server will initialize on first request")
        
        # Start the server
        logger.info(f"Starting Neo4j MCP Server on {self.host}:{self.port}")
        uvicorn.run(self.app, host=self.host, port=self.port)


def main():
    """
    Main entry point for the MCP server.
    """
    # Get configuration from environment variables
    neo4j_uri = os.environ.get("NEO4J_URI", config.neo4j.uri)
    neo4j_user = os.environ.get("NEO4J_USER", config.neo4j.username)
    neo4j_password = os.environ.get("NEO4J_PASSWORD", config.neo4j.password)
    neo4j_database = os.environ.get("NEO4J_DATABASE", config.neo4j.database)
    embedding_model = os.environ.get("EMBEDDING_MODEL", config.embedding.model_name)
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    
    # Create and start the server
    server = Neo4jMCPServer(
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        neo4j_database=neo4j_database,
        embedding_model=embedding_model,
        host=host,
        port=port
    )
    server.start()


if __name__ == "__main__":
    main()