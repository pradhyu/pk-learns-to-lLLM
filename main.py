#!/usr/bin/env python3
"""
Main entry point for the Drools Graph RAG application.
This script demonstrates the complete workflow:
1. Parse Drools files
2. Build Neo4j graph
3. Query the graph using natural language
"""
import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from drools_graph_rag.config import config
from drools_graph_rag.graph.connection import Neo4jConnection
from drools_graph_rag.graph.builder import Neo4jGraphManager
from drools_graph_rag.parser.parser import DroolsParser
from drools_graph_rag.parser.models import RuleFile
from drools_graph_rag.rag.interface import RAGInterface

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_drools_files(directory_path: str, recursive: bool = True) -> List[RuleFile]:
    """
    Parse Drools files from a directory.
    
    Args:
        directory_path: Path to the directory containing Drools files.
        recursive: Whether to scan subdirectories recursively.
        
    Returns:
        List of parsed RuleFile objects.
    """
    logger.info(f"Parsing Drools files from {directory_path} (recursive={recursive})")
    parser = DroolsParser()
    rule_files = parser.parse_directory(directory_path, recursive=recursive)
    logger.info(f"Parsed {len(rule_files)} rule files")
    return rule_files


def build_graph(rule_files: List[RuleFile], reset: bool = False) -> Neo4jGraphManager:
    """
    Build the Neo4j graph from parsed rule files.
    
    Args:
        rule_files: List of parsed RuleFile objects.
        reset: Whether to reset the graph before building.
        
    Returns:
        Neo4jGraphManager instance.
    """
    logger.info("Connecting to Neo4j database")
    connection = Neo4jConnection(
        uri=config.neo4j.uri,
        username=config.neo4j.username,
        password=config.neo4j.password,
        database=config.neo4j.database
    )
    
    graph_manager = Neo4jGraphManager(connection)
    
    if reset:
        logger.info("Resetting graph")
        graph_manager.reset_graph()
    else:
        logger.info("Initializing graph")
        graph_manager.initialize_graph()
    
    logger.info(f"Populating graph with {len(rule_files)} rule files")
    graph_manager.populate_graph(rule_files)
    
    # Get graph statistics
    stats = graph_manager.get_graph_statistics()
    logger.info(f"Graph statistics: {stats}")
    
    return graph_manager


def interactive_query(connection: Neo4jConnection) -> None:
    """
    Start an interactive query session.
    
    Args:
        connection: Neo4j connection to use.
    """
    rag = RAGInterface(connection)
    
    print("\n=== Drools Graph RAG Interactive Query ===")
    print("Enter your questions about the Drools rules (or 'exit' to quit)")
    print("Example queries:")
    print("  - What rules are in the system?")
    print("  - Show me rules related to customer validation")
    print("  - What are the dependencies of the OrderProcessing rule?")
    print("  - Are there any conflicting rules?")
    print("  - What is the execution order of rules?")
    print("  - Explain the CustomerValidation rule")
    
    while True:
        try:
            query = input("\nQuery: ")
            if query.lower() in ('exit', 'quit', 'q'):
                break
                
            if not query.strip():
                continue
                
            response = rag.process_query(query)
            print("\nResponse:")
            print(response)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            print(f"Error: {e}")
    
    print("\nExiting interactive query mode.")


def main() -> None:
    """
    Main entry point for the application.
    """
    parser = argparse.ArgumentParser(description="Drools Graph RAG Application")
    parser.add_argument(
        "--dir", 
        type=str, 
        default="drools",
        help="Directory containing Drools files"
    )
    parser.add_argument(
        "--recursive", 
        action="store_true", 
        help="Scan directory recursively"
    )
    parser.add_argument(
        "--reset", 
        action="store_true", 
        help="Reset the graph before building"
    )
    parser.add_argument(
        "--no-interactive", 
        action="store_true", 
        help="Skip interactive query mode"
    )
    
    args = parser.parse_args()
    
    # Check if directory exists
    if not os.path.isdir(args.dir):
        logger.error(f"Directory not found: {args.dir}")
        sys.exit(1)
    
    # Parse Drools files
    rule_files = parse_drools_files(args.dir, args.recursive)
    
    if not rule_files:
        logger.error(f"No Drools files found in {args.dir}")
        sys.exit(1)
    
    # Build graph
    graph_manager = build_graph(rule_files, args.reset)
    
    # Start interactive query mode
    if not args.no_interactive:
        interactive_query(graph_manager.connection)
    
    logger.info("Application completed successfully")


if __name__ == "__main__":
    main()