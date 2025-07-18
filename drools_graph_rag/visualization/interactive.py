"""
Interactive visualization interface for the Drools Graph RAG system.

This module provides classes and functions for adding interactive features to graph visualizations,
including node detail display on click and graph navigation controls.
"""
import logging
from typing import Dict, List, Optional, Any, Union, Tuple

from drools_graph_rag.visualization.generator import GraphVisualizationGenerator

# Configure logging
logger = logging.getLogger(__name__)


class InteractiveVisualization:
    """
    A class to add interactive features to graph visualizations.
    """

    def __init__(self, visualization_generator: GraphVisualizationGenerator) -> None:
        """
        Initialize the interactive visualization interface.

        Args:
            visualization_generator: A graph visualization generator instance.
        """
        self.visualization_generator = visualization_generator
        self.query_engine = visualization_generator.query_engine

    def get_node_details(self, node_id: Union[int, str]) -> Dict[str, Any]:
        """
        Get detailed information about a specific node.

        Args:
            node_id: The ID of the node to get details for.

        Returns:
            A dictionary with detailed information about the node.
        """
        try:
            # Convert string ID to int if necessary
            if isinstance(node_id, str) and node_id.isdigit():
                node_id = int(node_id)
            
            # Query the node details from Neo4j
            query = """
            MATCH (n)
            WHERE id(n) = $node_id
            RETURN n, labels(n) as labels
            """
            
            result = self.visualization_generator.connection.execute_read_query(
                query, {"node_id": node_id}
            )
            
            if not result:
                return {"error": f"Node with ID {node_id} not found"}
            
            # Extract node properties and labels
            node = result[0]["n"]
            labels = result[0]["labels"]
            
            # Create a base details object
            details = {
                "id": node_id,
                "labels": labels,
                "properties": {k: v for k, v in node.items()}
            }
            
            # Add type-specific details
            if "Rule" in labels:
                self._add_rule_details(details, node)
            elif "Condition" in labels:
                self._add_condition_details(details, node)
            elif "Action" in labels:
                self._add_action_details(details, node)
            elif "Class" in labels:
                self._add_class_details(details, node)
            elif "Constraint" in labels:
                self._add_constraint_details(details, node)
            
            return details
        except Exception as e:
            logger.error(f"Failed to get node details: {e}")
            return {"error": str(e)}

    def _add_rule_details(self, details: Dict[str, Any], node: Dict[str, Any]) -> None:
        """
        Add rule-specific details to the details dictionary.

        Args:
            details: The details dictionary to add to.
            node: The node properties.
        """
        # Get rule file
        query = """
        MATCH (rf:RuleFile)-[:CONTAINS]->(r:Rule)
        WHERE id(r) = $node_id
        RETURN rf.path as file_path, rf.package as package
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["file_path"] = result[0]["file_path"]
            details["package"] = result[0]["package"]
        
        # Get conditions count
        query = """
        MATCH (r:Rule)-[:HAS_CONDITION]->(c:Condition)
        WHERE id(r) = $node_id
        RETURN count(c) as conditions_count
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["conditions_count"] = result[0]["conditions_count"]
        
        # Get actions count
        query = """
        MATCH (r:Rule)-[:HAS_ACTION]->(a:Action)
        WHERE id(r) = $node_id
        RETURN count(a) as actions_count
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["actions_count"] = result[0]["actions_count"]
        
        # Get parent rule if any
        query = """
        MATCH (r:Rule)-[:EXTENDS]->(parent:Rule)
        WHERE id(r) = $node_id
        RETURN parent.name as parent_name, parent.package as parent_package
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["parent"] = {
                "name": result[0]["parent_name"],
                "package": result[0]["parent_package"]
            }

    def _add_condition_details(self, details: Dict[str, Any], node: Dict[str, Any]) -> None:
        """
        Add condition-specific details to the details dictionary.

        Args:
            details: The details dictionary to add to.
            node: The node properties.
        """
        # Get constraints
        query = """
        MATCH (c:Condition)-[:HAS_CONSTRAINT]->(con:Constraint)
        WHERE id(c) = $node_id
        RETURN con.field as field, con.operator as operator, con.value as value
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["constraints"] = [
                {
                    "field": row["field"],
                    "operator": row["operator"],
                    "value": row["value"]
                }
                for row in result
            ]
        
        # Get referenced class
        query = """
        MATCH (c:Condition)-[:REFERENCES]->(cl:Class)
        WHERE id(c) = $node_id
        RETURN cl.name as class_name, cl.package as class_package
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["referenced_class"] = {
                "name": result[0]["class_name"],
                "package": result[0]["class_package"]
            }
        
        # Get parent rule
        query = """
        MATCH (r:Rule)-[:HAS_CONDITION]->(c:Condition)
        WHERE id(c) = $node_id
        RETURN r.name as rule_name, r.package as rule_package
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["parent_rule"] = {
                "name": result[0]["rule_name"],
                "package": result[0]["rule_package"]
            }

    def _add_action_details(self, details: Dict[str, Any], node: Dict[str, Any]) -> None:
        """
        Add action-specific details to the details dictionary.

        Args:
            details: The details dictionary to add to.
            node: The node properties.
        """
        # Get referenced classes
        query = """
        MATCH (a:Action)-[:REFERENCES]->(cl:Class)
        WHERE id(a) = $node_id
        RETURN cl.name as class_name, cl.package as class_package
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["referenced_classes"] = [
                {
                    "name": row["class_name"],
                    "package": row["class_package"]
                }
                for row in result
            ]
        
        # Get modified globals
        query = """
        MATCH (a:Action)-[:MODIFIES]->(g:Global)
        WHERE id(a) = $node_id
        RETURN g.name as global_name, g.type as global_type
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["modified_globals"] = [
                {
                    "name": row["global_name"],
                    "type": row["global_type"]
                }
                for row in result
            ]
        
        # Get parent rule
        query = """
        MATCH (r:Rule)-[:HAS_ACTION]->(a:Action)
        WHERE id(a) = $node_id
        RETURN r.name as rule_name, r.package as rule_package
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["parent_rule"] = {
                "name": result[0]["rule_name"],
                "package": result[0]["rule_package"]
            }

    def _add_class_details(self, details: Dict[str, Any], node: Dict[str, Any]) -> None:
        """
        Add class-specific details to the details dictionary.

        Args:
            details: The details dictionary to add to.
            node: The node properties.
        """
        # Get rules that reference this class in conditions
        query = """
        MATCH (c:Condition)-[:REFERENCES]->(cl:Class)
        WHERE id(cl) = $node_id
        MATCH (r:Rule)-[:HAS_CONDITION]->(c)
        RETURN r.name as rule_name, r.package as rule_package
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["referenced_in_conditions"] = [
                {
                    "name": row["rule_name"],
                    "package": row["rule_package"]
                }
                for row in result
            ]
        
        # Get rules that reference this class in actions
        query = """
        MATCH (a:Action)-[:REFERENCES]->(cl:Class)
        WHERE id(cl) = $node_id
        MATCH (r:Rule)-[:HAS_ACTION]->(a)
        RETURN r.name as rule_name, r.package as rule_package
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["referenced_in_actions"] = [
                {
                    "name": row["rule_name"],
                    "package": row["rule_package"]
                }
                for row in result
            ]
        
        # Get rule files that import this class
        query = """
        MATCH (rf:RuleFile)-[:IMPORTS]->(cl:Class)
        WHERE id(cl) = $node_id
        RETURN rf.path as file_path, rf.package as package
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["imported_in"] = [
                {
                    "file_path": row["file_path"],
                    "package": row["package"]
                }
                for row in result
            ]

    def _add_constraint_details(self, details: Dict[str, Any], node: Dict[str, Any]) -> None:
        """
        Add constraint-specific details to the details dictionary.

        Args:
            details: The details dictionary to add to.
            node: The node properties.
        """
        # Get parent condition
        query = """
        MATCH (c:Condition)-[:HAS_CONSTRAINT]->(con:Constraint)
        WHERE id(con) = $node_id
        RETURN c.variable as variable, c.type as type
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["parent_condition"] = {
                "variable": result[0]["variable"],
                "type": result[0]["type"]
            }
        
        # Get parent rule
        query = """
        MATCH (r:Rule)-[:HAS_CONDITION]->(c:Condition)-[:HAS_CONSTRAINT]->(con:Constraint)
        WHERE id(con) = $node_id
        RETURN r.name as rule_name, r.package as rule_package
        """
        
        result = self.visualization_generator.connection.execute_read_query(
            query, {"node_id": details["id"]}
        )
        
        if result:
            details["parent_rule"] = {
                "name": result[0]["rule_name"],
                "package": result[0]["rule_package"]
            }

    def navigate_to_related_nodes(
        self, 
        node_id: Union[int, str], 
        relationship_type: Optional[str] = None,
        direction: str = "outgoing",
        depth: int = 1
    ) -> Dict[str, Any]:
        """
        Navigate to nodes related to the specified node.

        Args:
            node_id: The ID of the node to navigate from.
            relationship_type: Optional relationship type to filter by.
            direction: The direction of relationships to follow ('outgoing', 'incoming', or 'both').
            depth: The depth of relationships to traverse.

        Returns:
            A dictionary with nodes and edges for visualization.
        """
        try:
            # Convert string ID to int if necessary
            if isinstance(node_id, str) and node_id.isdigit():
                node_id = int(node_id)
            
            # Build the relationship pattern based on direction
            if direction == "outgoing":
                rel_pattern = "-[r]->"
            elif direction == "incoming":
                rel_pattern = "<-[r]-"
            else:  # both
                rel_pattern = "-[r]-"
            
            # Add relationship type filter if specified
            rel_type_filter = f":{relationship_type}" if relationship_type else ""
            
            # Query for related nodes
            query = f"""
            MATCH (n)
            WHERE id(n) = $node_id
            MATCH path = (n){rel_pattern}{rel_type_filter}(related)
            RETURN n, related, r, labels(n) as n_labels, labels(related) as related_labels, type(r) as rel_type
            LIMIT 100
            """
            
            result = self.visualization_generator.connection.execute_read_query(
                query, {"node_id": node_id}
            )
            
            if not result:
                return {"error": f"No related nodes found for node with ID {node_id}"}
            
            # Process results
            nodes = {}
            edges = []
            
            # Add the starting node
            start_node = result[0]["n"]
            start_node_id = node_id
            start_node_labels = result[0]["n_labels"]
            
            nodes[start_node_id] = {
                "id": start_node_id,
                "label": start_node_labels[0] if start_node_labels else "Unknown",
                "properties": {k: v for k, v in start_node.items()},
                "focus": True  # Mark as the focus node
            }
            
            # Add related nodes and edges
            for row in result:
                related_node = row["related"]
                related_node_id = self.visualization_generator.connection.get_node_id(related_node)
                related_node_labels = row["related_labels"]
                relationship = row["r"]
                rel_type = row["rel_type"]
                
                # Add related node if not already added
                if related_node_id not in nodes:
                    nodes[related_node_id] = {
                        "id": related_node_id,
                        "label": related_node_labels[0] if related_node_labels else "Unknown",
                        "properties": {k: v for k, v in related_node.items()}
                    }
                
                # Add edge
                edge_id = f"{start_node_id}_{related_node_id}_{rel_type}"
                edge = {
                    "id": edge_id,
                    "source": start_node_id,
                    "target": related_node_id,
                    "label": rel_type,
                    "type": rel_type.lower()
                }
                
                edges.append(edge)
            
            # Apply layout
            nodes_list = list(nodes.values())
            positioned_nodes = self.visualization_generator._apply_force_directed_layout(nodes_list, edges)
            
            return {
                "nodes": positioned_nodes,
                "edges": edges
            }
        except Exception as e:
            logger.error(f"Failed to navigate to related nodes: {e}")
            return {"error": str(e)}

    def zoom_to_node(self, graph_data: Dict[str, Any], node_id: Union[int, str]) -> Dict[str, Any]:
        """
        Zoom the visualization to focus on a specific node.

        Args:
            graph_data: The current graph data.
            node_id: The ID of the node to zoom to.

        Returns:
            Updated graph data with focus on the specified node.
        """
        try:
            # Convert string ID to int if necessary
            if isinstance(node_id, str) and node_id.isdigit():
                node_id = int(node_id)
            
            # Find the node in the graph data
            target_node = None
            for node in graph_data["nodes"]:
                if node["id"] == node_id:
                    target_node = node
                    break
            
            if not target_node:
                return {"error": f"Node with ID {node_id} not found in the graph data"}
            
            # Mark the target node as focused
            for node in graph_data["nodes"]:
                if "focus" in node:
                    del node["focus"]
            
            target_node["focus"] = True
            
            # Calculate the center position of the target node
            center_x = target_node.get("x", 0)
            center_y = target_node.get("y", 0)
            
            # Update the graph data with zoom information
            graph_data["view"] = {
                "center": {"x": center_x, "y": center_y},
                "zoom": 1.5  # Default zoom level
            }
            
            return graph_data
        except Exception as e:
            logger.error(f"Failed to zoom to node: {e}")
            return {"error": str(e)}

    def pan_graph(
        self, 
        graph_data: Dict[str, Any], 
        direction: str, 
        distance: float = 100.0
    ) -> Dict[str, Any]:
        """
        Pan the graph visualization in the specified direction.

        Args:
            graph_data: The current graph data.
            direction: The direction to pan ('up', 'down', 'left', 'right').
            distance: The distance to pan.

        Returns:
            Updated graph data with adjusted node positions.
        """
        try:
            # Calculate the offset based on direction
            dx, dy = 0, 0
            
            if direction == "up":
                dy = -distance
            elif direction == "down":
                dy = distance
            elif direction == "left":
                dx = -distance
            elif direction == "right":
                dx = distance
            else:
                return {"error": f"Invalid direction: {direction}"}
            
            # Update node positions
            for node in graph_data["nodes"]:
                if "x" in node and "y" in node:
                    node["x"] += dx
                    node["y"] += dy
            
            # Update view center if present
            if "view" in graph_data and "center" in graph_data["view"]:
                graph_data["view"]["center"]["x"] += dx
                graph_data["view"]["center"]["y"] += dy
            
            return graph_data
        except Exception as e:
            logger.error(f"Failed to pan graph: {e}")
            return {"error": str(e)}

    def zoom_graph(
        self, 
        graph_data: Dict[str, Any], 
        zoom_factor: float
    ) -> Dict[str, Any]:
        """
        Zoom the graph visualization by the specified factor.

        Args:
            graph_data: The current graph data.
            zoom_factor: The factor to zoom by (> 1 to zoom in, < 1 to zoom out).

        Returns:
            Updated graph data with adjusted zoom level.
        """
        try:
            # Ensure zoom factor is positive
            if zoom_factor <= 0:
                return {"error": "Zoom factor must be positive"}
            
            # Get or create view information
            if "view" not in graph_data:
                graph_data["view"] = {
                    "center": {"x": 500, "y": 400},  # Default center
                    "zoom": 1.0  # Default zoom level
                }
            
            # Update zoom level
            current_zoom = graph_data["view"].get("zoom", 1.0)
            new_zoom = current_zoom * zoom_factor
            
            # Limit zoom range
            min_zoom = 0.1
            max_zoom = 5.0
            new_zoom = max(min_zoom, min(max_zoom, new_zoom))
            
            graph_data["view"]["zoom"] = new_zoom
            
            return graph_data
        except Exception as e:
            logger.error(f"Failed to zoom graph: {e}")
            return {"error": str(e)}

    def reset_view(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reset the graph visualization view to the default.

        Args:
            graph_data: The current graph data.

        Returns:
            Updated graph data with default view settings.
        """
        try:
            # Calculate the center of the graph
            if not graph_data["nodes"]:
                center_x, center_y = 500, 400  # Default center
            else:
                sum_x = sum(node.get("x", 0) for node in graph_data["nodes"])
                sum_y = sum(node.get("y", 0) for node in graph_data["nodes"])
                count = len(graph_data["nodes"])
                center_x = sum_x / count
                center_y = sum_y / count
            
            # Set default view
            graph_data["view"] = {
                "center": {"x": center_x, "y": center_y},
                "zoom": 1.0  # Default zoom level
            }
            
            return graph_data
        except Exception as e:
            logger.error(f"Failed to reset view: {e}")
            return {"error": str(e)}