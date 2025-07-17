"""
Graph query engine for the Drools Graph RAG system.

This module provides classes and functions for querying the Neo4j graph database
to retrieve information about Drools rules, their relationships, and dependencies.
"""
import logging
from typing import Dict, List, Optional, Any, Union, Tuple, Set

from drools_graph_rag.graph.connection import Neo4jConnection, Neo4jQueryError

# Configure logging
logger = logging.getLogger(__name__)


class GraphQueryEngine:
    """
    A class to query the Neo4j graph for the Drools Graph RAG system.
    """

    def __init__(self, connection: Neo4jConnection) -> None:
        """
        Initialize the graph query engine.

        Args:
            connection: A Neo4j connection.
        """
        self.connection = connection

    def find_rules_by_name(self, name_pattern: str) -> List[Dict]:
        """
        Find rules by name pattern using case-insensitive regex matching.

        Args:
            name_pattern: The name pattern to search for.

        Returns:
            A list of rules matching the pattern.
        """
        try:
            query = """
            MATCH (r:Rule)
            WHERE r.name =~ $name_pattern
            RETURN r.name as name, r.package as package, r.salience as salience,
                   id(r) as id
            ORDER BY r.name
            """
            
            # Make the pattern case-insensitive
            if not name_pattern.startswith("(?i)"):
                name_pattern = f"(?i){name_pattern}"
                
            parameters = {"name_pattern": name_pattern}
            
            return self.connection.execute_read_query(query, parameters)
        except Neo4jQueryError as e:
            logger.error(f"Failed to find rules by name: {e}")
            return []

    def find_rule_by_exact_name(self, name: str, package: Optional[str] = None) -> Optional[Dict]:
        """
        Find a rule by its exact name and optionally package.

        Args:
            name: The exact name of the rule.
            package: The package of the rule (optional).

        Returns:
            The rule if found, None otherwise.
        """
        try:
            if package:
                query = """
                MATCH (r:Rule {name: $name, package: $package})
                RETURN r.name as name, r.package as package, r.salience as salience,
                       id(r) as id
                """
                parameters = {"name": name, "package": package}
            else:
                query = """
                MATCH (r:Rule {name: $name})
                RETURN r.name as name, r.package as package, r.salience as salience,
                       id(r) as id
                """
                parameters = {"name": name}
            
            results = self.connection.execute_read_query(query, parameters)
            return results[0] if results else None
        except Neo4jQueryError as e:
            logger.error(f"Failed to find rule by exact name: {e}")
            return None

    def find_rules_by_property(self, property_name: str, property_value: Any) -> List[Dict]:
        """
        Find rules by a specific property value.

        Args:
            property_name: The name of the property.
            property_value: The value of the property.

        Returns:
            A list of rules with the specified property value.
        """
        try:
            query = """
            MATCH (r:Rule)
            WHERE r[$property_name] = $property_value
            RETURN r.name as name, r.package as package, r.salience as salience,
                   id(r) as id
            ORDER BY r.name
            """
            parameters = {
                "property_name": property_name,
                "property_value": property_value
            }
            
            return self.connection.execute_read_query(query, parameters)
        except Neo4jQueryError as e:
            logger.error(f"Failed to find rules by property: {e}")
            return []

    def find_rules_by_class_reference(self, class_name: str) -> List[Dict]:
        """
        Find rules that reference a specific class.

        Args:
            class_name: The name of the class.

        Returns:
            A list of rules that reference the class.
        """
        try:
            query = """
            MATCH (r:Rule)-[:HAS_CONDITION]->(c:Condition)-[:REFERENCES]->(cl:Class)
            WHERE cl.name = $class_name OR cl.full_name = $class_name
            RETURN DISTINCT r.name as name, r.package as package, r.salience as salience,
                   id(r) as id
            UNION
            MATCH (r:Rule)-[:HAS_ACTION]->(a:Action)-[:REFERENCES]->(cl:Class)
            WHERE cl.name = $class_name OR cl.full_name = $class_name
            RETURN DISTINCT r.name as name, r.package as package, r.salience as salience,
                   id(r) as id
            """
            parameters = {"class_name": class_name}
            
            return self.connection.execute_read_query(query, parameters)
        except Neo4jQueryError as e:
            logger.error(f"Failed to find rules by class reference: {e}")
            return []

    def get_rule_details(self, rule_id: int) -> Dict:
        """
        Get detailed information about a rule.

        Args:
            rule_id: The ID of the rule.

        Returns:
            A dictionary with rule details.
        """
        try:
            query = """
            MATCH (r:Rule)
            WHERE id(r) = $rule_id
            OPTIONAL MATCH (r)-[:HAS_CONDITION]->(c:Condition)
            OPTIONAL MATCH (c)-[:HAS_CONSTRAINT]->(con:Constraint)
            OPTIONAL MATCH (r)-[:HAS_ACTION]->(a:Action)
            RETURN r.name as name, r.package as package, r.salience as salience,
                   collect(DISTINCT {
                       variable: c.variable,
                       type: c.type,
                       constraints: collect(DISTINCT {
                           field: con.field,
                           operator: con.operator,
                           value: con.value
                       })
                   }) as conditions,
                   collect(DISTINCT {
                       type: a.type,
                       target: a.target,
                       method: a.method,
                       arguments: a.arguments
                   }) as actions
            """
            parameters = {"rule_id": rule_id}
            
            results = self.connection.execute_read_query(query, parameters)
            return results[0] if results else {}
        except Neo4jQueryError as e:
            logger.error(f"Failed to get rule details: {e}")
            return {}

    def find_rule_dependencies(self, rule_name: str, package: Optional[str] = None) -> Dict:
        """
        Find dependencies of a specific rule.

        Args:
            rule_name: The name of the rule.
            package: The package of the rule (optional).

        Returns:
            A dictionary with rule dependencies.
        """
        try:
            # Find the rule first
            rule = self.find_rule_by_exact_name(rule_name, package)
            if not rule:
                logger.warning(f"Rule not found: {rule_name}")
                return {"error": f"Rule not found: {rule_name}"}
            
            rule_id = rule["id"]
            
            # Find parent rules (extends)
            parent_query = """
            MATCH (r:Rule)-[:EXTENDS]->(parent:Rule)
            WHERE id(r) = $rule_id
            RETURN parent.name as name, parent.package as package, 'extends' as relationship_type
            """
            
            # Find rules that this rule depends on (referenced in conditions or actions)
            depends_on_query = """
            MATCH (r:Rule)-[:HAS_CONDITION]->(c:Condition)-[:REFERENCES]->(cl:Class)<-[:REFERENCES]-(c2:Condition)<-[:HAS_CONDITION]-(r2:Rule)
            WHERE id(r) = $rule_id AND id(r) <> id(r2)
            RETURN DISTINCT r2.name as name, r2.package as package, 'depends_on' as relationship_type
            UNION
            MATCH (r:Rule)-[:HAS_ACTION]->(a:Action)-[:REFERENCES]->(cl:Class)<-[:REFERENCES]-(c:Condition)<-[:HAS_CONDITION]-(r2:Rule)
            WHERE id(r) = $rule_id AND id(r) <> id(r2)
            RETURN DISTINCT r2.name as name, r2.package as package, 'depends_on' as relationship_type
            """
            
            # Find rules that depend on this rule
            dependent_rules_query = """
            MATCH (r:Rule)-[:HAS_CONDITION]->(c:Condition)-[:REFERENCES]->(cl:Class)<-[:REFERENCES]-(c2:Condition)<-[:HAS_CONDITION]-(r2:Rule)
            WHERE id(r2) = $rule_id AND id(r) <> id(r2)
            RETURN DISTINCT r.name as name, r.package as package, 'dependent' as relationship_type
            UNION
            MATCH (r:Rule)-[:HAS_ACTION]->(a:Action)-[:REFERENCES]->(cl:Class)<-[:REFERENCES]-(c:Condition)<-[:HAS_CONDITION]-(r2:Rule)
            WHERE id(r2) = $rule_id AND id(r) <> id(r2)
            RETURN DISTINCT r.name as name, r.package as package, 'dependent' as relationship_type
            """
            
            parameters = {"rule_id": rule_id}
            
            parents = self.connection.execute_read_query(parent_query, parameters)
            depends_on = self.connection.execute_read_query(depends_on_query, parameters)
            dependent_rules = self.connection.execute_read_query(dependent_rules_query, parameters)
            
            return {
                "rule": rule,
                "parents": parents,
                "depends_on": depends_on,
                "dependent_rules": dependent_rules
            }
        except Neo4jQueryError as e:
            logger.error(f"Failed to find rule dependencies: {e}")
            return {"error": str(e)}

    def get_all_rules(self) -> List[Dict]:
        """
        Get all rules in the graph.

        Returns:
            A list of all rules.
        """
        try:
            query = """
            MATCH (r:Rule)
            RETURN r.name as name, r.package as package, r.salience as salience,
                   id(r) as id
            ORDER BY r.package, r.name
            """
            
            return self.connection.execute_read_query(query)
        except Neo4jQueryError as e:
            logger.error(f"Failed to get all rules: {e}")
            return []

    def get_rules_by_package(self, package: str) -> List[Dict]:
        """
        Get all rules in a specific package.

        Args:
            package: The package name.

        Returns:
            A list of rules in the package.
        """
        try:
            query = """
            MATCH (r:Rule {package: $package})
            RETURN r.name as name, r.package as package, r.salience as salience,
                   id(r) as id
            ORDER BY r.name
            """
            parameters = {"package": package}
            
            return self.connection.execute_read_query(query, parameters)
        except Neo4jQueryError as e:
            logger.error(f"Failed to get rules by package: {e}")
            return []

    def get_all_packages(self) -> List[str]:
        """
        Get all packages in the graph.

        Returns:
            A list of all packages.
        """
        try:
            query = """
            MATCH (r:Rule)
            RETURN DISTINCT r.package as package
            ORDER BY package
            """
            
            results = self.connection.execute_read_query(query)
            return [result["package"] for result in results]
        except Neo4jQueryError as e:
            logger.error(f"Failed to get all packages: {e}")
            return []

    def get_all_classes(self) -> List[Dict]:
        """
        Get all classes referenced in the graph.

        Returns:
            A list of all classes.
        """
        try:
            query = """
            MATCH (c:Class)
            RETURN c.name as name, c.package as package, c.full_name as full_name
            ORDER BY c.package, c.name
            """
            
            return self.connection.execute_read_query(query)
        except Neo4jQueryError as e:
            logger.error(f"Failed to get all classes: {e}")
            return []
            
    def find_unused_rules(self) -> List[Dict]:
        """
        Find rules that are never referenced or triggered by other rules.
        
        A rule is considered unused if:
        1. No other rule extends it
        2. No other rule depends on it (through class references)
        3. It's not a top-level rule with no dependencies (these are entry points)
        
        Returns:
            A list of unused rules with their details.
        """
        try:
            query = """
            // Find rules that are not extended by any other rule
            // and are not referenced through class dependencies
            // and are not entry point rules (rules with no dependencies)
            MATCH (r:Rule)
            WHERE NOT EXISTS {
                // Rules that are extended by other rules
                MATCH (r)<-[:EXTENDS]-(:Rule)
            }
            AND NOT EXISTS {
                // Rules that are referenced through class dependencies
                MATCH (r)-[:HAS_ACTION]->(a:Action)-[:REFERENCES]->(cl:Class)<-[:REFERENCES]-(:Condition)<-[:HAS_CONDITION]-(:Rule)
                WHERE r <> r
            }
            AND NOT EXISTS {
                // Rules that are entry points (have no dependencies themselves)
                MATCH (r)-[:HAS_CONDITION]->(c:Condition)
                WHERE NOT EXISTS {
                    MATCH (c)-[:REFERENCES]->(:Class)
                }
            }
            // Exclude rules that are directly referenced in rule chains
            AND NOT EXISTS {
                MATCH (r)<-[:DEPENDS_ON]-(:Rule)
            }
            RETURN r.name as name, r.package as package, r.salience as salience,
                   id(r) as id, 
                   'unused' as reason
            """
            
            return self.connection.execute_read_query(query)
        except Neo4jQueryError as e:
            logger.error(f"Failed to find unused rules: {e}")
            return []
            
    def find_circular_dependencies(self) -> List[Dict]:
        """
        Find circular dependencies between rules.
        
        A circular dependency exists when rule A depends on rule B,
        and rule B depends on rule A (directly or indirectly).
        
        Returns:
            A list of circular dependency chains with the involved rules.
        """
        try:
            # This query finds paths where a rule depends on itself through other rules
            query = """
            // Find circular dependencies through class references
            MATCH path = (r1:Rule)-[:HAS_CONDITION|HAS_ACTION*1..2]->(n)-[:REFERENCES]->(cl:Class)
                        <-[:REFERENCES]-(m)<-[:HAS_CONDITION|HAS_ACTION*1..2]-(r2:Rule),
                  circular_path = (r2)-[:HAS_CONDITION|HAS_ACTION*1..2]->(p)-[:REFERENCES]->(cl2:Class)
                                <-[:REFERENCES]-(q)<-[:HAS_CONDITION|HAS_ACTION*1..2]-(r1)
            WHERE id(r1) <> id(r2) AND id(cl) <> id(cl2)
            
            // Extract the rules in the circular dependency
            WITH r1, r2, 
                 [r1.name + ' (' + r1.package + ')', r2.name + ' (' + r2.package + ')'] as cycle_rules,
                 cl.name as shared_class1,
                 cl2.name as shared_class2
            
            RETURN DISTINCT
                cycle_rules,
                r1.name as from_rule,
                r1.package as from_package,
                r2.name as to_rule,
                r2.package as to_package,
                [shared_class1, shared_class2] as shared_classes
            """
            
            # Execute the query
            results = self.connection.execute_read_query(query)
            
            # Process the results to make them more readable
            processed_results = []
            for result in results:
                processed_result = {
                    "cycle": result["cycle_rules"],
                    "from_rule": {
                        "name": result["from_rule"],
                        "package": result["from_package"]
                    },
                    "to_rule": {
                        "name": result["to_rule"],
                        "package": result["to_package"]
                    },
                    "shared_classes": result["shared_classes"]
                }
                processed_results.append(processed_result)
            
            return processed_results
        except Neo4jQueryError as e:
            logger.error(f"Failed to find circular dependencies: {e}")
            return []
    
    def find_complex_rules(self, complexity_threshold: int = 5) -> List[Dict]:
        """
        Find rules that exceed a complexity threshold.
        
        Complexity is calculated based on:
        1. Number of conditions
        2. Number of constraints per condition
        3. Number of actions
        4. Number of referenced classes
        
        Args:
            complexity_threshold: The threshold above which a rule is considered complex.
                                 Default is 5.
        
        Returns:
            A list of complex rules with their complexity metrics.
        """
        try:
            query = """
            // Match rules and calculate complexity metrics
            MATCH (r:Rule)
            
            // Count conditions
            OPTIONAL MATCH (r)-[:HAS_CONDITION]->(c:Condition)
            WITH r, count(c) as condition_count
            
            // Count constraints
            OPTIONAL MATCH (r)-[:HAS_CONDITION]->(c2:Condition)-[:HAS_CONSTRAINT]->(con:Constraint)
            WITH r, condition_count, count(con) as constraint_count
            
            // Count actions
            OPTIONAL MATCH (r)-[:HAS_ACTION]->(a:Action)
            WITH r, condition_count, constraint_count, count(a) as action_count
            
            // Count referenced classes
            OPTIONAL MATCH (r)-[:HAS_CONDITION|HAS_ACTION]->(n)-[:REFERENCES]->(cl:Class)
            WITH r, condition_count, constraint_count, action_count, count(DISTINCT cl) as class_count
            
            // Calculate total complexity
            WITH r, 
                 condition_count, 
                 constraint_count, 
                 action_count, 
                 class_count,
                 condition_count + constraint_count + action_count + class_count as total_complexity
            
            // Filter by complexity threshold
            WHERE total_complexity >= $complexity_threshold
            
            // Return results
            RETURN r.name as name, 
                   r.package as package, 
                   r.salience as salience,
                   id(r) as id,
                   condition_count,
                   constraint_count,
                   action_count,
                   class_count,
                   total_complexity
            ORDER BY total_complexity DESC
            """
            
            parameters = {"complexity_threshold": complexity_threshold}
            
            return self.connection.execute_read_query(query, parameters)
        except Neo4jQueryError as e:
            logger.error(f"Failed to find complex rules: {e}")
            return []
            
    def find_conflicting_rules(self) -> List[Dict]:
        """
        Find rules that might conflict with each other.
        
        Rules are considered potentially conflicting if:
        1. They operate on the same fact types
        2. They have similar or overlapping conditions
        3. They have contradictory actions
        4. They have similar salience values
        
        Returns:
            A list of potentially conflicting rule pairs with conflict details.
        """
        try:
            # Find rules that operate on the same fact types with similar conditions
            query = """
            // Find pairs of rules that operate on the same fact types
            MATCH (r1:Rule)-[:HAS_CONDITION]->(c1:Condition),
                  (r2:Rule)-[:HAS_CONDITION]->(c2:Condition)
            WHERE id(r1) < id(r2)  // Avoid duplicate pairs
              AND c1.type = c2.type  // Same fact type
              
            // Check if they have similar conditions
            WITH r1, r2, c1.type as fact_type,
                 collect(DISTINCT c1.variable) as r1_vars,
                 collect(DISTINCT c2.variable) as r2_vars
                 
            // Get constraints for both rules
            OPTIONAL MATCH (r1)-[:HAS_CONDITION]->(c1:Condition)-[:HAS_CONSTRAINT]->(con1:Constraint)
            WITH r1, r2, fact_type, r1_vars, r2_vars,
                 collect(DISTINCT {field: con1.field, operator: con1.operator, value: con1.value}) as r1_constraints
                 
            OPTIONAL MATCH (r2)-[:HAS_CONDITION]->(c2:Condition)-[:HAS_CONSTRAINT]->(con2:Constraint)
            WITH r1, r2, fact_type, r1_vars, r2_vars, r1_constraints,
                 collect(DISTINCT {field: con2.field, operator: con2.operator, value: con2.value}) as r2_constraints
                 
            // Get actions for both rules
            OPTIONAL MATCH (r1)-[:HAS_ACTION]->(a1:Action)
            WITH r1, r2, fact_type, r1_vars, r2_vars, r1_constraints, r2_constraints,
                 collect(DISTINCT {type: a1.type, target: a1.target, method: a1.method}) as r1_actions
                 
            OPTIONAL MATCH (r2)-[:HAS_ACTION]->(a2:Action)
            WITH r1, r2, fact_type, r1_vars, r2_vars, r1_constraints, r2_constraints, r1_actions,
                 collect(DISTINCT {type: a2.type, target: a2.target, method: a2.method}) as r2_actions
                 
            // Calculate salience difference
            WITH r1, r2, fact_type, r1_vars, r2_vars, r1_constraints, r2_constraints, r1_actions, r2_actions,
                 CASE 
                   WHEN r1.salience IS NULL OR r2.salience IS NULL THEN 999
                   ELSE abs(r1.salience - r2.salience)
                 END as salience_diff
                 
            // Determine conflict type
            WITH r1, r2, fact_type, r1_vars, r2_vars, r1_constraints, r2_constraints, r1_actions, r2_actions, salience_diff,
                 CASE
                   // Same fact, similar constraints, different actions, close salience
                   WHEN size([c IN r1_constraints WHERE c IN r2_constraints]) > 0 AND 
                        size([a IN r1_actions WHERE NOT a IN r2_actions]) > 0 AND
                        salience_diff < 20
                   THEN "potential_action_conflict"
                   
                   // Same fact, overlapping constraints, close salience
                   WHEN size([c IN r1_constraints WHERE c.field IN [c2.field FOR c2 IN r2_constraints]]) > 0 AND
                        salience_diff < 20
                   THEN "potential_condition_overlap"
                   
                   // Same fact, contradictory constraints
                   WHEN size([c1 IN r1_constraints WHERE 
                        ANY(c2 IN r2_constraints WHERE 
                            c1.field = c2.field AND 
                            c1.operator <> c2.operator AND 
                            c1.value = c2.value)]) > 0
                   THEN "contradictory_constraints"
                   
                   // Same fact, same actions, different constraints
                   WHEN size([a IN r1_actions WHERE a IN r2_actions]) > 0 AND
                        size([c IN r1_constraints WHERE NOT c IN r2_constraints]) > 0
                   THEN "redundant_rules"
                   
                   ELSE "same_fact_type"
                 END as conflict_type
                 
            // Filter out weak conflicts
            WHERE conflict_type <> "same_fact_type" OR salience_diff < 10
                 
            // Return results
            RETURN r1.name as rule1_name, r1.package as rule1_package, r1.salience as rule1_salience,
                   r2.name as rule2_name, r2.package as rule2_package, r2.salience as rule2_salience,
                   fact_type, conflict_type, salience_diff,
                   r1_vars, r2_vars, r1_constraints, r2_constraints, r1_actions, r2_actions
            ORDER BY 
                CASE conflict_type
                    WHEN "contradictory_constraints" THEN 1
                    WHEN "potential_action_conflict" THEN 2
                    WHEN "potential_condition_overlap" THEN 3
                    WHEN "redundant_rules" THEN 4
                    ELSE 5
                END,
                salience_diff
            """
            
            results = self.connection.execute_read_query(query)
            
            # Process results to make them more readable
            processed_results = []
            for result in results:
                processed_result = {
                    "rule1": {
                        "name": result["rule1_name"],
                        "package": result["rule1_package"],
                        "salience": result["rule1_salience"]
                    },
                    "rule2": {
                        "name": result["rule2_name"],
                        "package": result["rule2_package"],
                        "salience": result["rule2_salience"]
                    },
                    "fact_type": result["fact_type"],
                    "conflict_type": result["conflict_type"],
                    "salience_difference": result["salience_diff"],
                    "details": {
                        "rule1_variables": result["r1_vars"],
                        "rule2_variables": result["r2_vars"],
                        "rule1_constraints": result["r1_constraints"],
                        "rule2_constraints": result["r2_constraints"],
                        "rule1_actions": result["r1_actions"],
                        "rule2_actions": result["r2_actions"]
                    }
                }
                processed_results.append(processed_result)
            
            return processed_results
        except Neo4jQueryError as e:
            logger.error(f"Failed to find conflicting rules: {e}")
            return []
    
    def analyze_execution_order(self, rule_names: Optional[List[str]] = None) -> List[Dict]:
        """
        Analyze the execution order of rules based on salience and dependencies.
        
        Args:
            rule_names: Optional list of rule names to analyze. If None, analyzes all rules.
            
        Returns:
            A list of rules in their likely execution order with execution path details.
        """
        try:
            # If rule names are provided, build a parameter list
            rule_names_param = ""
            parameters = {}
            
            if rule_names:
                rule_names_param = "AND r.name IN $rule_names"
                parameters["rule_names"] = rule_names
            
            # Query to analyze execution order based on salience and dependencies
            query = f"""
            // Match all rules or specific rules
            MATCH (r:Rule)
            WHERE true {rule_names_param}
            
            // Get rule dependencies through class references
            OPTIONAL MATCH (r)-[:HAS_CONDITION]->(c:Condition)-[:REFERENCES]->(cl:Class)
            OPTIONAL MATCH (r2:Rule)-[:HAS_ACTION]->(a:Action)-[:REFERENCES]->(cl)
            WHERE r <> r2
            
            // Collect dependencies
            WITH r, collect(DISTINCT r2) as dependencies
            
            // Calculate effective salience (actual salience or default to 0)
            WITH r, dependencies,
                 CASE WHEN r.salience IS NULL THEN 0 ELSE r.salience END as effective_salience
            
            // Return rules with their dependencies and salience
            RETURN r.name as name,
                   r.package as package,
                   r.salience as original_salience,
                   effective_salience,
                   [dep in dependencies | {{name: dep.name, package: dep.package}}] as depends_on,
                   size([dep in dependencies | dep]) as dependency_count,
                   CASE
                     WHEN r.salience IS NOT NULL AND r.salience > 50 THEN "high_priority"
                     WHEN size([dep in dependencies | dep]) = 0 THEN "entry_point"
                     WHEN size([dep in dependencies | dep]) > 3 THEN "aggregator"
                     ELSE "normal"
                   END as rule_type
            
            // Order by salience (highest first) and then by dependency count (lowest first)
            ORDER BY effective_salience DESC, dependency_count ASC
            """
            
            results = self.connection.execute_read_query(query, parameters)
            
            # Process results to add execution path information
            processed_results = []
            execution_path = []
            
            # First pass: collect all rules for dependency resolution
            rule_map = {f"{r['name']}:{r['package']}": r for r in results}
            
            # Second pass: build execution path considering dependencies
            for result in results:
                rule_key = f"{result['name']}:{result['package']}"
                
                # Check if all dependencies are already in the execution path
                dependencies_met = True
                missing_deps = []
                
                for dep in result["depends_on"]:
                    dep_key = f"{dep['name']}:{dep['package']}"
                    if dep_key not in execution_path and dep_key in rule_map:
                        dependencies_met = False
                        missing_deps.append(dep)
                
                # Add execution path information
                result["execution_status"] = "ready" if dependencies_met else "waiting_for_dependencies"
                result["missing_dependencies"] = missing_deps if not dependencies_met else []
                
                # Add to processed results
                processed_results.append(result)
                
                # Add to execution path if dependencies are met
                if dependencies_met:
                    execution_path.append(rule_key)
            
            return processed_results
        except Neo4jQueryError as e:
            logger.error(f"Failed to analyze execution order: {e}")
            return []
    
    def find_rule_patterns(self) -> Dict[str, List[Dict]]:
        """
        Identify common patterns and anti-patterns in rules.
        
        Patterns detected:
        1. Rules with high salience (priority rules)
        2. Rules with no conditions (always fire)
        3. Rules with no actions (no effect)
        4. Rules with many conditions but few constraints (broad rules)
        5. Rules with few conditions but many constraints (specific rules)
        
        Returns:
            A dictionary mapping pattern types to lists of rules matching those patterns.
        """
        try:
            # Find rules with high salience
            high_salience_query = """
            MATCH (r:Rule)
            WHERE r.salience IS NOT NULL AND r.salience > 50
            RETURN r.name as name, r.package as package, r.salience as salience,
                   id(r) as id, 'high_salience' as pattern
            ORDER BY r.salience DESC
            LIMIT 10
            """
            
            # Find rules with no conditions
            no_conditions_query = """
            MATCH (r:Rule)
            WHERE NOT EXISTS {
                MATCH (r)-[:HAS_CONDITION]->(:Condition)
            }
            RETURN r.name as name, r.package as package, r.salience as salience,
                   id(r) as id, 'no_conditions' as pattern
            """
            
            # Find rules with no actions
            no_actions_query = """
            MATCH (r:Rule)
            WHERE NOT EXISTS {
                MATCH (r)-[:HAS_ACTION]->(:Action)
            }
            RETURN r.name as name, r.package as package, r.salience as salience,
                   id(r) as id, 'no_actions' as pattern
            """
            
            # Find broad rules (many conditions, few constraints)
            broad_rules_query = """
            MATCH (r:Rule)-[:HAS_CONDITION]->(c:Condition)
            WITH r, count(c) as condition_count
            WHERE condition_count > 2
            OPTIONAL MATCH (r)-[:HAS_CONDITION]->(c2:Condition)-[:HAS_CONSTRAINT]->(con:Constraint)
            WITH r, condition_count, count(con) as constraint_count
            WHERE constraint_count < condition_count
            RETURN r.name as name, r.package as package, r.salience as salience,
                   id(r) as id, 'broad_rule' as pattern,
                   condition_count, constraint_count
            """
            
            # Find specific rules (few conditions, many constraints)
            specific_rules_query = """
            MATCH (r:Rule)-[:HAS_CONDITION]->(c:Condition)
            WITH r, count(c) as condition_count
            WHERE condition_count <= 2
            OPTIONAL MATCH (r)-[:HAS_CONDITION]->(c2:Condition)-[:HAS_CONSTRAINT]->(con:Constraint)
            WITH r, condition_count, count(con) as constraint_count
            WHERE constraint_count > 3
            RETURN r.name as name, r.package as package, r.salience as salience,
                   id(r) as id, 'specific_rule' as pattern,
                   condition_count, constraint_count
            """
            
            # Execute all queries
            high_salience_rules = self.connection.execute_read_query(high_salience_query)
            no_conditions_rules = self.connection.execute_read_query(no_conditions_query)
            no_actions_rules = self.connection.execute_read_query(no_actions_query)
            broad_rules = self.connection.execute_read_query(broad_rules_query)
            specific_rules = self.connection.execute_read_query(specific_rules_query)
            
            # Combine results
            return {
                "high_salience_rules": high_salience_rules,
                "no_conditions_rules": no_conditions_rules,
                "no_actions_rules": no_actions_rules,
                "broad_rules": broad_rules,
                "specific_rules": specific_rules
            }
        except Neo4jQueryError as e:
            logger.error(f"Failed to find rule patterns: {e}")
            return {}