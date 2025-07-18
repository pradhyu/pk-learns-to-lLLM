"""
Query processing pipeline for the Drools Graph RAG system.

This module provides classes and functions for processing natural language queries,
extracting intent, and translating them to graph operations.
"""
import logging
import re
from typing import Dict, List, Optional, Any, Tuple

from sentence_transformers import SentenceTransformer
import numpy as np

from drools_graph_rag.config import config
from drools_graph_rag.query_engine.query_engine import GraphQueryEngine

# Configure logging
logger = logging.getLogger(__name__)


class QueryIntent:
    """
    Class representing the intent of a natural language query.
    """
    
    # Intent types
    FIND_RULE = "find_rule"
    EXPLAIN_RULE = "explain_rule"
    FIND_DEPENDENCIES = "find_dependencies"
    FIND_CONFLICTS = "find_conflicts"
    EXECUTION_ORDER = "execution_order"
    FIND_PATTERNS = "find_patterns"
    UNKNOWN = "unknown"
    
    def __init__(
        self, 
        intent_type: str, 
        entities: Dict[str, Any] = None, 
        confidence: float = 0.0
    ) -> None:
        """
        Initialize a query intent.
        
        Args:
            intent_type: The type of intent.
            entities: Entities extracted from the query.
            confidence: Confidence score for the intent classification.
        """
        self.intent_type = intent_type
        self.entities = entities or {}
        self.confidence = confidence
    
    def __str__(self) -> str:
        """
        String representation of the intent.
        
        Returns:
            A string representation of the intent.
        """
        return f"Intent: {self.intent_type}, Entities: {self.entities}, Confidence: {self.confidence:.2f}"


class QueryProcessor:
    """
    Class for processing natural language queries.
    """
    
    # Intent patterns for rule-based matching
    INTENT_PATTERNS = {
        QueryIntent.FIND_RULE: [
            r"(?:find|search for|get|show|list) (?:rule|rules) (?:with name|named|called) ['\"](.*?)['\"]",
            r"(?:find|search for|get|show|list) (?:rule|rules) (?:about|related to|concerning) (.*)",
            r"(?:find|search for|get|show|list) (?:rule|rules) (?:that|which) (.*)",
        ],
        QueryIntent.EXPLAIN_RULE: [
            r"(?:explain|describe|tell me about) (?:rule|the rule) ['\"](.*?)['\"]",
            r"(?:explain|describe|tell me about) (?:rule|the rule) (?:named|called) ['\"](.*?)['\"]",
            r"(?:what does|how does) (?:rule|the rule) ['\"](.*?)['\"] (?:do|work)",
        ],
        QueryIntent.FIND_DEPENDENCIES: [
            r"(?:find|show|list|what are) (?:the |)(?:dependencies|dependent rules) (?:of|for) (?:rule|the rule) ['\"](.*?)['\"]",
            r"(?:what rules|which rules) (?:depend on|are related to) (?:rule|the rule) ['\"](.*?)['\"]",
            r"(?:dependency|dependencies) (?:graph|tree|analysis) (?:for|of) ['\"](.*?)['\"]",
        ],
        QueryIntent.FIND_CONFLICTS: [
            r"(?:find|show|list|are there) (?:any |)(?:conflicts|conflicting rules|rule conflicts)",
            r"(?:find|show|list) (?:conflicts|conflicting rules) (?:with|related to) ['\"](.*?)['\"]",
            r"(?:does|do) (?:rule|rules) ['\"](.*?)['\"] (?:conflict with|contradict) (?:any other|other) rules",
        ],
        QueryIntent.EXECUTION_ORDER: [
            r"(?:what is|show|list) (?:the |)(?:execution order|execution sequence|firing sequence) (?:of|for) (?:rules|the rules)",
            r"(?:in what order|how) (?:do|would|will) (?:rules|the rules) (?:execute|fire|run)",
            r"(?:execution|firing) (?:order|sequence) (?:for|of) ['\"](.*?)['\"]",
        ],
        QueryIntent.FIND_PATTERNS: [
            r"(?:find|show|list|are there) (?:any |)(?:patterns|rule patterns|common patterns)",
            r"(?:find|show|list) (?:complex|unused|circular|redundant) rules",
            r"(?:analyze|analysis of) (?:rule|rules) (?:quality|structure|complexity)",
        ],
    }
    
    def __init__(self, embedding_model: Optional[SentenceTransformer] = None) -> None:
        """
        Initialize the query processor.
        
        Args:
            embedding_model: Optional embedding model for intent classification.
                            If None, a new model will be loaded.
        """
        self.embedding_model = embedding_model or SentenceTransformer(
            config.embedding.model_name,
            device=config.embedding.device
        )
        
        # Example queries for each intent type (used for embedding-based classification)
        self.intent_examples = {
            QueryIntent.FIND_RULE: [
                "Find rule named 'Validate Customer'",
                "Show me rules about order processing",
                "List rules that check customer age",
                "Get rules related to validation",
                "Search for rules with name containing 'discount'",
            ],
            QueryIntent.EXPLAIN_RULE: [
                "Explain rule 'Calculate Discount'",
                "Describe the rule named 'Validate Order'",
                "Tell me about rule 'Check Inventory'",
                "What does rule 'Apply Tax' do?",
                "How does the rule 'Process Payment' work?",
            ],
            QueryIntent.FIND_DEPENDENCIES: [
                "Find dependencies of rule 'Validate Customer'",
                "What rules depend on 'Calculate Total'?",
                "Show dependency graph for 'Process Order'",
                "List dependent rules for 'Apply Discount'",
                "Which rules are related to 'Check Inventory'?",
            ],
            QueryIntent.FIND_CONFLICTS: [
                "Find conflicting rules",
                "Show conflicts with rule 'Apply Discount'",
                "Are there any rule conflicts?",
                "List rules that conflict with 'Validate Customer'",
                "Does rule 'Apply Tax' conflict with any other rules?",
            ],
            QueryIntent.EXECUTION_ORDER: [
                "What is the execution order of rules?",
                "Show firing sequence for rules",
                "In what order do the rules execute?",
                "Execution order for 'Process Order'",
                "How would rules related to customer validation run?",
            ],
            QueryIntent.FIND_PATTERNS: [
                "Find rule patterns",
                "Show complex rules",
                "List unused rules",
                "Are there any circular dependencies?",
                "Analyze rule quality",
            ],
        }
        
        # Pre-compute embeddings for example queries
        self.intent_embeddings = {}
        for intent_type, examples in self.intent_examples.items():
            embeddings = self.embedding_model.encode(examples)
            self.intent_embeddings[intent_type] = embeddings
    
    def process_query(self, query: str) -> QueryIntent:
        """
        Process a natural language query and extract intent.
        
        Args:
            query: The natural language query.
            
        Returns:
            A QueryIntent object with the extracted intent and entities.
        """
        # Try rule-based intent extraction first
        intent = self._extract_intent_rule_based(query)
        
        # If rule-based extraction fails or has low confidence, try embedding-based
        if intent.intent_type == QueryIntent.UNKNOWN or intent.confidence < 0.7:
            embedding_intent = self._extract_intent_embedding_based(query)
            
            # Use embedding-based intent if it has higher confidence
            if embedding_intent.confidence > intent.confidence:
                intent = embedding_intent
                
                # Try to extract entities for the new intent
                entities = self._extract_entities(query, intent.intent_type)
                if entities:
                    intent.entities.update(entities)
        
        logger.debug(f"Extracted intent: {intent}")
        return intent
    
    def _extract_intent_rule_based(self, query: str) -> QueryIntent:
        """
        Extract intent using rule-based pattern matching.
        
        Args:
            query: The natural language query.
            
        Returns:
            A QueryIntent object with the extracted intent and entities.
        """
        # Normalize query
        normalized_query = query.lower().strip()
        
        for intent_type, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, normalized_query, re.IGNORECASE)
                if match:
                    entities = {}
                    
                    # Extract entities based on the intent type
                    if intent_type in [QueryIntent.FIND_RULE, QueryIntent.EXPLAIN_RULE, 
                                      QueryIntent.FIND_DEPENDENCIES, QueryIntent.EXECUTION_ORDER]:
                        if match.groups():
                            entities["rule_name"] = match.group(1).strip()
                    
                    elif intent_type == QueryIntent.FIND_CONFLICTS:
                        if match.groups():
                            entities["rule_name"] = match.group(1).strip()
                    
                    return QueryIntent(intent_type, entities, confidence=0.9)
        
        # If no pattern matches, try to extract entities anyway
        for intent_type in self.INTENT_PATTERNS.keys():
            entities = self._extract_entities(normalized_query, intent_type)
            if entities:
                return QueryIntent(intent_type, entities, confidence=0.6)
        
        return QueryIntent(QueryIntent.UNKNOWN, confidence=0.0)
    
    def _extract_intent_embedding_based(self, query: str) -> QueryIntent:
        """
        Extract intent using embedding-based similarity.
        
        Args:
            query: The natural language query.
            
        Returns:
            A QueryIntent object with the extracted intent.
        """
        # Encode the query
        query_embedding = self.embedding_model.encode([query])[0]
        
        best_intent = QueryIntent.UNKNOWN
        best_score = -1.0
        
        # Compare with example embeddings for each intent
        for intent_type, embeddings in self.intent_embeddings.items():
            # Calculate cosine similarity
            similarities = np.dot(embeddings, query_embedding) / (
                np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding)
            )
            
            # Get the highest similarity score
            max_similarity = np.max(similarities)
            
            if max_similarity > best_score:
                best_score = max_similarity
                best_intent = intent_type
        
        # Extract entities for the best intent
        entities = self._extract_entities(query, best_intent)
        
        return QueryIntent(best_intent, entities, confidence=best_score)
    
    def _extract_entities(self, query: str, intent_type: str) -> Dict[str, Any]:
        """
        Extract entities from a query based on the intent type.
        
        Args:
            query: The natural language query.
            intent_type: The type of intent.
            
        Returns:
            A dictionary of extracted entities.
        """
        entities = {}
        
        # Extract rule names
        if intent_type in [QueryIntent.FIND_RULE, QueryIntent.EXPLAIN_RULE, 
                          QueryIntent.FIND_DEPENDENCIES, QueryIntent.FIND_CONFLICTS,
                          QueryIntent.EXECUTION_ORDER]:
            # Look for quoted rule names
            rule_name_match = re.search(r"['\"]([^'\"]+)['\"]", query)
            if rule_name_match:
                entities["rule_name"] = rule_name_match.group(1).strip()
            else:
                # Look for rule names after specific keywords
                keywords = ["rule", "named", "called", "about", "for"]
                for keyword in keywords:
                    pattern = f"{keyword} ([\\w\\s]+?)(?:\\s|$)"
                    match = re.search(pattern, query, re.IGNORECASE)
                    if match:
                        entities["rule_name"] = match.group(1).strip()
                        break
        
        # Extract class names
        if intent_type == QueryIntent.FIND_RULE:
            class_match = re.search(r"class[es]* (?:named |called |)['\"]*([\\w\\.]+)['\"]*", query, re.IGNORECASE)
            if class_match:
                entities["class_name"] = class_match.group(1).strip()
        
        # Extract complexity threshold
        if intent_type == QueryIntent.FIND_PATTERNS:
            threshold_match = re.search(r"complexity (?:threshold |)(?:of |)([0-9]+)", query, re.IGNORECASE)
            if threshold_match:
                entities["complexity_threshold"] = int(threshold_match.group(1))
        
        return entities


class QueryTranslator:
    """
    Class for translating query intents to graph operations.
    """
    
    def __init__(self, query_engine: GraphQueryEngine) -> None:
        """
        Initialize the query translator.
        
        Args:
            query_engine: The graph query engine to use for executing queries.
        """
        self.query_engine = query_engine
    
    def translate_intent(self, intent: QueryIntent) -> Dict[str, Any]:
        """
        Translate a query intent to graph operations and execute them.
        
        Args:
            intent: The query intent.
            
        Returns:
            A dictionary with the query results.
        """
        if intent.intent_type == QueryIntent.UNKNOWN:
            return {"error": "Could not understand the query intent"}
        
        try:
            # Dispatch to the appropriate handler based on intent type
            if intent.intent_type == QueryIntent.FIND_RULE:
                return self._handle_find_rule(intent)
            elif intent.intent_type == QueryIntent.EXPLAIN_RULE:
                return self._handle_explain_rule(intent)
            elif intent.intent_type == QueryIntent.FIND_DEPENDENCIES:
                return self._handle_find_dependencies(intent)
            elif intent.intent_type == QueryIntent.FIND_CONFLICTS:
                return self._handle_find_conflicts(intent)
            elif intent.intent_type == QueryIntent.EXECUTION_ORDER:
                return self._handle_execution_order(intent)
            elif intent.intent_type == QueryIntent.FIND_PATTERNS:
                return self._handle_find_patterns(intent)
            else:
                return {"error": f"Unsupported intent type: {intent.intent_type}"}
        except Exception as e:
            logger.error(f"Error translating intent: {e}")
            return {"error": f"Error processing query: {str(e)}"}
    
    def _handle_find_rule(self, intent: QueryIntent) -> Dict[str, Any]:
        """
        Handle FIND_RULE intent.
        
        Args:
            intent: The query intent.
            
        Returns:
            A dictionary with the query results.
        """
        results = {}
        
        # Check if we have a rule name
        if "rule_name" in intent.entities:
            rule_name = intent.entities["rule_name"]
            # Use regex pattern to find rules with similar names
            rules = self.query_engine.find_rules_by_name(f".*{rule_name}.*")
            results["rules_by_name"] = rules
        
        # Check if we have a class name
        if "class_name" in intent.entities:
            class_name = intent.entities["class_name"]
            rules = self.query_engine.find_rules_by_class_reference(class_name)
            results["rules_by_class"] = rules
        
        # If no specific entities, return all rules
        if not intent.entities:
            results["all_rules"] = self.query_engine.get_all_rules()
        
        return {
            "intent": intent.intent_type,
            "results": results
        }
    
    def _handle_explain_rule(self, intent: QueryIntent) -> Dict[str, Any]:
        """
        Handle EXPLAIN_RULE intent.
        
        Args:
            intent: The query intent.
            
        Returns:
            A dictionary with the query results.
        """
        results = {}
        
        # Check if we have a rule name
        if "rule_name" in intent.entities:
            rule_name = intent.entities["rule_name"]
            
            # First try exact match
            rule = self.query_engine.find_rule_by_exact_name(rule_name)
            
            # If not found, try fuzzy match
            if not rule:
                rules = self.query_engine.find_rules_by_name(f".*{rule_name}.*")
                if rules:
                    rule = rules[0]  # Take the first match
            
            if rule:
                # Get rule details
                rule_details = self.query_engine.get_rule_details(rule["id"])
                results["rule_details"] = rule_details
                
                # Get rule dependencies
                rule_dependencies = self.query_engine.find_rule_dependencies(rule["name"], rule.get("package"))
                results["rule_dependencies"] = rule_dependencies
            else:
                results["error"] = f"Rule '{rule_name}' not found"
        else:
            results["error"] = "No rule name provided"
        
        return {
            "intent": intent.intent_type,
            "results": results
        }
    
    def _handle_find_dependencies(self, intent: QueryIntent) -> Dict[str, Any]:
        """
        Handle FIND_DEPENDENCIES intent.
        
        Args:
            intent: The query intent.
            
        Returns:
            A dictionary with the query results.
        """
        results = {}
        
        # Check if we have a rule name
        if "rule_name" in intent.entities:
            rule_name = intent.entities["rule_name"]
            
            # First try exact match
            rule = self.query_engine.find_rule_by_exact_name(rule_name)
            
            # If not found, try fuzzy match
            if not rule:
                rules = self.query_engine.find_rules_by_name(f".*{rule_name}.*")
                if rules:
                    rule = rules[0]  # Take the first match
            
            if rule:
                # Get rule dependencies
                rule_dependencies = self.query_engine.find_rule_dependencies(rule["name"], rule.get("package"))
                results["rule_dependencies"] = rule_dependencies
            else:
                results["error"] = f"Rule '{rule_name}' not found"
        else:
            # If no rule name, find circular dependencies
            circular_deps = self.query_engine.find_circular_dependencies()
            results["circular_dependencies"] = circular_deps
        
        return {
            "intent": intent.intent_type,
            "results": results
        }
    
    def _handle_find_conflicts(self, intent: QueryIntent) -> Dict[str, Any]:
        """
        Handle FIND_CONFLICTS intent.
        
        Args:
            intent: The query intent.
            
        Returns:
            A dictionary with the query results.
        """
        results = {}
        
        # Get all conflicting rules
        conflicting_rules = self.query_engine.find_conflicting_rules()
        
        # Filter by rule name if provided
        if "rule_name" in intent.entities:
            rule_name = intent.entities["rule_name"]
            filtered_conflicts = []
            
            for conflict in conflicting_rules:
                if (rule_name.lower() in conflict["rule1"]["name"].lower() or 
                    rule_name.lower() in conflict["rule2"]["name"].lower()):
                    filtered_conflicts.append(conflict)
            
            results["conflicting_rules"] = filtered_conflicts
        else:
            results["conflicting_rules"] = conflicting_rules
        
        return {
            "intent": intent.intent_type,
            "results": results
        }
    
    def _handle_execution_order(self, intent: QueryIntent) -> Dict[str, Any]:
        """
        Handle EXECUTION_ORDER intent.
        
        Args:
            intent: The query intent.
            
        Returns:
            A dictionary with the query results.
        """
        results = {}
        
        # Check if we have a rule name
        if "rule_name" in intent.entities:
            rule_name = intent.entities["rule_name"]
            
            # Find rules matching the name
            rules = self.query_engine.find_rules_by_name(f".*{rule_name}.*")
            if rules:
                rule_names = [rule["name"] for rule in rules]
                execution_order = self.query_engine.analyze_execution_order(rule_names)
                results["execution_order"] = execution_order
            else:
                results["error"] = f"No rules found matching '{rule_name}'"
        else:
            # Get execution order for all rules
            execution_order = self.query_engine.analyze_execution_order()
            results["execution_order"] = execution_order
        
        return {
            "intent": intent.intent_type,
            "results": results
        }
    
    def _handle_find_patterns(self, intent: QueryIntent) -> Dict[str, Any]:
        """
        Handle FIND_PATTERNS intent.
        
        Args:
            intent: The query intent.
            
        Returns:
            A dictionary with the query results.
        """
        results = {}
        
        # Check for specific pattern types in the query
        query_lower = str(intent.entities).lower()
        
        # Get unused rules
        if "unused" in query_lower:
            unused_rules = self.query_engine.find_unused_rules()
            results["unused_rules"] = unused_rules
        
        # Get circular dependencies
        if "circular" in query_lower:
            circular_deps = self.query_engine.find_circular_dependencies()
            results["circular_dependencies"] = circular_deps
        
        # Get complex rules
        if "complex" in query_lower:
            complexity_threshold = intent.entities.get("complexity_threshold", 5)
            complex_rules = self.query_engine.find_complex_rules(complexity_threshold)
            results["complex_rules"] = complex_rules
        
        # Get conflicting rules
        if "conflict" in query_lower:
            conflicting_rules = self.query_engine.find_conflicting_rules()
            results["conflicting_rules"] = conflicting_rules
        
        # If no specific pattern type, get all patterns
        if not results:
            results["unused_rules"] = self.query_engine.find_unused_rules()
            results["circular_dependencies"] = self.query_engine.find_circular_dependencies()
            results["complex_rules"] = self.query_engine.find_complex_rules(5)
            results["conflicting_rules"] = self.query_engine.find_conflicting_rules()
        
        return {
            "intent": intent.intent_type,
            "results": results
        }