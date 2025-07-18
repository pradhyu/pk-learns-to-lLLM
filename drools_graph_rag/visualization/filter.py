"""
Filtering and search capabilities for the Drools Graph RAG system.

This module provides classes and functions for filtering and searching graph visualizations,
including filtering by properties and searching for nodes.
"""
import logging
import re
from typing import Dict, List, Optional, Any, Union, Tuple, Set

from drools_graph_rag.visualization.generator import GraphVisualizationGenerator

# Configure logging
logger = logging.getLogger(__name__)


class GraphFilterAndSearch:
    """
    A class to add filtering and search capabilities to graph visualizations.
    """

    def __init__(self, visualization_generator: GraphVisualizationGenerator) -> None:
        """
        Initialize the graph filter and search interface.

        Args:
            visualization_generator: A graph visualization generator instance.
        """
        self.visualization_generator = visualization_generator
        self.query_engine = visualization_generator.query_engine
        self.connection = visualization_generator.connection

    def filter_graph_by_properties(
        self, 
        graph_data: Dict[str, Any], 
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Filter the graph visualization by node properties.

        Args:
            graph_data: The current graph data.
            filters: Dictionary of property filters.
                Format: {
                    "node_type": ["rule", "condition"],  # Filter by node type
                    "properties": {
                        "salience": {"min": 50, "max": 100},  # Range filter
                        "name": {"pattern": "Customer.*"},  # Regex pattern filter
                        "package": {"values": ["com.example", "org.test"]}  # List of values filter
                    }
                }

        Returns:
            Filtered graph data.
        """
        try:
            # Start with all nodes
            filtered_nodes = graph_data["nodes"].copy()
            
            # Apply node type filter if specified
            if "node_type" in filters:
                node_types = filters["node_type"]
                if node_types:
                    filtered_nodes = [
                        node for node in filtered_nodes
                        if node.get("type") in node_types or node.get("node_type") in node_types
                    ]
            
            # Apply property filters if specified
            if "properties" in filters:
                property_filters = filters["properties"]
                
                for prop_name, filter_spec in property_filters.items():
                    # Range filter
                    if "min" in filter_spec or "max" in filter_spec:
                        min_val = filter_spec.get("min")
                        max_val = filter_spec.get("max")
                        
                        filtered_nodes = [
                            node for node in filtered_nodes
                            if (min_val is None or 
                                node.get(prop_name, node.get("properties", {}).get(prop_name)) is not None and 
                                float(node.get(prop_name, node.get("properties", {}).get(prop_name))) >= min_val) and
                               (max_val is None or 
                                node.get(prop_name, node.get("properties", {}).get(prop_name)) is not None and 
                                float(node.get(prop_name, node.get("properties", {}).get(prop_name))) <= max_val)
                        ]
                    
                    # Regex pattern filter
                    elif "pattern" in filter_spec:
                        pattern = filter_spec["pattern"]
                        regex = re.compile(pattern)
                        
                        filtered_nodes = [
                            node for node in filtered_nodes
                            if node.get(prop_name, node.get("properties", {}).get(prop_name)) is not None and
                               regex.search(str(node.get(prop_name, node.get("properties", {}).get(prop_name))))
                        ]
                    
                    # List of values filter
                    elif "values" in filter_spec:
                        values = filter_spec["values"]
                        
                        filtered_nodes = [
                            node for node in filtered_nodes
                            if node.get(prop_name, node.get("properties", {}).get(prop_name)) in values
                        ]
            
            # Get the IDs of filtered nodes
            filtered_node_ids = {node["id"] for node in filtered_nodes}
            
            # Filter edges to only include those connecting filtered nodes
            filtered_edges = [
                edge for edge in graph_data["edges"]
                if edge["source"] in filtered_node_ids and edge["target"] in filtered_node_ids
            ]
            
            # Create the filtered graph data
            filtered_graph = {
                "nodes": filtered_nodes,
                "edges": filtered_edges
            }
            
            # Copy view settings if present
            if "view" in graph_data:
                filtered_graph["view"] = graph_data["view"]
            
            return filtered_graph
        except Exception as e:
            logger.error(f"Failed to filter graph: {e}")
            return {"error": str(e)}

    def search_nodes(
        self, 
        query: str, 
        node_types: Optional[List[str]] = None,
        properties: Optional[List[str]] = None,
        case_sensitive: bool = False,
        exact_match: bool = False,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for nodes in the graph based on a query string.

        Args:
            query: The search query string.
            node_types: Optional list of node types to search within.
            properties: Optional list of properties to search in.
            case_sensitive: Whether the search should be case-sensitive.
            exact_match: Whether to require exact matches.
            limit: Maximum number of results to return.

        Returns:
            A list of matching nodes.
        """
        try:
            # Build the Cypher query
            cypher_parts = []
            parameters = {"query": query}
            
            # Add node type filter if specified
            if node_types:
                node_type_conditions = []
                for i, node_type in enumerate(node_types):
                    param_name = f"label_{i}"
                    node_type_conditions.append(f"any(label IN labels(n) WHERE label = ${param_name})")
                    parameters[param_name] = node_type
                
                if node_type_conditions:
                    cypher_parts.append(f"({' OR '.join(node_type_conditions)})")
            
            # Add property search conditions
            property_conditions = []
            
            # If no specific properties are provided, search in common properties
            if not properties:
                properties = ["name", "package", "variable", "type", "method", "field", "value"]
            
            # Build property search conditions
            for i, prop in enumerate(properties):
                param_name = f"prop_{i}"
                
                if exact_match:
                    if case_sensitive:
                        property_conditions.append(f"n.{prop} = $query")
                    else:
                        property_conditions.append(f"toLower(n.{prop}) = toLower($query)")
                else:
                    if case_sensitive:
                        property_conditions.append(f"n.{prop} CONTAINS $query")
                    else:
                        property_conditions.append(f"toLower(n.{prop}) CONTAINS toLower($query)")
            
            if property_conditions:
                cypher_parts.append(f"({' OR '.join(property_conditions)})")
            
            # Combine all conditions
            where_clause = " AND ".join(cypher_parts) if cypher_parts else ""
            
            # Build the final query
            cypher = f"""
            MATCH (n)
            {f'WHERE {where_clause}' if where_clause else ''}
            RETURN n, labels(n) as labels, id(n) as id
            LIMIT {limit}
            """
            
            # Execute the query
            result = self.connection.execute_read_query(cypher, parameters)
            
            # Process results
            nodes = []
            for row in result:
                node = row["n"]
                labels = row["labels"]
                node_id = row["id"]
                
                # Determine node type
                node_type = labels[0].lower() if labels else "unknown"
                
                # Create node object
                node_obj = {
                    "id": node_id,
                    "label": labels[0] if labels else "Unknown",
                    "type": node_type,
                    "properties": {k: v for k, v in node.items()}
                }
                
                nodes.append(node_obj)
            
            return nodes
        except Exception as e:
            logger.error(f"Failed to search nodes: {e}")
            return [{"error": str(e)}]

    def highlight_search_results(
        self, 
        graph_data: Dict[str, Any], 
        search_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Highlight search results in the graph visualization.

        Args:
            graph_data: The current graph data.
            search_results: List of search result nodes.

        Returns:
            Updated graph data with highlighted nodes.
        """
        try:
            # Get the IDs of search result nodes
            result_ids = {node["id"] for node in search_results}
            
            # Update nodes to highlight search results
            for node in graph_data["nodes"]:
                if node["id"] in result_ids:
                    node["highlighted"] = True
                elif "highlighted" in node:
                    del node["highlighted"]
            
            return graph_data
        except Exception as e:
            logger.error(f"Failed to highlight search results: {e}")
            return {"error": str(e)}

    def filter_by_relationship_distance(
        self, 
        graph_data: Dict[str, Any], 
        center_node_id: Union[int, str],
        max_distance: int = 2
    ) -> Dict[str, Any]:
        """
        Filter the graph to show only nodes within a certain relationship distance from a center node.

        Args:
            graph_data: The current graph data.
            center_node_id: The ID of the center node.
            max_distance: Maximum relationship distance from the center node.

        Returns:
            Filtered graph data.
        """
        try:
            # Convert string ID to int if necessary
            if isinstance(center_node_id, str) and center_node_id.isdigit():
                center_node_id = int(center_node_id)
            
            # Query for nodes within the specified distance
            query = """
            MATCH (center)
            WHERE id(center) = $center_id
            MATCH path = (center)-[*1..{max_distance}]-(related)
            RETURN DISTINCT related, id(related) as related_id
            """.format(max_distance=max_distance)
            
            result = self.connection.execute_read_query(
                query, {"center_id": center_node_id}
            )
            
            if not result:
                return {"error": f"No related nodes found for node with ID {center_node_id}"}
            
            # Get the IDs of nodes within the distance
            related_ids = {row["related_id"] for row in result}
            related_ids.add(center_node_id)  # Add the center node
            
            # Filter nodes
            filtered_nodes = [
                node for node in graph_data["nodes"]
                if node["id"] in related_ids
            ]
            
            # Filter edges
            filtered_edges = [
                edge for edge in graph_data["edges"]
                if edge["source"] in related_ids and edge["target"] in related_ids
            ]
            
            # Create the filtered graph data
            filtered_graph = {
                "nodes": filtered_nodes,
                "edges": filtered_edges
            }
            
            # Copy view settings if present
            if "view" in graph_data:
                filtered_graph["view"] = graph_data["view"]
            
            return filtered_graph
        except Exception as e:
            logger.error(f"Failed to filter by relationship distance: {e}")
            return {"error": str(e)}

    def filter_by_rule_type(
        self, 
        graph_data: Dict[str, Any], 
        rule_types: List[str]
    ) -> Dict[str, Any]:
        """
        Filter the graph to show only rules of specific types and their related nodes.

        Args:
            graph_data: The current graph data.
            rule_types: List of rule types to include (e.g., 'entry_point', 'normal', 'terminal').

        Returns:
            Filtered graph data.
        """
        try:
            # Find rule nodes of the specified types
            rule_nodes = [
                node for node in graph_data["nodes"]
                if node.get("type") == "rule" and node.get("rule_type") in rule_types
            ]
            
            # Get the IDs of rule nodes
            rule_ids = {node["id"] for node in rule_nodes}
            
            # Find directly connected nodes
            connected_ids = set()
            for edge in graph_data["edges"]:
                if edge["source"] in rule_ids:
                    connected_ids.add(edge["target"])
                if edge["target"] in rule_ids:
                    connected_ids.add(edge["source"])
            
            # Combine all node IDs to keep
            keep_ids = rule_ids.union(connected_ids)
            
            # Filter nodes
            filtered_nodes = [
                node for node in graph_data["nodes"]
                if node["id"] in keep_ids
            ]
            
            # Filter edges
            filtered_edges = [
                edge for edge in graph_data["edges"]
                if edge["source"] in keep_ids and edge["target"] in keep_ids
            ]
            
            # Create the filtered graph data
            filtered_graph = {
                "nodes": filtered_nodes,
                "edges": filtered_edges
            }
            
            # Copy view settings if present
            if "view" in graph_data:
                filtered_graph["view"] = graph_data["view"]
            
            return filtered_graph
        except Exception as e:
            logger.error(f"Failed to filter by rule type: {e}")
            return {"error": str(e)}

    def filter_by_complexity(
        self, 
        graph_data: Dict[str, Any], 
        min_complexity: Optional[int] = None,
        max_complexity: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Filter the graph to show only rules within a certain complexity range.

        Complexity is calculated based on the number of conditions and actions.

        Args:
            graph_data: The current graph data.
            min_complexity: Minimum complexity (inclusive).
            max_complexity: Maximum complexity (inclusive).

        Returns:
            Filtered graph data.
        """
        try:
            # Calculate complexity for each rule node
            rule_complexities = {}
            
            # Find all rule nodes
            rule_nodes = [
                node for node in graph_data["nodes"]
                if node.get("type") == "rule"
            ]
            
            # Count conditions and actions for each rule
            for rule in rule_nodes:
                rule_id = rule["id"]
                conditions = 0
                actions = 0
                
                for edge in graph_data["edges"]:
                    if edge["source"] == rule_id and edge["type"] == "has_condition":
                        conditions += 1
                    elif edge["source"] == rule_id and edge["type"] == "has_action":
                        actions += 1
                
                # Calculate complexity (simple sum for now)
                complexity = conditions + actions
                rule_complexities[rule_id] = complexity
            
            # Filter rules by complexity
            filtered_rule_ids = set()
            for rule_id, complexity in rule_complexities.items():
                if ((min_complexity is None or complexity >= min_complexity) and
                    (max_complexity is None or complexity <= max_complexity)):
                    filtered_rule_ids.add(rule_id)
            
            # Find directly connected nodes
            connected_ids = set()
            for edge in graph_data["edges"]:
                if edge["source"] in filtered_rule_ids:
                    connected_ids.add(edge["target"])
                if edge["target"] in filtered_rule_ids:
                    connected_ids.add(edge["source"])
            
            # Combine all node IDs to keep
            keep_ids = filtered_rule_ids.union(connected_ids)
            
            # Filter nodes
            filtered_nodes = [
                node for node in graph_data["nodes"]
                if node["id"] in keep_ids
            ]
            
            # Filter edges
            filtered_edges = [
                edge for edge in graph_data["edges"]
                if edge["source"] in keep_ids and edge["target"] in keep_ids
            ]
            
            # Create the filtered graph data
            filtered_graph = {
                "nodes": filtered_nodes,
                "edges": filtered_edges
            }
            
            # Copy view settings if present
            if "view" in graph_data:
                filtered_graph["view"] = graph_data["view"]
            
            return filtered_graph
        except Exception as e:
            logger.error(f"Failed to filter by complexity: {e}")
            return {"error": str(e)}

    def search_by_text_content(
        self, 
        text_query: str,
        case_sensitive: bool = False,
        node_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for nodes containing specific text in their properties.

        Args:
            text_query: The text to search for.
            case_sensitive: Whether the search should be case-sensitive.
            node_types: Optional list of node types to search within.

        Returns:
            A list of matching nodes.
        """
        try:
            # Build the Cypher query
            cypher_parts = []
            parameters = {"query": text_query}
            
            # Add node type filter if specified
            if node_types:
                node_type_conditions = []
                for i, node_type in enumerate(node_types):
                    param_name = f"label_{i}"
                    node_type_conditions.append(f"any(label IN labels(n) WHERE label = ${param_name})")
                    parameters[param_name] = node_type
                
                if node_type_conditions:
                    cypher_parts.append(f"({' OR '.join(node_type_conditions)})")
            
            # Add text search condition
            if case_sensitive:
                cypher_parts.append("""
                (
                    ANY(prop IN keys(n) WHERE 
                        n[prop] IS NOT NULL AND 
                        toString(n[prop]) CONTAINS $query
                    )
                )
                """)
            else:
                cypher_parts.append("""
                (
                    ANY(prop IN keys(n) WHERE 
                        n[prop] IS NOT NULL AND 
                        toLower(toString(n[prop])) CONTAINS toLower($query)
                    )
                )
                """)
            
            # Combine all conditions
            where_clause = " AND ".join(cypher_parts)
            
            # Build the final query
            cypher = f"""
            MATCH (n)
            WHERE {where_clause}
            RETURN n, labels(n) as labels, id(n) as id
            LIMIT 100
            """
            
            # Execute the query
            result = self.connection.execute_read_query(cypher, parameters)
            
            # Process results
            nodes = []
            for row in result:
                node = row["n"]
                labels = row["labels"]
                node_id = row["id"]
                
                # Determine node type
                node_type = labels[0].lower() if labels else "unknown"
                
                # Create node object
                node_obj = {
                    "id": node_id,
                    "label": labels[0] if labels else "Unknown",
                    "type": node_type,
                    "properties": {k: v for k, v in node.items()}
                }
                
                nodes.append(node_obj)
            
            return nodes
        except Exception as e:
            logger.error(f"Failed to search by text content: {e}")
            return [{"error": str(e)}]