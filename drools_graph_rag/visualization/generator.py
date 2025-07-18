"""
Graph visualization generator for the Drools Graph RAG system.

This module provides classes and functions for generating visualizations of the Neo4j graph,
including node and edge rendering and layout algorithms for clear visualization.
"""
import logging
from typing import Dict, List, Optional, Any, Union, Tuple

from drools_graph_rag.graph.connection import Neo4jConnection, Neo4jQueryError
from drools_graph_rag.query_engine.query_engine import GraphQueryEngine

# Configure logging
logger = logging.getLogger(__name__)


class GraphVisualizationGenerator:
    """
    A class to generate graph visualizations for the Drools Graph RAG system.
    """

    def __init__(self, query_engine: GraphQueryEngine) -> None:
        """
        Initialize the graph visualization generator.

        Args:
            query_engine: A graph query engine instance.
        """
        self.query_engine = query_engine
        self.connection = query_engine.connection

    def generate_rule_graph(
        self, 
        rule_names: Optional[List[str]] = None,
        include_conditions: bool = True,
        include_actions: bool = True,
        include_classes: bool = True,
        layout_algorithm: str = "force_directed"
    ) -> Dict[str, Any]:
        """
        Generate a graph visualization of rules and their relationships.

        Args:
            rule_names: Optional list of rule names to include. If None, includes all rules.
            include_conditions: Whether to include condition nodes.
            include_actions: Whether to include action nodes.
            include_classes: Whether to include class nodes.
            layout_algorithm: The layout algorithm to use ('force_directed', 'hierarchical', 'circular').

        Returns:
            A dictionary with nodes and edges for visualization.
        """
        try:
            # Build the query based on parameters
            rule_filter = ""
            parameters = {}
            
            if rule_names:
                rule_filter = "WHERE r.name IN $rule_names"
                parameters["rule_names"] = rule_names
            
            # Base query to get rules
            query = f"""
            // Match rules
            MATCH (r:Rule)
            {rule_filter}
            
            // Return rule nodes
            WITH r
            
            // Collect rule nodes
            WITH collect({{
                id: id(r),
                label: 'Rule',
                name: r.name,
                package: r.package,
                salience: r.salience,
                type: 'rule'
            }}) as rule_nodes
            
            // Return the nodes
            RETURN rule_nodes
            """
            
            # Execute the query
            result = self.connection.execute_read_query(query, parameters)
            rule_nodes = result[0]["rule_nodes"] if result else []
            
            # Get rule relationships (extends)
            extends_query = f"""
            // Match rule extends relationships
            MATCH (r1:Rule)-[:EXTENDS]->(r2:Rule)
            {rule_filter}
            
            // Return edges
            RETURN collect({{
                source: id(r1),
                target: id(r2),
                type: 'extends',
                label: 'EXTENDS'
            }}) as extends_edges
            """
            
            extends_result = self.connection.execute_read_query(extends_query, parameters)
            extends_edges = extends_result[0]["extends_edges"] if extends_result else []
            
            # Initialize nodes and edges
            nodes = rule_nodes
            edges = extends_edges
            
            # Add condition nodes if requested
            if include_conditions:
                conditions_query = f"""
                // Match conditions
                MATCH (r:Rule)-[:HAS_CONDITION]->(c:Condition)
                {rule_filter}
                
                // Return condition nodes and edges
                RETURN collect({{
                    id: id(c),
                    label: 'Condition',
                    variable: c.variable,
                    type: c.type,
                    node_type: 'condition'
                }}) as condition_nodes,
                collect({{
                    source: id(r),
                    target: id(c),
                    type: 'has_condition',
                    label: 'HAS_CONDITION'
                }}) as condition_edges
                """
                
                conditions_result = self.connection.execute_read_query(conditions_query, parameters)
                if conditions_result:
                    nodes.extend(conditions_result[0]["condition_nodes"])
                    edges.extend(conditions_result[0]["condition_edges"])
                    
                    # Add constraint nodes
                    constraints_query = f"""
                    // Match constraints
                    MATCH (r:Rule)-[:HAS_CONDITION]->(c:Condition)-[:HAS_CONSTRAINT]->(con:Constraint)
                    {rule_filter}
                    
                    // Return constraint nodes and edges
                    RETURN collect({{
                        id: id(con),
                        label: 'Constraint',
                        field: con.field,
                        operator: con.operator,
                        value: con.value,
                        node_type: 'constraint'
                    }}) as constraint_nodes,
                    collect({{
                        source: id(c),
                        target: id(con),
                        type: 'has_constraint',
                        label: 'HAS_CONSTRAINT'
                    }}) as constraint_edges
                    """
                    
                    constraints_result = self.connection.execute_read_query(constraints_query, parameters)
                    if constraints_result:
                        nodes.extend(constraints_result[0]["constraint_nodes"])
                        edges.extend(constraints_result[0]["constraint_edges"])
            
            # Add action nodes if requested
            if include_actions:
                actions_query = f"""
                // Match actions
                MATCH (r:Rule)-[:HAS_ACTION]->(a:Action)
                {rule_filter}
                
                // Return action nodes and edges
                RETURN collect({{
                    id: id(a),
                    label: 'Action',
                    type: a.type,
                    target: a.target,
                    method: a.method,
                    node_type: 'action'
                }}) as action_nodes,
                collect({{
                    source: id(r),
                    target: id(a),
                    type: 'has_action',
                    label: 'HAS_ACTION'
                }}) as action_edges
                """
                
                actions_result = self.connection.execute_read_query(actions_query, parameters)
                if actions_result:
                    nodes.extend(actions_result[0]["action_nodes"])
                    edges.extend(actions_result[0]["action_edges"])
            
            # Add class nodes if requested
            if include_classes:
                classes_query = f"""
                // Match classes referenced by conditions
                MATCH (r:Rule)-[:HAS_CONDITION]->(c:Condition)-[:REFERENCES]->(cl:Class)
                {rule_filter}
                
                // Return class nodes and edges
                WITH collect({{
                    id: id(cl),
                    label: 'Class',
                    name: cl.name,
                    package: cl.package,
                    full_name: cl.full_name,
                    node_type: 'class'
                }}) as class_nodes_from_conditions,
                collect({{
                    source: id(c),
                    target: id(cl),
                    type: 'references',
                    label: 'REFERENCES'
                }}) as class_edges_from_conditions
                
                // Match classes referenced by actions
                MATCH (r:Rule)-[:HAS_ACTION]->(a:Action)-[:REFERENCES]->(cl:Class)
                {rule_filter}
                
                // Return class nodes and edges
                WITH class_nodes_from_conditions, class_edges_from_conditions,
                collect({{
                    id: id(cl),
                    label: 'Class',
                    name: cl.name,
                    package: cl.package,
                    full_name: cl.full_name,
                    node_type: 'class'
                }}) as class_nodes_from_actions,
                collect({{
                    source: id(a),
                    target: id(cl),
                    type: 'references',
                    label: 'REFERENCES'
                }}) as class_edges_from_actions
                
                // Combine results
                RETURN class_nodes_from_conditions + class_nodes_from_actions as class_nodes,
                class_edges_from_conditions + class_edges_from_actions as class_edges
                """
                
                classes_result = self.connection.execute_read_query(classes_query, parameters)
                if classes_result:
                    # Deduplicate class nodes by ID
                    class_nodes_map = {}
                    for node in classes_result[0]["class_nodes"]:
                        class_nodes_map[node["id"]] = node
                    
                    nodes.extend(list(class_nodes_map.values()))
                    edges.extend(classes_result[0]["class_edges"])
            
            # Apply layout algorithm
            positioned_nodes = self._apply_layout(nodes, edges, layout_algorithm)
            
            return {
                "nodes": positioned_nodes,
                "edges": edges
            }
        except Neo4jQueryError as e:
            logger.error(f"Failed to generate rule graph: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error generating rule graph: {e}")
            return {"error": str(e)}

    def _apply_layout(
        self, 
        nodes: List[Dict], 
        edges: List[Dict], 
        algorithm: str
    ) -> List[Dict]:
        """
        Apply a layout algorithm to position nodes.

        Args:
            nodes: List of node dictionaries.
            edges: List of edge dictionaries.
            algorithm: The layout algorithm to use.

        Returns:
            List of nodes with position attributes added.
        """
        if algorithm == "force_directed":
            return self._apply_force_directed_layout(nodes, edges)
        elif algorithm == "hierarchical":
            return self._apply_hierarchical_layout(nodes, edges)
        elif algorithm == "circular":
            return self._apply_circular_layout(nodes)
        else:
            logger.warning(f"Unknown layout algorithm: {algorithm}. Using force directed.")
            return self._apply_force_directed_layout(nodes, edges)

    def _apply_force_directed_layout(
        self, 
        nodes: List[Dict], 
        edges: List[Dict]
    ) -> List[Dict]:
        """
        Apply a force-directed layout algorithm.

        This is a simple implementation that positions nodes based on a 
        force-directed algorithm. For production use, consider using a 
        specialized graph layout library.

        Args:
            nodes: List of node dictionaries.
            edges: List of edge dictionaries.

        Returns:
            List of nodes with position attributes added.
        """
        # Create a map of node IDs to indices
        node_indices = {node["id"]: i for i, node in enumerate(nodes)}
        
        # Initialize positions randomly
        import random
        width, height = 1000, 800
        
        for node in nodes:
            node["x"] = random.uniform(0, width)
            node["y"] = random.uniform(0, height)
        
        # Define force parameters
        iterations = 100
        k = 20  # Optimal distance
        gravity = 0.1
        damping = 0.9
        
        # Run force-directed algorithm
        for _ in range(iterations):
            # Calculate repulsive forces between all nodes
            for i, node1 in enumerate(nodes):
                force_x, force_y = 0, 0
                
                # Repulsive forces from other nodes
                for j, node2 in enumerate(nodes):
                    if i != j:
                        dx = node1["x"] - node2["x"]
                        dy = node1["y"] - node2["y"]
                        distance = max(0.1, (dx * dx + dy * dy) ** 0.5)
                        
                        # Repulsive force is inversely proportional to distance
                        force = k * k / distance
                        force_x += dx / distance * force
                        force_y += dy / distance * force
                
                # Attractive forces from edges
                for edge in edges:
                    if edge["source"] == node1["id"] and edge["target"] in node_indices:
                        target_idx = node_indices[edge["target"]]
                        target = nodes[target_idx]
                        dx = node1["x"] - target["x"]
                        dy = node1["y"] - target["y"]
                        distance = max(0.1, (dx * dx + dy * dy) ** 0.5)
                        
                        # Attractive force is proportional to distance
                        force = distance * distance / k
                        force_x -= dx / distance * force
                        force_y -= dy / distance * force
                    
                    elif edge["target"] == node1["id"] and edge["source"] in node_indices:
                        source_idx = node_indices[edge["source"]]
                        source = nodes[source_idx]
                        dx = node1["x"] - source["x"]
                        dy = node1["y"] - source["y"]
                        distance = max(0.1, (dx * dx + dy * dy) ** 0.5)
                        
                        # Attractive force is proportional to distance
                        force = distance * distance / k
                        force_x -= dx / distance * force
                        force_y -= dy / distance * force
                
                # Gravity force towards center
                center_dx = width / 2 - node1["x"]
                center_dy = height / 2 - node1["y"]
                force_x += gravity * center_dx
                force_y += gravity * center_dy
                
                # Apply forces with damping
                node1["x"] += force_x * damping
                node1["y"] += force_y * damping
                
                # Keep nodes within bounds
                node1["x"] = max(10, min(width - 10, node1["x"]))
                node1["y"] = max(10, min(height - 10, node1["y"]))
        
        return nodes

    def _apply_hierarchical_layout(
        self, 
        nodes: List[Dict], 
        edges: List[Dict]
    ) -> List[Dict]:
        """
        Apply a hierarchical layout algorithm.

        This algorithm positions nodes in layers based on their dependencies.

        Args:
            nodes: List of node dictionaries.
            edges: List of edge dictionaries.

        Returns:
            List of nodes with position attributes added.
        """
        # Create a map of node IDs to indices
        node_indices = {node["id"]: i for i, node in enumerate(nodes)}
        
        # Create adjacency lists
        outgoing = {node["id"]: [] for node in nodes}
        incoming = {node["id"]: [] for node in nodes}
        
        for edge in edges:
            if edge["source"] in outgoing and edge["target"] in incoming:
                outgoing[edge["source"]].append(edge["target"])
                incoming[edge["target"]].append(edge["source"])
        
        # Assign layers using a topological sort approach
        layers = []
        remaining = set(node["id"] for node in nodes)
        
        while remaining:
            # Find nodes with no incoming edges
            current_layer = [node_id for node_id in remaining if not any(src in remaining for src in incoming[node_id])]
            
            if not current_layer:
                # Handle cycles by picking a node arbitrarily
                current_layer = [next(iter(remaining))]
            
            layers.append(current_layer)
            remaining -= set(current_layer)
        
        # Position nodes based on layers
        width, height = 1000, 800
        layer_height = height / (len(layers) + 1)
        
        for layer_idx, layer in enumerate(layers):
            layer_width = width / (len(layer) + 1)
            for node_idx, node_id in enumerate(layer):
                if node_id in node_indices:
                    node = nodes[node_indices[node_id]]
                    node["x"] = (node_idx + 1) * layer_width
                    node["y"] = (layer_idx + 1) * layer_height
        
        return nodes

    def _apply_circular_layout(self, nodes: List[Dict]) -> List[Dict]:
        """
        Apply a circular layout algorithm.

        This algorithm positions nodes in a circle.

        Args:
            nodes: List of node dictionaries.

        Returns:
            List of nodes with position attributes added.
        """
        import math
        
        # Define circle parameters
        width, height = 1000, 800
        center_x, center_y = width / 2, height / 2
        radius = min(width, height) * 0.4
        
        # Position nodes in a circle
        for i, node in enumerate(nodes):
            angle = 2 * math.pi * i / len(nodes)
            node["x"] = center_x + radius * math.cos(angle)
            node["y"] = center_y + radius * math.sin(angle)
        
        return nodes

    def generate_rule_dependency_graph(self, rule_name: str) -> Dict[str, Any]:
        """
        Generate a graph visualization focused on a specific rule and its dependencies.

        Args:
            rule_name: The name of the rule to focus on.

        Returns:
            A dictionary with nodes and edges for visualization.
        """
        try:
            # Get rule dependencies
            dependencies = self.query_engine.find_rule_dependencies(rule_name)
            
            if "error" in dependencies:
                return {"error": dependencies["error"]}
            
            # Start with the main rule
            rule = dependencies["rule"]
            nodes = [{
                "id": rule["id"],
                "label": "Rule",
                "name": rule["name"],
                "package": rule["package"],
                "salience": rule["salience"],
                "type": "rule",
                "focus": True  # Mark as the focus node
            }]
            
            edges = []
            
            # Add parent rules
            for parent in dependencies["parents"]:
                parent_id = self.query_engine.find_rule_by_exact_name(
                    parent["name"], parent["package"]
                )["id"]
                
                nodes.append({
                    "id": parent_id,
                    "label": "Rule",
                    "name": parent["name"],
                    "package": parent["package"],
                    "type": "rule",
                    "relationship": "parent"
                })
                
                edges.append({
                    "source": rule["id"],
                    "target": parent_id,
                    "type": "extends",
                    "label": "EXTENDS"
                })
            
            # Add rules this rule depends on
            for dep in dependencies["depends_on"]:
                dep_id = self.query_engine.find_rule_by_exact_name(
                    dep["name"], dep["package"]
                )["id"]
                
                nodes.append({
                    "id": dep_id,
                    "label": "Rule",
                    "name": dep["name"],
                    "package": dep["package"],
                    "type": "rule",
                    "relationship": "depends_on"
                })
                
                edges.append({
                    "source": rule["id"],
                    "target": dep_id,
                    "type": "depends_on",
                    "label": "DEPENDS_ON"
                })
            
            # Add rules that depend on this rule
            for dep in dependencies["dependent_rules"]:
                dep_id = self.query_engine.find_rule_by_exact_name(
                    dep["name"], dep["package"]
                )["id"]
                
                nodes.append({
                    "id": dep_id,
                    "label": "Rule",
                    "name": dep["name"],
                    "package": dep["package"],
                    "type": "rule",
                    "relationship": "dependent"
                })
                
                edges.append({
                    "source": dep_id,
                    "target": rule["id"],
                    "type": "depends_on",
                    "label": "DEPENDS_ON"
                })
            
            # Apply force-directed layout
            positioned_nodes = self._apply_force_directed_layout(nodes, edges)
            
            return {
                "nodes": positioned_nodes,
                "edges": edges
            }
        except Exception as e:
            logger.error(f"Failed to generate rule dependency graph: {e}")
            return {"error": str(e)}

    def generate_execution_path_graph(self, rule_names: List[str]) -> Dict[str, Any]:
        """
        Generate a graph visualization of the execution path for a set of rules.

        Args:
            rule_names: List of rule names to include in the execution path.

        Returns:
            A dictionary with nodes and edges for visualization.
        """
        try:
            # Get execution order analysis
            execution_order = self.query_engine.analyze_execution_order(rule_names)
            
            if not execution_order:
                return {"error": "No execution path found for the specified rules"}
            
            # Create nodes for each rule in the execution order
            nodes = []
            edges = []
            
            for i, rule in enumerate(execution_order):
                # Add rule node
                rule_id = rule.get("id")
                if not rule_id:
                    # If ID is not available, use a generated one
                    rule_id = f"rule_{i}"
                
                nodes.append({
                    "id": rule_id,
                    "label": "Rule",
                    "name": rule["name"],
                    "package": rule["package"],
                    "salience": rule["original_salience"],
                    "effective_salience": rule["effective_salience"],
                    "type": "rule",
                    "execution_order": i + 1,
                    "rule_type": rule["rule_type"]
                })
                
                # Add edges for dependencies
                for dep in rule.get("depends_on", []):
                    dep_id = None
                    
                    # Find the ID of the dependency rule
                    for j, other_rule in enumerate(execution_order):
                        if other_rule["name"] == dep["name"] and other_rule["package"] == dep["package"]:
                            dep_id = other_rule.get("id", f"rule_{j}")
                            break
                    
                    if dep_id:
                        edges.append({
                            "source": rule_id,
                            "target": dep_id,
                            "type": "depends_on",
                            "label": "DEPENDS_ON"
                        })
            
            # Apply hierarchical layout for execution path
            positioned_nodes = self._apply_hierarchical_layout(nodes, edges)
            
            return {
                "nodes": positioned_nodes,
                "edges": edges
            }
        except Exception as e:
            logger.error(f"Failed to generate execution path graph: {e}")
            return {"error": str(e)}

    def export_graph_as_json(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export graph data in a format suitable for visualization libraries.

        Args:
            graph_data: Graph data from one of the generation methods.

        Returns:
            A dictionary with formatted graph data.
        """
        if "error" in graph_data:
            return graph_data
        
        # Format for visualization libraries (e.g., D3.js, Cytoscape.js)
        return {
            "nodes": [
                {
                    "id": str(node["id"]),
                    "label": node.get("name", node.get("label", "")),
                    "type": node.get("type", "unknown"),
                    "data": {k: v for k, v in node.items() if k not in ["id", "x", "y"]},
                    "position": {"x": node.get("x", 0), "y": node.get("y", 0)}
                }
                for node in graph_data["nodes"]
            ],
            "edges": [
                {
                    "id": f"e{i}",
                    "source": str(edge["source"]),
                    "target": str(edge["target"]),
                    "label": edge.get("label", ""),
                    "type": edge.get("type", "unknown")
                }
                for i, edge in enumerate(graph_data["edges"])
            ]
        }