"""
Main entry point for the Drools Graph RAG application.
"""
import argparse
import logging
import os
import sys

from drools_graph_rag.config import config
from drools_graph_rag.graph.connection import Neo4jConnection


def setup_logging(log_level: str) -> None:
    """
    Set up logging configuration.

    Args:
        log_level: The log level to use.
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


def test_neo4j_connection() -> bool:
    """
    Test the Neo4j connection.

    Returns:
        True if the connection is successful, False otherwise.
    """
    try:
        connection = Neo4jConnection(
            uri=config.neo4j.uri,
            username=config.neo4j.username,
            password=config.neo4j.password,
            database=config.neo4j.database,
        )
        connection.execute_query("RETURN 1")
        connection.close()
        return True
    except Exception as e:
        logging.error(f"Failed to connect to Neo4j: {e}")
        return False


def main() -> None:
    """
    Main entry point.
    """
    parser = argparse.ArgumentParser(description="Drools Graph RAG")
    parser.add_argument(
        "--log-level",
        type=str,
        default=config.log_level,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the log level",
    )
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test the Neo4j connection",
    )
    args = parser.parse_args()

    # Set up logging
    setup_logging(args.log_level)

    if args.test_connection:
        if test_neo4j_connection():
            logging.info("Neo4j connection successful")
        else:
            logging.error("Neo4j connection failed")
            sys.exit(1)


if __name__ == "__main__":
    main()