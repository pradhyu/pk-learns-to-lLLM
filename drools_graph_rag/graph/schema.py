"""
Neo4j graph schema creation and management.

This module provides classes and functions for creating and managing the Neo4j graph schema
for the Drools Graph RAG system, including node labels, relationship types, indexes, and constraints.
"""
import logging
from typing import Dict, List, Optional, Any, Union

from drools_graph_rag.graph.connection import Neo4jConnection, Neo4jQueryError

# Configure logging
logger = logging.getLogger(__name__)


class Neo4jSchemaManager:
    """
    A class to manage the Neo4j graph schema for the Drools Graph RAG system.
    """

    def __init__(self, connection: Neo4jConnection) -> None:
        """
        Initialize the Neo4j schema manager.

        Args:
            connection: A Neo4j connection.
        """
        self.connection = connection

    def create_schema(self) -> None:
        """
        Create the complete schema for the Drools Graph RAG system.
        This includes constraints, indexes, and any other schema elements.
        """
        try:
            # Create constraints first to ensure uniqueness
            self._create_constraints()
            
            # Create indexes for performance
            self._create_indexes()
            
            logger.info("Neo4j schema created successfully")
        except Neo4jQueryError as e:
            logger.error(f"Failed to create Neo4j schema: {e}")
            raise

    def _create_constraints(self) -> None:
        """
        Create constraints for the Neo4j graph.
        """
        constraints = [
            # RuleFile constraints
            """
            CREATE CONSTRAINT rule_file_path_unique IF NOT EXISTS
            FOR (rf:RuleFile) REQUIRE rf.path IS UNIQUE
            """,
            
            # Rule constraints
            """
            CREATE CONSTRAINT rule_name_package_unique IF NOT EXISTS
            FOR (r:Rule) REQUIRE (r.name, r.package) IS UNIQUE
            """,
            
            # Class constraints
            """
            CREATE CONSTRAINT class_full_name_unique IF NOT EXISTS
            FOR (c:Class) REQUIRE c.full_name IS UNIQUE
            """,
            
            # Global constraints
            """
            CREATE CONSTRAINT global_name_package_unique IF NOT EXISTS
            FOR (g:Global) REQUIRE (g.name, g.package) IS UNIQUE
            """
        ]
        
        for constraint in constraints:
            try:
                self.connection.execute_write_query(constraint)
                logger.debug(f"Created constraint: {constraint}")
            except Neo4jQueryError as e:
                # Check if the error is because the constraint already exists
                if "already exists" in str(e):
                    logger.warning(f"Constraint already exists: {constraint}")
                else:
                    logger.error(f"Failed to create constraint: {constraint}")
                    raise

    def _create_indexes(self) -> None:
        """
        Create indexes for the Neo4j graph.
        """
        indexes = [
            # RuleFile indexes
            """
            CREATE INDEX rule_file_package_idx IF NOT EXISTS
            FOR (rf:RuleFile) ON (rf.package)
            """,
            
            # Rule indexes
            """
            CREATE INDEX rule_name_idx IF NOT EXISTS
            FOR (r:Rule) ON (r.name)
            """,
            
            """
            CREATE INDEX rule_salience_idx IF NOT EXISTS
            FOR (r:Rule) ON (r.salience)
            """,
            
            # Condition indexes
            """
            CREATE INDEX condition_type_idx IF NOT EXISTS
            FOR (c:Condition) ON (c.type)
            """,
            
            # Action indexes
            """
            CREATE INDEX action_type_idx IF NOT EXISTS
            FOR (a:Action) ON (a.type)
            """,
            
            # Class indexes
            """
            CREATE INDEX class_name_idx IF NOT EXISTS
            FOR (c:Class) ON (c.name)
            """,
            
            """
            CREATE INDEX class_package_idx IF NOT EXISTS
            FOR (c:Class) ON (c.package)
            """
        ]
        
        for index in indexes:
            try:
                self.connection.execute_write_query(index)
                logger.debug(f"Created index: {index}")
            except Neo4jQueryError as e:
                # Check if the error is because the index already exists
                if "already exists" in str(e):
                    logger.warning(f"Index already exists: {index}")
                else:
                    logger.error(f"Failed to create index: {index}")
                    raise

    def clear_schema(self) -> None:
        """
        Clear the schema by dropping all constraints and indexes.
        """
        try:
            # Drop constraints
            self._drop_constraints()
            
            # Drop indexes
            self._drop_indexes()
            
            logger.info("Neo4j schema cleared successfully")
        except Neo4jQueryError as e:
            logger.error(f"Failed to clear Neo4j schema: {e}")
            raise

    def _drop_constraints(self) -> None:
        """
        Drop all constraints from the Neo4j graph.
        """
        try:
            # Get all constraints
            constraints = self.connection.execute_read_query(
                "SHOW CONSTRAINTS"
            )
            
            # Drop each constraint
            for constraint in constraints:
                constraint_name = constraint.get("name")
                if constraint_name:
                    self.connection.execute_write_query(
                        f"DROP CONSTRAINT {constraint_name} IF EXISTS"
                    )
                    logger.debug(f"Dropped constraint: {constraint_name}")
        except Neo4jQueryError as e:
            logger.error(f"Failed to drop constraints: {e}")
            raise

    def _drop_indexes(self) -> None:
        """
        Drop all indexes from the Neo4j graph.
        """
        try:
            # Get all indexes
            indexes = self.connection.execute_read_query(
                "SHOW INDEXES"
            )
            
            # Drop each index
            for index in indexes:
                index_name = index.get("name")
                if index_name and not index.get("type") == "CONSTRAINT":
                    self.connection.execute_write_query(
                        f"DROP INDEX {index_name} IF EXISTS"
                    )
                    logger.debug(f"Dropped index: {index_name}")
        except Neo4jQueryError as e:
            logger.error(f"Failed to drop indexes: {e}")
            raise

    def check_schema_exists(self) -> bool:
        """
        Check if the schema exists.
        
        Returns:
            True if the schema exists, False otherwise.
        """
        try:
            # Check if at least one of our constraints exists
            result = self.connection.execute_read_query(
                """
                SHOW CONSTRAINTS
                WHERE name = 'rule_file_path_unique'
                """
            )
            return len(result) > 0
        except Neo4jQueryError as e:
            logger.error(f"Failed to check if schema exists: {e}")
            return False

    def get_schema_info(self) -> Dict[str, Any]:
        """
        Get information about the current schema.
        
        Returns:
            Dictionary with schema information.
        """
        try:
            constraints = self.connection.execute_read_query(
                "SHOW CONSTRAINTS"
            )
            
            indexes = self.connection.execute_read_query(
                "SHOW INDEXES WHERE type <> 'CONSTRAINT'"
            )
            
            return {
                "constraints": constraints,
                "indexes": indexes
            }
        except Neo4jQueryError as e:
            logger.error(f"Failed to get schema info: {e}")
            return {"error": str(e)}


class Neo4jGraphBuilder:
    """
    A class to build and manage the Neo4j graph for the Drools Graph RAG system.
    """

    def __init__(self, connection: Neo4jConnection) -> None:
        """
        Initialize the Neo4j graph builder.

        Args:
            connection: A Neo4j connection.
        """
        self.connection = connection
        self.schema_manager = Neo4jSchemaManager(connection)

    def initialize_graph(self) -> None:
        """
        Initialize the graph by creating the schema.
        """
        # Check if schema exists
        if not self.schema_manager.check_schema_exists():
            logger.info("Schema does not exist, creating...")
            self.schema_manager.create_schema()
        else:
            logger.info("Schema already exists")

    def clear_graph(self) -> None:
        """
        Clear the graph by deleting all nodes and relationships.
        """
        try:
            # Delete all relationships first
            self.connection.execute_write_query(
                "MATCH ()-[r]-() DELETE r"
            )
            logger.info("All relationships deleted")
            
            # Then delete all nodes
            self.connection.execute_write_query(
                "MATCH (n) DELETE n"
            )
            logger.info("All nodes deleted")
        except Neo4jQueryError as e:
            logger.error(f"Failed to clear graph: {e}")
            raise

    def reset_graph(self) -> None:
        """
        Reset the graph by clearing it and recreating the schema.
        """
        try:
            # Clear the graph
            self.clear_graph()
            
            # Clear the schema
            self.schema_manager.clear_schema()
            
            # Recreate the schema
            self.schema_manager.create_schema()
            
            logger.info("Graph reset successfully")
        except Neo4jQueryError as e:
            logger.error(f"Failed to reset graph: {e}")
            raise

    def get_graph_statistics(self) -> Dict[str, int]:
        """
        Get statistics about the graph.
        
        Returns:
            Dictionary with graph statistics.
        """
        try:
            # Get node counts by label
            node_counts = self.connection.execute_read_query(
                """
                CALL apoc.meta.stats()
                YIELD labels
                RETURN labels
                """
            )
            
            if not node_counts:
                return {"error": "Failed to get node counts"}
            
            # Get relationship counts by type
            rel_counts = self.connection.execute_read_query(
                """
                CALL apoc.meta.stats()
                YIELD relTypes
                RETURN relTypes
                """
            )
            
            if not rel_counts:
                return {"error": "Failed to get relationship counts"}
            
            # Combine the results
            stats = {
                "nodes": node_counts[0].get("labels", {}),
                "relationships": rel_counts[0].get("relTypes", {})
            }
            
            # Add total counts
            stats["total_nodes"] = sum(stats["nodes"].values())
            stats["total_relationships"] = sum(stats["relationships"].values())
            
            return stats
        except Neo4jQueryError as e:
            logger.error(f"Failed to get graph statistics: {e}")
            return {"error": str(e)}