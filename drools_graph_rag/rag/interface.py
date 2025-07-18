"""
RAG interface for the Drools Graph RAG system.

This module provides the main interface for the RAG system, combining the query processor,
query translator, and response generator components.
"""
import logging
from typing import Dict, List, Any, Optional, Union

from drools_graph_rag.config import config
from drools_graph_rag.graph.connection import Neo4jConnection
from drools_graph_rag.query_engine.query_engine import GraphQueryEngine
from drools_graph_rag.rag.query_processor import QueryProcessor, QueryTranslator
from drools_graph_rag.rag.response_generator import ResponseGenerator, RuleExplainer

# Configure logging
logger = logging.getLogger(__name__)


class RAGInterface:
    """
    Main interface for the Drools Graph RAG system.
    """
    
    def __init__(
        self,
        neo4j_connection: Optional[Neo4jConnection] = None,
        query_processor: Optional[QueryProcessor] = None,
        response_generator: Optional[ResponseGenerator] = None
    ) -> None:
        """
        Initialize the RAG interface.
        
        Args:
            neo4j_connection: Optional Neo4j connection. If None, a new connection will be created.
            query_processor: Optional query processor. If None, a new processor will be created.
            response_generator: Optional response generator. If None, a new generator will be created.
        """
        # Create Neo4j connection if not provided
        if neo4j_connection is None:
            neo4j_connection = Neo4jConnection(
                uri=config.neo4j.uri,
                username=config.neo4j.username,
                password=config.neo4j.password,
                database=config.neo4j.database
            )
        self.neo4j_connection = neo4j_connection
        
        # Create query engine
        self.query_engine = GraphQueryEngine(self.neo4j_connection)
        
        # Create query processor if not provided
        if query_processor is None:
            query_processor = QueryProcessor()
        self.query_processor = query_processor
        
        # Create query translator
        self.query_translator = QueryTranslator(self.query_engine)
        
        # Create response generator if not provided
        if response_generator is None:
            response_generator = ResponseGenerator()
        self.response_generator = response_generator
        
        # Create rule explainer
        self.rule_explainer = RuleExplainer(self.response_generator)
    
    def process_query(self, query: str) -> str:
        """
        Process a natural language query and return a response.
        
        Args:
            query: The natural language query.
            
        Returns:
            A natural language response.
        """
        try:
            # Extract intent from the query
            intent = self.query_processor.process_query(query)
            logger.info(f"Extracted intent: {intent.intent_type} with confidence {intent.confidence:.2f}")
            
            # Translate intent to graph operations
            query_results = self.query_translator.translate_intent(intent)
            logger.info(f"Translated intent to query results")
            
            # Generate response
            response = self.response_generator.generate_response(query, query_results)
            logger.info(f"Generated response")
            
            return response
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return f"Error processing query: {str(e)}"
    
    def explain_rule_context(self, rule_name: str) -> str:
        """
        Provide contextual explanation of a rule including when it fires and what it affects.
        
        Args:
            rule_name: The name of the rule to explain.
            
        Returns:
            A natural language explanation of the rule context.
        """
        try:
            # Find the rule
            rule = self.query_engine.find_rule_by_exact_name(rule_name)
            
            if not rule:
                # Try fuzzy match
                rules = self.query_engine.find_rules_by_name(f".*{rule_name}.*")
                if rules:
                    rule = rules[0]  # Take the first match
            
            if not rule:
                return f"Rule '{rule_name}' not found"
            
            # Get rule details
            rule_details = self.query_engine.get_rule_details(rule["id"])
            
            # Get rule dependencies
            rule_dependencies = self.query_engine.find_rule_dependencies(rule["name"], rule.get("package"))
            
            # Combine results
            query_results = {
                "rule_details": rule_details,
                "rule_dependencies": rule_dependencies
            }
            
            # Generate explanation
            return self.rule_explainer.explain_rule_context(rule_name, query_results)
        except Exception as e:
            logger.error(f"Error explaining rule context: {e}")
            return f"Error explaining rule context: {str(e)}"
    
    def explain_rule_conflicts(self, rule_names: Union[str, List[str]]) -> str:
        """
        Explain conflicts between rules and their resolution.
        
        Args:
            rule_names: The name(s) of the rule(s) to explain conflicts for.
                       Can be a single rule name or a list of rule names.
            
        Returns:
            A natural language explanation of the rule conflicts.
        """
        try:
            # Convert single rule name to list
            if isinstance(rule_names, str):
                rule_names = [rule_names]
            
            # Get all conflicting rules
            all_conflicts = self.query_engine.find_conflicting_rules()
            
            # Filter conflicts involving the specified rules
            if rule_names:
                filtered_conflicts = []
                for conflict in all_conflicts:
                    rule1_name = conflict["rule1"]["name"]
                    rule2_name = conflict["rule2"]["name"]
                    if any(name.lower() in rule1_name.lower() or name.lower() in rule2_name.lower() for name in rule_names):
                        filtered_conflicts.append(conflict)
                
                conflicts = filtered_conflicts
            else:
                conflicts = all_conflicts
            
            # Combine results
            query_results = {
                "conflicting_rules": conflicts
            }
            
            # Generate explanation
            return self.rule_explainer.explain_rule_conflicts(rule_names, query_results)
        except Exception as e:
            logger.error(f"Error explaining rule conflicts: {e}")
            return f"Error explaining rule conflicts: {str(e)}"
    
    def explain_execution_order(self, rule_names: Optional[Union[str, List[str]]] = None) -> str:
        """
        Explain the execution order of rules based on salience and dependencies.
        
        Args:
            rule_names: Optional name(s) of the rule(s) to explain execution order for.
                       Can be a single rule name, a list of rule names, or None for all rules.
            
        Returns:
            A natural language explanation of the rule execution order.
        """
        try:
            # Convert single rule name to list
            if isinstance(rule_names, str):
                rule_names_list = [rule_names]
            elif rule_names is None:
                rule_names_list = []
            else:
                rule_names_list = rule_names
            
            # Find rules matching the names
            matched_rule_names = []
            if rule_names_list:
                for name in rule_names_list:
                    # Try exact match
                    rule = self.query_engine.find_rule_by_exact_name(name)
                    if rule:
                        matched_rule_names.append(rule["name"])
                    else:
                        # Try fuzzy match
                        rules = self.query_engine.find_rules_by_name(f".*{name}.*")
                        if rules:
                            matched_rule_names.extend([r["name"] for r in rules])
            
            # Get execution order
            execution_order = self.query_engine.analyze_execution_order(matched_rule_names if matched_rule_names else None)
            
            # Combine results
            query_results = {
                "execution_order": execution_order
            }
            
            # Generate explanation
            return self.rule_explainer.explain_execution_order(rule_names_list, query_results)
        except Exception as e:
            logger.error(f"Error explaining execution order: {e}")
            return f"Error explaining execution order: {str(e)}"