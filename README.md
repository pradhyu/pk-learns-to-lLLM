# Drools Graph RAG

A graph-based Retrieval-Augmented Generation (RAG) system for analyzing and querying Drools rule files using Neo4j and natural language processing.

## Overview

Drools Graph RAG is a system that parses Drools rule files (.drl), builds a knowledge graph in Neo4j, and provides a natural language interface for querying and analyzing the rules. The system helps users understand complex rule relationships, detect conflicts, and analyze rule execution order.

## Features

- **Drools Parser**: Parse Drools rule files (.drl) into structured data models
- **Neo4j Graph Builder**: Convert parsed rules into a knowledge graph in Neo4j
- **Graph Query Engine**: Execute complex queries against the rule graph
- **RAG Interface**: Process natural language queries about rules
- **Visualization**: Generate interactive visualizations of rule relationships

## Prerequisites

- Python 3.9+
- Docker and Docker Compose (for Neo4j)
- Neo4j database (can be run via Docker)
- Poetry (optional, for dependency management)

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd drools-graph-rag
```

### 2. Set up a virtual environment (optional but recommended)

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies

Using pip:

```bash
pip install -r requirements.txt
```

Or using Poetry:

```bash
poetry install
```

### 4. Start Neo4j using Docker Compose

```bash
docker-compose up -d
```

This will start a Neo4j instance with the following default credentials:
- URL: bolt://localhost:7687
- Username: neo4j
- Password: password

## Configuration

Create a `.env` file in the project root with the following variables:

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j
```

## Usage

### 1. Parse Drools files and build the graph

```python
from drools_graph_rag.parser.parser import DroolsParser
from drools_graph_rag.graph.connection import Neo4jConnection
from drools_graph_rag.graph.builder import Neo4jGraphManager

# Parse Drools files
parser = DroolsParser()
rule_files = parser.parse_directory("path/to/drools/files")

# Connect to Neo4j
connection = Neo4jConnection(
    uri="bolt://localhost:7687",
    username="neo4j",
    password="password"
)

# Build the graph
graph_manager = Neo4jGraphManager(connection)
graph_manager.initialize_graph()
graph_manager.populate_graph(rule_files)
```

### 2. Query the graph using the RAG interface

```python
from drools_graph_rag.rag.interface import RAGInterface

# Create RAG interface
rag = RAGInterface(connection)

# Process a natural language query
response = rag.process_query("What rules are triggered when a customer places an order?")
print(response)

# Explain a specific rule
explanation = rag.explain_rule_context("ValidateCustomerOrder")
print(explanation)

# Explain rule conflicts
conflicts = rag.explain_rule_conflicts(["OrderValidation", "CustomerValidation"])
print(conflicts)

# Explain execution order
execution_order = rag.explain_execution_order()
print(execution_order)
```

### 3. Use the MCP server for Neo4j integration

The MCP (Model Context Protocol) server provides an interface for integrating with Kiro IDE:

```bash
python -m drools_graph_rag.mcp.neo4j_mcp_server
```

## Running Tests

### Unit Tests

Run all tests:

```bash
python -m unittest discover
```

Run specific test modules:

```bash
python -m unittest drools_graph_rag.tests.test_parser_integration
python -m unittest drools_graph_rag.tests.test_neo4j_connection
python -m unittest drools_graph_rag.tests.test_neo4j_schema
```

### Integration Tests

To run integration tests that require a Neo4j database:

```bash
# Make sure Neo4j is running
docker-compose up -d

# Run integration tests
python -m unittest drools_graph_rag.tests.test_graph_builder_integration
```

## Example Workflow

1. **Start Neo4j**:
   ```bash
   docker-compose up -d
   ```

2. **Parse Drools files and build the graph**:
   ```bash
   python -m drools_graph_rag.examples.build_graph --dir path/to/drools/files
   ```

3. **Run the interactive query interface**:
   ```bash
   python -m drools_graph_rag.examples.interactive_query
   ```

4. **Generate visualizations**:
   ```bash
   python -m drools_graph_rag.examples.generate_visualization --output rule_graph.html
   ```

## Project Structure

```
drools_graph_rag/
├── __init__.py
├── config.py                  # Configuration settings
├── graph/                     # Neo4j graph management
│   ├── __init__.py
│   ├── builder.py             # Graph population logic
│   ├── connection.py          # Neo4j connection utilities
│   └── schema.py              # Graph schema definition
├── mcp/                       # Model Context Protocol server
│   └── neo4j_mcp_server.py    # MCP server implementation
├── parser/                    # Drools parser
│   ├── __init__.py
│   ├── error_handler.py       # Error handling utilities
│   ├── exceptions.py          # Custom exceptions
│   ├── models.py              # Data models
│   └── parser.py              # DRL file parser
├── query_engine/              # Graph query engine
│   ├── __init__.py
│   └── query_engine.py        # Query execution logic
├── rag/                       # RAG interface
│   ├── __init__.py
│   ├── interface.py           # Main RAG interface
│   ├── query_processor.py     # Query processing
│   └── response_generator.py  # Response generation
├── tests/                     # Test modules
│   ├── __init__.py
│   └── ...
└── visualization/             # Visualization components
    ├── __init__.py
    ├── filter.py              # Graph filtering
    ├── generator.py           # Visualization generation
    └── interactive.py         # Interactive features
```

## Troubleshooting

### Neo4j Connection Issues

If you encounter connection issues with Neo4j:

1. Verify that Neo4j is running:
   ```bash
   docker ps | grep neo4j
   ```

2. Check Neo4j logs:
   ```bash
   docker-compose logs neo4j
   ```

3. Ensure the Neo4j credentials in your `.env` file match the ones in `docker-compose.yml`

### Parser Errors

If the parser encounters errors with Drools files:

1. Check the parser logs for specific error messages
2. Verify that the Drools files are valid and properly formatted
3. Try parsing individual files to isolate the issue:
   ```python
   parser = DroolsParser()
   rule_file = parser.parse_file("path/to/problematic/file.drl")
   ```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.