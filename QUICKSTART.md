# Drools Graph RAG - Quick Start Guide

This guide provides step-by-step instructions to quickly get started with the Drools Graph RAG system.

## Quick Setup

### 1. Start Neo4j Database

The first step is to start the Neo4j database using Docker Compose:

```bash
docker-compose up -d
```

This will start a Neo4j instance with the following default credentials:
- URL: bolt://localhost:7687
- Username: neo4j
- Password: password

You can verify that Neo4j is running by visiting http://localhost:7474 in your browser.

### 2. Activate Virtual Environment

If you're using a virtual environment (recommended):

```bash
# On Linux/macOS
source .venv/bin/activate

# On Windows
.venv\Scripts\activate
```

### 3. Run the Main Application

The main application can be run with:

```bash
python -m drools_graph_rag.main
```

This will:
1. Parse the sample Drools files in the `drools` directory
2. Build the Neo4j graph
3. Start an interactive query interface

## Sample Queries to Try

Once the application is running, you can try these sample queries:

1. "What rules are in the system?"
2. "Show me rules related to customer validation"
3. "What are the dependencies of the OrderProcessing rule?"
4. "Are there any conflicting rules?"
5. "What is the execution order of rules?"
6. "Explain the CustomerValidation rule"

## Visualizing the Graph

To generate a visualization of the rule graph:

```bash
python -m drools_graph_rag.visualization.generator --output rule_graph.html
```

This will create an HTML file that you can open in your browser to see an interactive visualization of the rule graph.

## Running Tests

To run the tests:

```bash
python -m unittest discover
```

## Next Steps

- Explore the API documentation in the `docs` directory
- Check out the examples in the `examples` directory
- Try parsing your own Drools files by modifying the paths in the main script
- Experiment with different queries to understand your rule base better

For more detailed information, refer to the full README.md file.