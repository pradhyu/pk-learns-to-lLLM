"""
Neo4j graph population logic.

This module provides classes and functions for populating the Neo4j graph
with data from parsed Drools rule files.
"""
import logging
from typing import Dict, List, Optional, Any, Union, Set

from drools_graph_rag.graph.connection import Neo4jConnection, Neo4jQueryError
from drools_graph_rag.graph.schema import Neo4jGraphBuilder
from drools_graph_rag.parser.models import RuleFile, Rule, Condition, Action, Import, Global, Constraint

# Configure logging
logger = logging.getLogger(__name__)


class Neo4jGraphPopulator:
    """
    A class to populate the Neo4j graph with data from parsed Drools rule files.
    """

    def __init__(self, graph_builder: Neo4jGraphBuilder) -> None:
        """
        Initialize the Neo4j graph populator.

        Args:
            graph_builder: A Neo4j graph builder.
        """
        self.graph_builder = graph_builder
        self.connection = graph_builder.connection
        self.batch_size = 1000  # Default batch size

    def populate_graph(self, rule_files: List[RuleFile], batch_size: int = 1000) -> None:
        """
        Populate the Neo4j graph with data from parsed Drools rule files.

        Args:
            rule_files: A list of parsed RuleFile objects.
            batch_size: The batch size for database operations.
        """
        self.batch_size = batch_size
        
        try:
            # Initialize the graph schema if needed
            self.graph_builder.initialize_graph()
            
            # Create rule files
            self._create_rule_files(rule_files)
            
            # Create imports and classes
            self._create_imports_and_classes(rule_files)
            
            # Create globals
            self._create_globals(rule_files)
            
            # Create rules
            self._create_rules(rule_files)
            
            # Create conditions and constraints
            self._create_conditions_and_constraints(rule_files)
            
            # Create actions
            self._create_actions(rule_files)
            
            # Create relationships
            self._create_relationships(rule_files)
            
            logger.info(f"Graph populated with {len(rule_files)} rule files")
        except Neo4jQueryError as e:
            logger.error(f"Failed to populate graph: {e}")
            raise

    def _create_rule_files(self, rule_files: List[RuleFile]) -> None:
        """
        Create RuleFile nodes in the graph.

        Args:
            rule_files: A list of parsed RuleFile objects.
        """
        logger.info(f"Creating {len(rule_files)} RuleFile nodes")
        
        # Prepare batch queries
        queries = []
        for rule_file in rule_files:
            query = {
                "query": """
                MERGE (rf:RuleFile {path: $path})
                SET rf.package = $package
                RETURN rf
                """,
                "parameters": {
                    "path": rule_file.path,
                    "package": rule_file.package
                }
            }
            queries.append(query)
        
        # Execute batch
        self._execute_batch(queries)

    def _create_imports_and_classes(self, rule_files: List[RuleFile]) -> None:
        """
        Create Import relationships and Class nodes in the graph.

        Args:
            rule_files: A list of parsed RuleFile objects.
        """
        # Collect all unique imports
        all_imports = set()
        for rule_file in rule_files:
            for imp in rule_file.imports:
                all_imports.add((imp.package, imp.class_name))
        
        logger.info(f"Creating {len(all_imports)} Class nodes")
        
        # Create Class nodes
        class_queries = []
        for package, class_name in all_imports:
            query = {
                "query": """
                MERGE (c:Class {full_name: $full_name})
                SET c.package = $package,
                    c.name = $name
                RETURN c
                """,
                "parameters": {
                    "full_name": f"{package}.{class_name}",
                    "package": package,
                    "name": class_name
                }
            }
            class_queries.append(query)
        
        # Execute batch
        self._execute_batch(class_queries)
        
        # Create Import relationships
        import_queries = []
        for rule_file in rule_files:
            for imp in rule_file.imports:
                query = {
                    "query": """
                    MATCH (rf:RuleFile {path: $path})
                    MATCH (c:Class {full_name: $full_name})
                    MERGE (rf)-[r:IMPORTS]->(c)
                    RETURN r
                    """,
                    "parameters": {
                        "path": rule_file.path,
                        "full_name": imp.full_name
                    }
                }
                import_queries.append(query)
        
        # Execute batch
        self._execute_batch(import_queries)

    def _create_globals(self, rule_files: List[RuleFile]) -> None:
        """
        Create Global nodes in the graph.

        Args:
            rule_files: A list of parsed RuleFile objects.
        """
        # Collect all globals
        global_queries = []
        for rule_file in rule_files:
            for glob in rule_file.globals:
                # Create Global node
                query = {
                    "query": """
                    MATCH (rf:RuleFile {path: $path})
                    MERGE (g:Global {name: $name, package: $package})
                    SET g.type = $type
                    MERGE (rf)-[r:DECLARES]->(g)
                    RETURN g
                    """,
                    "parameters": {
                        "path": rule_file.path,
                        "name": glob.name,
                        "type": glob.type,
                        "package": rule_file.package
                    }
                }
                global_queries.append(query)
        
        # Execute batch
        self._execute_batch(global_queries)

    def _create_rules(self, rule_files: List[RuleFile]) -> None:
        """
        Create Rule nodes in the graph.

        Args:
            rule_files: A list of parsed RuleFile objects.
        """
        # Create Rule nodes
        rule_queries = []
        for rule_file in rule_files:
            for rule in rule_file.rules:
                query = {
                    "query": """
                    MATCH (rf:RuleFile {path: $path})
                    MERGE (r:Rule {name: $name, package: $package})
                    SET r.salience = $salience
                    MERGE (rf)-[rel:CONTAINS]->(r)
                    RETURN r
                    """,
                    "parameters": {
                        "path": rule_file.path,
                        "name": rule.name,
                        "package": rule_file.package,
                        "salience": rule.salience
                    }
                }
                rule_queries.append(query)
                
                # If the rule extends another rule, create the EXTENDS relationship
                if rule.extends:
                    extends_query = {
                        "query": """
                        MATCH (r1:Rule {name: $name, package: $package})
                        MATCH (r2:Rule {name: $extends_name})
                        MERGE (r1)-[r:EXTENDS]->(r2)
                        RETURN r
                        """,
                        "parameters": {
                            "name": rule.name,
                            "package": rule_file.package,
                            "extends_name": rule.extends
                        }
                    }
                    rule_queries.append(extends_query)
        
        # Execute batch
        self._execute_batch(rule_queries)

    def _create_conditions_and_constraints(self, rule_files: List[RuleFile]) -> None:
        """
        Create Condition and Constraint nodes in the graph.

        Args:
            rule_files: A list of parsed RuleFile objects.
        """
        # Create Condition and Constraint nodes
        condition_queries = []
        for rule_file in rule_files:
            for rule in rule_file.rules:
                for i, condition in enumerate(rule.conditions):
                    # Create Condition node
                    condition_query = {
                        "query": """
                        MATCH (r:Rule {name: $rule_name, package: $package})
                        CREATE (c:Condition {
                            id: $condition_id,
                            variable: $variable,
                            type: $type,
                            position: $position
                        })
                        CREATE (r)-[rel:HAS_CONDITION {position: $position}]->(c)
                        RETURN c
                        """,
                        "parameters": {
                            "rule_name": rule.name,
                            "package": rule_file.package,
                            "condition_id": f"{rule_file.package}.{rule.name}.condition.{i}",
                            "variable": condition.variable,
                            "type": condition.type,
                            "position": i
                        }
                    }
                    condition_queries.append(condition_query)
                    
                    # Create Constraint nodes
                    for j, constraint in enumerate(condition.constraints):
                        constraint_query = {
                            "query": """
                            MATCH (c:Condition {id: $condition_id})
                            CREATE (con:Constraint {
                                id: $constraint_id,
                                field: $field,
                                operator: $operator,
                                value: $value,
                                position: $position
                            })
                            CREATE (c)-[rel:HAS_CONSTRAINT {position: $position}]->(con)
                            RETURN con
                            """,
                            "parameters": {
                                "condition_id": f"{rule_file.package}.{rule.name}.condition.{i}",
                                "constraint_id": f"{rule_file.package}.{rule.name}.condition.{i}.constraint.{j}",
                                "field": constraint.field,
                                "operator": constraint.operator,
                                "value": constraint.value,
                                "position": j
                            }
                        }
                        condition_queries.append(constraint_query)
                    
                    # Create REFERENCES relationship to Class
                    class_query = {
                        "query": """
                        MATCH (c:Condition {id: $condition_id})
                        MATCH (cl:Class)
                        WHERE cl.name = $type OR cl.full_name ENDS WITH $type
                        MERGE (c)-[r:REFERENCES]->(cl)
                        RETURN r
                        """,
                        "parameters": {
                            "condition_id": f"{rule_file.package}.{rule.name}.condition.{i}",
                            "type": condition.type
                        }
                    }
                    condition_queries.append(class_query)
        
        # Execute batch
        self._execute_batch(condition_queries)

    def _create_actions(self, rule_files: List[RuleFile]) -> None:
        """
        Create Action nodes in the graph.

        Args:
            rule_files: A list of parsed RuleFile objects.
        """
        # Create Action nodes
        action_queries = []
        for rule_file in rule_files:
            for rule in rule_file.rules:
                for i, action in enumerate(rule.actions):
                    # Create Action node
                    action_query = {
                        "query": """
                        MATCH (r:Rule {name: $rule_name, package: $package})
                        CREATE (a:Action {
                            id: $action_id,
                            type: $type,
                            target: $target,
                            method: $method,
                            position: $position
                        })
                        CREATE (r)-[rel:HAS_ACTION {position: $position}]->(a)
                        RETURN a
                        """,
                        "parameters": {
                            "rule_name": rule.name,
                            "package": rule_file.package,
                            "action_id": f"{rule_file.package}.{rule.name}.action.{i}",
                            "type": action.type,
                            "target": action.target,
                            "method": action.method,
                            "position": i
                        }
                    }
                    action_queries.append(action_query)
                    
                    # Create REFERENCES relationship to Global if target is a global
                    global_query = {
                        "query": """
                        MATCH (a:Action {id: $action_id})
                        MATCH (g:Global {name: $target})
                        MERGE (a)-[r:MODIFIES]->(g)
                        RETURN r
                        """,
                        "parameters": {
                            "action_id": f"{rule_file.package}.{rule.name}.action.{i}",
                            "target": action.target
                        }
                    }
                    action_queries.append(global_query)
                    
                    # Store action arguments as properties
                    if action.arguments:
                        args_query = {
                            "query": """
                            MATCH (a:Action {id: $action_id})
                            SET a.arguments = $arguments
                            RETURN a
                            """,
                            "parameters": {
                                "action_id": f"{rule_file.package}.{rule.name}.action.{i}",
                                "arguments": action.arguments
                            }
                        }
                        action_queries.append(args_query)
        
        # Execute batch
        self._execute_batch(action_queries)

    def _create_relationships(self, rule_files: List[RuleFile]) -> None:
        """
        Create additional relationships in the graph.

        Args:
            rule_files: A list of parsed RuleFile objects.
        """
        # This method can be extended to create additional relationships
        # based on more complex analysis of the rules
        pass

    def _execute_batch(self, queries: List[Dict[str, Any]]) -> None:
        """
        Execute a batch of queries.

        Args:
            queries: A list of query dictionaries with 'query' and 'parameters' keys.
        """
        if not queries:
            return
            
        logger.debug(f"Executing batch of {len(queries)} queries")
        
        # Execute in batches
        for i in range(0, len(queries), self.batch_size):
            batch = queries[i:i+self.batch_size]
            self.connection.execute_batch(batch)
            logger.debug(f"Executed batch {i//self.batch_size + 1} of {(len(queries) - 1)//self.batch_size + 1}")

    def update_graph(self, rule_files: List[RuleFile], batch_size: int = 1000) -> None:
        """
        Update the Neo4j graph with data from parsed Drools rule files.
        This method will only update or add new data, not remove existing data.

        Args:
            rule_files: A list of parsed RuleFile objects.
            batch_size: The batch size for database operations.
        """
        self.batch_size = batch_size
        
        try:
            # Initialize the graph schema if needed
            self.graph_builder.initialize_graph()
            
            # Get existing rule file paths
            existing_paths = self._get_existing_rule_file_paths()
            
            # Split rule files into new and existing
            new_rule_files = []
            existing_rule_files = []
            
            for rule_file in rule_files:
                if rule_file.path in existing_paths:
                    existing_rule_files.append(rule_file)
                else:
                    new_rule_files.append(rule_file)
            
            logger.info(f"Updating graph with {len(existing_rule_files)} existing and {len(new_rule_files)} new rule files")
            
            # Update existing rule files
            if existing_rule_files:
                self._update_existing_rule_files(existing_rule_files)
            
            # Add new rule files
            if new_rule_files:
                self.populate_graph(new_rule_files, batch_size)
            
            logger.info(f"Graph updated with {len(rule_files)} rule files")
        except Neo4jQueryError as e:
            logger.error(f"Failed to update graph: {e}")
            raise

    def _get_existing_rule_file_paths(self) -> Set[str]:
        """
        Get the paths of existing rule files in the graph.
        
        Returns:
            A set of rule file paths.
        """
        result = self.connection.execute_read_query(
            "MATCH (rf:RuleFile) RETURN rf.path as path"
        )
        return {record["path"] for record in result if "path" in record}

    def _update_existing_rule_files(self, rule_files: List[RuleFile]) -> None:
        """
        Update existing rule files in the graph.

        Args:
            rule_files: A list of parsed RuleFile objects.
        """
        for rule_file in rule_files:
            # Delete existing rule file data
            self._delete_rule_file_data(rule_file.path)
        
        # Repopulate with new data
        self.populate_graph(rule_files, self.batch_size)

    def _delete_rule_file_data(self, path: str) -> None:
        """
        Delete all data related to a rule file.

        Args:
            path: The path of the rule file.
        """
        logger.info(f"Deleting existing data for rule file: {path}")
        
        # Delete all relationships and nodes related to the rule file
        query = """
        MATCH (rf:RuleFile {path: $path})
        OPTIONAL MATCH (rf)-[:CONTAINS]->(r:Rule)
        OPTIONAL MATCH (r)-[:HAS_CONDITION]->(c:Condition)
        OPTIONAL MATCH (c)-[:HAS_CONSTRAINT]->(con:Constraint)
        OPTIONAL MATCH (r)-[:HAS_ACTION]->(a:Action)
        
        // Delete all relationships
        OPTIONAL MATCH (rf)-[ri:IMPORTS]->()
        OPTIONAL MATCH (rf)-[rd:DECLARES]->()
        OPTIONAL MATCH (r)-[rc:CONTAINS]->()
        OPTIONAL MATCH (r)-[re:EXTENDS]->()
        OPTIONAL MATCH (r)-[rhc:HAS_CONDITION]->()
        OPTIONAL MATCH (c)-[rhco:HAS_CONSTRAINT]->()
        OPTIONAL MATCH (r)-[rha:HAS_ACTION]->()
        OPTIONAL MATCH (c)-[rref:REFERENCES]->()
        OPTIONAL MATCH (a)-[rmod:MODIFIES]->()
        
        DELETE ri, rd, rc, re, rhc, rhco, rha, rref, rmod
        
        // Delete nodes
        DELETE con, c, a, r, rf
        """
        
        self.connection.execute_write_query(query, {"path": path})


class Neo4jGraphManager:
    """
    A class to manage the Neo4j graph for the Drools Graph RAG system.
    This class combines the functionality of Neo4jGraphBuilder and Neo4jGraphPopulator.
    """

    def __init__(self, connection: Neo4jConnection) -> None:
        """
        Initialize the Neo4j graph manager.

        Args:
            connection: A Neo4j connection.
        """
        self.connection = connection
        self.graph_builder = Neo4jGraphBuilder(connection)
        self.graph_populator = Neo4jGraphPopulator(self.graph_builder)

    def initialize_graph(self) -> None:
        """
        Initialize the graph by creating the schema.
        """
        self.graph_builder.initialize_graph()

    def populate_graph(self, rule_files: List[RuleFile], batch_size: int = 1000) -> None:
        """
        Populate the Neo4j graph with data from parsed Drools rule files.

        Args:
            rule_files: A list of parsed RuleFile objects.
            batch_size: The batch size for database operations.
        """
        self.graph_populator.populate_graph(rule_files, batch_size)

    def update_graph(self, rule_files: List[RuleFile], batch_size: int = 1000) -> None:
        """
        Update the Neo4j graph with data from parsed Drools rule files.

        Args:
            rule_files: A list of parsed RuleFile objects.
            batch_size: The batch size for database operations.
        """
        self.graph_populator.update_graph(rule_files, batch_size)

    def clear_graph(self) -> None:
        """
        Clear the graph by deleting all nodes and relationships.
        """
        self.graph_builder.clear_graph()

    def reset_graph(self) -> None:
        """
        Reset the graph by clearing it and recreating the schema.
        """
        self.graph_builder.reset_graph()

    def get_graph_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the graph.
        
        Returns:
            Dictionary with graph statistics.
        """
        return self.graph_builder.get_graph_statistics()