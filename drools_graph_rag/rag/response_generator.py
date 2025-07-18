"""
Response generator for the Drools Graph RAG system.

This module provides classes and functions for generating natural language responses
based on graph query results.
"""
import logging
from typing import Dict, List, Any, Optional

from drools_graph_rag.config import config
from drools_graph_rag.rag.query_processor import QueryIntent

# Configure logging
logger = logging.getLogger(__name__)

# Import LLM integration conditionally to handle missing dependencies gracefully
try:
    from langchain.llms import OpenAI
    from langchain.chat_models import ChatOpenAI
    from langchain.prompts import PromptTemplate
    from langchain.chains import LLMChain
    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.warning("LangChain not available. Using template-based responses.")
    LANGCHAIN_AVAILABLE = False


class ResponseGenerator:
    """
    Class for generating natural language responses from query results.
    """
    
    def __init__(self) -> None:
        """
        Initialize the response generator.
        """
        self.llm = None
        
        # Initialize LLM if available and API key is set
        if LANGCHAIN_AVAILABLE and config.llm.api_key:
            try:
                self.llm = ChatOpenAI(
                    model_name=config.llm.model_name,
                    temperature=config.llm.temperature,
                    max_tokens=config.llm.max_tokens,
                    openai_api_key=config.llm.api_key
                )
                logger.info(f"Initialized LLM: {config.llm.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM: {e}")
    
    def generate_response(self, query: str, query_results: Dict[str, Any]) -> str:
        """
        Generate a natural language response based on query results.
        
        Args:
            query: The original natural language query.
            query_results: The results from the query engine.
            
        Returns:
            A natural language response.
        """
        intent = query_results.get("intent")
        results = query_results.get("results", {})
        
        # Check for errors
        if "error" in query_results:
            return f"Error: {query_results['error']}"
        
        if "error" in results:
            return f"Error: {results['error']}"
        
        # Use LLM if available
        if self.llm:
            return self._generate_llm_response(query, intent, results)
        else:
            # Fall back to template-based responses
            return self._generate_template_response(intent, results)
    
    def _generate_llm_response(self, query: str, intent: str, results: Dict[str, Any]) -> str:
        """
        Generate a response using a language model.
        
        Args:
            query: The original natural language query.
            intent: The query intent.
            results: The query results.
            
        Returns:
            A natural language response.
        """
        try:
            # Create a prompt based on the intent and results
            prompt_template = self._get_prompt_template(intent)
            
            # Format the results as a string
            results_str = self._format_results_for_llm(results)
            
            # Create the prompt
            prompt = PromptTemplate(
                input_variables=["query", "results"],
                template=prompt_template
            )
            
            # Create the chain
            chain = LLMChain(llm=self.llm, prompt=prompt)
            
            # Run the chain
            response = chain.run(query=query, results=results_str)
            
            return response.strip()
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            # Fall back to template-based response
            return self._generate_template_response(intent, results)
    
    def _get_prompt_template(self, intent: str) -> str:
        """
        Get a prompt template based on the intent.
        
        Args:
            intent: The query intent.
            
        Returns:
            A prompt template string.
        """
        if intent == QueryIntent.FIND_RULE:
            return """
            You are an assistant for a Drools rule engine. The user has asked: "{query}"
            
            Based on the query, I searched for rules and found the following results:
            
            {results}
            
            Please provide a clear, concise response that answers the user's question about finding rules.
            Focus on the most relevant information and explain any technical terms if necessary.
            If multiple rules were found, summarize them and highlight any patterns or relationships.
            """
        
        elif intent == QueryIntent.EXPLAIN_RULE:
            return """
            You are an assistant for a Drools rule engine. The user has asked: "{query}"
            
            Based on the query, I retrieved the following information about the rule:
            
            {results}
            
            Please provide a clear, detailed explanation of this rule, including:
            1. What the rule does (its purpose)
            2. When it fires (its conditions)
            3. What actions it takes
            4. How it relates to other rules (dependencies)
            
            Use a conversational tone and explain any technical terms if necessary.
            """
        
        elif intent == QueryIntent.FIND_DEPENDENCIES:
            return """
            You are an assistant for a Drools rule engine. The user has asked: "{query}"
            
            Based on the query, I found the following dependency information:
            
            {results}
            
            Please provide a clear explanation of these dependencies, including:
            1. What rules depend on the target rule
            2. What rules the target rule depends on
            3. Any parent-child relationships (extends)
            4. Any circular dependencies if present
            
            Use a conversational tone and explain the implications of these dependencies.
            """
        
        elif intent == QueryIntent.FIND_CONFLICTS:
            return """
            You are an assistant for a Drools rule engine. The user has asked: "{query}"
            
            Based on the query, I found the following potential conflicts between rules:
            
            {results}
            
            Please provide a clear explanation of these conflicts, including:
            1. Which rules are in conflict
            2. The nature of each conflict (e.g., contradictory conditions, overlapping actions)
            3. How these conflicts might affect rule execution
            4. Suggestions for resolving these conflicts
            
            Use a conversational tone and explain the implications of these conflicts.
            """
        
        elif intent == QueryIntent.EXECUTION_ORDER:
            return """
            You are an assistant for a Drools rule engine. The user has asked: "{query}"
            
            Based on the query, I analyzed the execution order of rules and found:
            
            {results}
            
            Please provide a clear explanation of the execution order, including:
            1. The sequence in which rules are likely to fire
            2. What factors determine this order (salience, dependencies)
            3. Any potential issues with the execution order
            
            Use a conversational tone and explain how the Drools rule engine determines execution order.
            """
        
        elif intent == QueryIntent.FIND_PATTERNS:
            return """
            You are an assistant for a Drools rule engine. The user has asked: "{query}"
            
            Based on the query, I analyzed the rules and found the following patterns:
            
            {results}
            
            Please provide a clear summary of these patterns, including:
            1. Unused rules and why they might be unused
            2. Circular dependencies and their implications
            3. Complex rules that might benefit from refactoring
            4. Conflicting rules and potential issues they might cause
            
            Use a conversational tone and provide suggestions for improving the rule base.
            """
        
        else:
            return """
            You are an assistant for a Drools rule engine. The user has asked: "{query}"
            
            Based on the query, I found the following information:
            
            {results}
            
            Please provide a clear, helpful response that addresses the user's question.
            Use a conversational tone and explain any technical terms if necessary.
            """
    
    def _format_results_for_llm(self, results: Dict[str, Any]) -> str:
        """
        Format query results as a string for the LLM.
        
        Args:
            results: The query results.
            
        Returns:
            A formatted string representation of the results.
        """
        formatted_results = []
        
        # Format rules by name
        if "rules_by_name" in results:
            rules = results["rules_by_name"]
            if rules:
                formatted_results.append(f"Rules found by name ({len(rules)}):")
                for rule in rules:
                    salience = f", Salience: {rule['salience']}" if rule.get('salience') is not None else ""
                    formatted_results.append(f"- {rule['name']} (Package: {rule['package']}{salience})")
            else:
                formatted_results.append("No rules found by name.")
        
        # Format rules by class
        if "rules_by_class" in results:
            rules = results["rules_by_class"]
            if rules:
                formatted_results.append(f"Rules referencing the specified class ({len(rules)}):")
                for rule in rules:
                    salience = f", Salience: {rule['salience']}" if rule.get('salience') is not None else ""
                    formatted_results.append(f"- {rule['name']} (Package: {rule['package']}{salience})")
            else:
                formatted_results.append("No rules found referencing the specified class.")
        
        # Format all rules
        if "all_rules" in results:
            rules = results["all_rules"]
            if rules:
                formatted_results.append(f"All rules ({len(rules)}):")
                for rule in rules[:10]:  # Limit to 10 rules to avoid overwhelming the LLM
                    salience = f", Salience: {rule['salience']}" if rule.get('salience') is not None else ""
                    formatted_results.append(f"- {rule['name']} (Package: {rule['package']}{salience})")
                if len(rules) > 10:
                    formatted_results.append(f"... and {len(rules) - 10} more rules.")
            else:
                formatted_results.append("No rules found in the system.")
        
        # Format rule details
        if "rule_details" in results:
            rule = results["rule_details"]
            if rule:
                formatted_results.append(f"Rule details for '{rule['name']}':")
                formatted_results.append(f"Package: {rule['package']}")
                if rule.get('salience') is not None:
                    formatted_results.append(f"Salience: {rule['salience']}")
                
                # Format conditions
                conditions = rule.get('conditions', [])
                if conditions:
                    formatted_results.append("Conditions:")
                    for condition in conditions:
                        if condition.get('variable'):
                            formatted_results.append(f"- Variable: {condition['variable']}, Type: {condition['type']}")
                            constraints = condition.get('constraints', [])
                            for constraint in constraints:
                                if constraint.get('field'):
                                    formatted_results.append(f"  - {constraint['field']} {constraint['operator']} {constraint['value']}")
                
                # Format actions
                actions = rule.get('actions', [])
                if actions:
                    formatted_results.append("Actions:")
                    for action in actions:
                        if action.get('type') == 'method_call':
                            formatted_results.append(f"- Call method: {action['method']} on {action['target']}")
                            if action.get('arguments'):
                                formatted_results.append(f"  Arguments: {action['arguments']}")
                        elif action.get('type') == 'assignment':
                            formatted_results.append(f"- Assign to: {action['target']}")
                        else:
                            formatted_results.append(f"- {action['type']}: {action.get('target', '')}")
            else:
                formatted_results.append("No rule details found.")
        
        # Format rule dependencies
        if "rule_dependencies" in results:
            deps = results["rule_dependencies"]
            if deps and not "error" in deps:
                rule = deps.get("rule", {})
                formatted_results.append(f"Dependencies for rule '{rule.get('name')}':")
                
                # Format parent rules
                parents = deps.get("parents", [])
                if parents:
                    formatted_results.append("Parent rules (extends):")
                    for parent in parents:
                        formatted_results.append(f"- {parent['name']} (Package: {parent['package']})")
                else:
                    formatted_results.append("No parent rules.")
                
                # Format rules this rule depends on
                depends_on = deps.get("depends_on", [])
                if depends_on:
                    formatted_results.append("Rules this rule depends on:")
                    for dep in depends_on:
                        formatted_results.append(f"- {dep['name']} (Package: {dep['package']})")
                else:
                    formatted_results.append("This rule doesn't depend on other rules.")
                
                # Format rules that depend on this rule
                dependent_rules = deps.get("dependent_rules", [])
                if dependent_rules:
                    formatted_results.append("Rules that depend on this rule:")
                    for dep in dependent_rules:
                        formatted_results.append(f"- {dep['name']} (Package: {dep['package']})")
                else:
                    formatted_results.append("No rules depend on this rule.")
            elif "error" in deps:
                formatted_results.append(f"Error finding dependencies: {deps['error']}")
            else:
                formatted_results.append("No dependency information found.")
        
        # Format circular dependencies
        if "circular_dependencies" in results:
            circular_deps = results["circular_dependencies"]
            if circular_deps:
                formatted_results.append(f"Circular dependencies found ({len(circular_deps)}):")
                for i, dep in enumerate(circular_deps[:5]):  # Limit to 5 to avoid overwhelming the LLM
                    formatted_results.append(f"Circular dependency {i+1}:")
                    formatted_results.append(f"- From: {dep['from_rule']['name']} (Package: {dep['from_rule']['package']})")
                    formatted_results.append(f"- To: {dep['to_rule']['name']} (Package: {dep['to_rule']['package']})")
                    formatted_results.append(f"- Shared classes: {', '.join(dep['shared_classes'])}")
                if len(circular_deps) > 5:
                    formatted_results.append(f"... and {len(circular_deps) - 5} more circular dependencies.")
            else:
                formatted_results.append("No circular dependencies found.")
        
        # Format unused rules
        if "unused_rules" in results:
            unused_rules = results["unused_rules"]
            if unused_rules:
                formatted_results.append(f"Unused rules found ({len(unused_rules)}):")
                for rule in unused_rules[:10]:  # Limit to 10 to avoid overwhelming the LLM
                    salience = f", Salience: {rule['salience']}" if rule.get('salience') is not None else ""
                    formatted_results.append(f"- {rule['name']} (Package: {rule['package']}{salience})")
                if len(unused_rules) > 10:
                    formatted_results.append(f"... and {len(unused_rules) - 10} more unused rules.")
            else:
                formatted_results.append("No unused rules found.")
        
        # Format complex rules
        if "complex_rules" in results:
            complex_rules = results["complex_rules"]
            if complex_rules:
                formatted_results.append(f"Complex rules found ({len(complex_rules)}):")
                for rule in complex_rules[:10]:  # Limit to 10 to avoid overwhelming the LLM
                    formatted_results.append(
                        f"- {rule['name']} (Package: {rule['package']}, Complexity: {rule['total_complexity']})"
                    )
                    formatted_results.append(
                        f"  Details: {rule['condition_count']} conditions, {rule['constraint_count']} constraints, "
                        f"{rule['action_count']} actions, {rule['class_count']} referenced classes"
                    )
                if len(complex_rules) > 10:
                    formatted_results.append(f"... and {len(complex_rules) - 10} more complex rules.")
            else:
                formatted_results.append("No complex rules found.")
        
        # Format conflicting rules
        if "conflicting_rules" in results:
            conflicting_rules = results["conflicting_rules"]
            if conflicting_rules:
                formatted_results.append(f"Potentially conflicting rules found ({len(conflicting_rules)}):")
                for i, conflict in enumerate(conflicting_rules[:5]):  # Limit to 5 to avoid overwhelming the LLM
                    formatted_results.append(f"Conflict {i+1} ({conflict['conflict_type']}):")
                    formatted_results.append(
                        f"- Rule 1: {conflict['rule1']['name']} (Package: {conflict['rule1']['package']}, "
                        f"Salience: {conflict['rule1']['salience']})"
                    )
                    formatted_results.append(
                        f"- Rule 2: {conflict['rule2']['name']} (Package: {conflict['rule2']['package']}, "
                        f"Salience: {conflict['rule2']['salience']})"
                    )
                    formatted_results.append(f"- Fact type: {conflict['fact_type']}")
                    formatted_results.append(f"- Salience difference: {conflict['salience_difference']}")
                if len(conflicting_rules) > 5:
                    formatted_results.append(f"... and {len(conflicting_rules) - 5} more conflicts.")
            else:
                formatted_results.append("No conflicting rules found.")
        
        # Format execution order
        if "execution_order" in results:
            execution_order = results["execution_order"]
            if execution_order:
                formatted_results.append(f"Rule execution order ({len(execution_order)} rules):")
                for i, rule in enumerate(execution_order[:15]):  # Limit to 15 to avoid overwhelming the LLM
                    salience = f", Salience: {rule['original_salience']}" if rule.get('original_salience') is not None else ""
                    formatted_results.append(
                        f"{i+1}. {rule['name']} (Package: {rule['package']}{salience}, Type: {rule['rule_type']})"
                    )
                if len(execution_order) > 15:
                    formatted_results.append(f"... and {len(execution_order) - 15} more rules in the execution order.")
            else:
                formatted_results.append("No execution order information found.")
        
        return "\n".join(formatted_results)
    
    def _generate_template_response(self, intent: str, results: Dict[str, Any]) -> str:
        """
        Generate a response using templates.
        
        Args:
            intent: The query intent.
            results: The query results.
            
        Returns:
            A natural language response.
        """
        if intent == QueryIntent.FIND_RULE:
            return self._generate_find_rule_response(results)
        elif intent == QueryIntent.EXPLAIN_RULE:
            return self._generate_explain_rule_response(results)
        elif intent == QueryIntent.FIND_DEPENDENCIES:
            return self._generate_dependencies_response(results)
        elif intent == QueryIntent.FIND_CONFLICTS:
            return self._generate_conflicts_response(results)
        elif intent == QueryIntent.EXECUTION_ORDER:
            return self._generate_execution_order_response(results)
        elif intent == QueryIntent.FIND_PATTERNS:
            return self._generate_patterns_response(results)
        else:
            return "I'm sorry, I couldn't process that query type."
    
    def _generate_find_rule_response(self, results: Dict[str, Any]) -> str:
        """
        Generate a response for FIND_RULE intent.
        
        Args:
            results: The query results.
            
        Returns:
            A natural language response.
        """
        response_parts = []
        
        # Handle rules by name
        if "rules_by_name" in results:
            rules = results["rules_by_name"]
            if rules:
                response_parts.append(f"I found {len(rules)} rule(s) matching your query:")
                for rule in rules:
                    salience = f" (Salience: {rule['salience']})" if rule.get('salience') is not None else ""
                    response_parts.append(f"- {rule['name']} in package {rule['package']}{salience}")
            else:
                response_parts.append("I couldn't find any rules matching your query.")
        
        # Handle rules by class
        if "rules_by_class" in results:
            rules = results["rules_by_class"]
            if rules:
                response_parts.append(f"I found {len(rules)} rule(s) referencing the specified class:")
                for rule in rules:
                    salience = f" (Salience: {rule['salience']})" if rule.get('salience') is not None else ""
                    response_parts.append(f"- {rule['name']} in package {rule['package']}{salience}")
            else:
                response_parts.append("I couldn't find any rules referencing the specified class.")
        
        # Handle all rules
        if "all_rules" in results:
            rules = results["all_rules"]
            if rules:
                response_parts.append(f"There are {len(rules)} rules in the system.")
                if len(rules) <= 10:
                    response_parts.append("Here they are:")
                    for rule in rules:
                        salience = f" (Salience: {rule['salience']})" if rule.get('salience') is not None else ""
                        response_parts.append(f"- {rule['name']} in package {rule['package']}{salience}")
                else:
                    response_parts.append("Here are the first 10:")
                    for rule in rules[:10]:
                        salience = f" (Salience: {rule['salience']})" if rule.get('salience') is not None else ""
                        response_parts.append(f"- {rule['name']} in package {rule['package']}{salience}")
                    response_parts.append(f"... and {len(rules) - 10} more.")
            else:
                response_parts.append("There are no rules in the system.")
        
        # If no results were handled, return a generic message
        if not response_parts:
            return "I couldn't find any rules matching your query."
        
        return "\n".join(response_parts)
    
    def _generate_explain_rule_response(self, results: Dict[str, Any]) -> str:
        """
        Generate a response for EXPLAIN_RULE intent.
        
        Args:
            results: The query results.
            
        Returns:
            A natural language response.
        """
        response_parts = []
        
        # Handle rule details
        if "rule_details" in results:
            rule = results["rule_details"]
            if rule:
                response_parts.append(f"Here's an explanation of rule '{rule['name']}':")
                response_parts.append(f"Package: {rule['package']}")
                if rule.get('salience') is not None:
                    response_parts.append(f"Salience: {rule['salience']} (higher values fire first)")
                
                # Explain conditions
                conditions = rule.get('conditions', [])
                if conditions:
                    response_parts.append("\nConditions (when the rule fires):")
                    for condition in conditions:
                        if condition.get('variable'):
                            response_parts.append(f"- When there is a {condition['type']} object (variable: {condition['variable']})")
                            constraints = condition.get('constraints', [])
                            for constraint in constraints:
                                if constraint.get('field'):
                                    response_parts.append(f"  - With {constraint['field']} {constraint['operator']} {constraint['value']}")
                else:
                    response_parts.append("\nThis rule has no explicit conditions.")
                
                # Explain actions
                actions = rule.get('actions', [])
                if actions:
                    response_parts.append("\nActions (what the rule does when fired):")
                    for action in actions:
                        if action.get('type') == 'method_call':
                            response_parts.append(f"- Calls method {action['method']} on {action['target']}")
                            if action.get('arguments'):
                                response_parts.append(f"  With arguments: {action['arguments']}")
                        elif action.get('type') == 'assignment':
                            response_parts.append(f"- Assigns a value to {action['target']}")
                        else:
                            response_parts.append(f"- {action['type']}: {action.get('target', '')}")
                else:
                    response_parts.append("\nThis rule has no explicit actions.")
            else:
                response_parts.append("I couldn't find details for the specified rule.")
        
        # Handle rule dependencies
        if "rule_dependencies" in results:
            deps = results["rule_dependencies"]
            if deps and not "error" in deps:
                rule = deps.get("rule", {})
                response_parts.append(f"\nDependencies for rule '{rule.get('name')}':")
                
                # Explain parent rules
                parents = deps.get("parents", [])
                if parents:
                    response_parts.append("\nThis rule extends the following parent rules:")
                    for parent in parents:
                        response_parts.append(f"- {parent['name']} in package {parent['package']}")
                else:
                    response_parts.append("\nThis rule doesn't extend any parent rules.")
                
                # Explain rules this rule depends on
                depends_on = deps.get("depends_on", [])
                if depends_on:
                    response_parts.append("\nThis rule depends on (might be affected by):")
                    for dep in depends_on:
                        response_parts.append(f"- {dep['name']} in package {dep['package']}")
                else:
                    response_parts.append("\nThis rule doesn't depend on other rules.")
                
                # Explain rules that depend on this rule
                dependent_rules = deps.get("dependent_rules", [])
                if dependent_rules:
                    response_parts.append("\nThe following rules depend on this rule:")
                    for dep in dependent_rules:
                        response_parts.append(f"- {dep['name']} in package {dep['package']}")
                else:
                    response_parts.append("\nNo other rules depend on this rule.")
            elif "error" in deps:
                response_parts.append(f"\nError finding dependencies: {deps['error']}")
        
        # If no results were handled, return a generic message
        if not response_parts:
            return "I couldn't find information about the specified rule."
        
        return "\n".join(response_parts)
    
    def _generate_dependencies_response(self, results: Dict[str, Any]) -> str:
        """
        Generate a response for FIND_DEPENDENCIES intent.
        
        Args:
            results: The query results.
            
        Returns:
            A natural language response.
        """
        response_parts = []
        
        # Handle rule dependencies
        if "rule_dependencies" in results:
            deps = results["rule_dependencies"]
            if deps and not "error" in deps:
                rule = deps.get("rule", {})
                response_parts.append(f"Here are the dependencies for rule '{rule.get('name')}':")
                
                # Explain parent rules
                parents = deps.get("parents", [])
                if parents:
                    response_parts.append("\nParent rules (this rule extends):")
                    for parent in parents:
                        response_parts.append(f"- {parent['name']} in package {parent['package']}")
                else:
                    response_parts.append("\nThis rule doesn't extend any parent rules.")
                
                # Explain rules this rule depends on
                depends_on = deps.get("depends_on", [])
                if depends_on:
                    response_parts.append("\nRules this rule depends on:")
                    for dep in depends_on:
                        response_parts.append(f"- {dep['name']} in package {dep['package']}")
                else:
                    response_parts.append("\nThis rule doesn't depend on other rules.")
                
                # Explain rules that depend on this rule
                dependent_rules = deps.get("dependent_rules", [])
                if dependent_rules:
                    response_parts.append("\nRules that depend on this rule:")
                    for dep in dependent_rules:
                        response_parts.append(f"- {dep['name']} in package {dep['package']}")
                else:
                    response_parts.append("\nNo other rules depend on this rule.")
            elif "error" in deps:
                response_parts.append(f"Error finding dependencies: {deps['error']}")
        
        # Handle circular dependencies
        if "circular_dependencies" in results:
            circular_deps = results["circular_dependencies"]
            if circular_deps:
                response_parts.append(f"\nI found {len(circular_deps)} circular dependencies in the rule base:")
                for i, dep in enumerate(circular_deps[:5]):  # Limit to 5 to avoid overwhelming the response
                    response_parts.append(f"\nCircular dependency {i+1}:")
                    response_parts.append(f"- Rule '{dep['from_rule']['name']}' depends on rule '{dep['to_rule']['name']}'")
                    response_parts.append(f"- And rule '{dep['to_rule']['name']}' depends back on rule '{dep['from_rule']['name']}'")
                    response_parts.append(f"- They share these classes: {', '.join(dep['shared_classes'])}")
                if len(circular_deps) > 5:
                    response_parts.append(f"\n... and {len(circular_deps) - 5} more circular dependencies.")
                
                response_parts.append("\nCircular dependencies can cause unpredictable behavior in rule execution.")
            else:
                response_parts.append("\nNo circular dependencies found in the rule base.")
        
        # If no results were handled, return a generic message
        if not response_parts:
            return "I couldn't find dependency information for the specified rule."
        
        return "\n".join(response_parts)
    
    def _generate_conflicts_response(self, results: Dict[str, Any]) -> str:
        """
        Generate a response for FIND_CONFLICTS intent.
        
        Args:
            results: The query results.
            
        Returns:
            A natural language response.
        """
        response_parts = []
        
        # Handle conflicting rules
        if "conflicting_rules" in results:
            conflicting_rules = results["conflicting_rules"]
            if conflicting_rules:
                response_parts.append(f"I found {len(conflicting_rules)} potentially conflicting rules:")
                
                for i, conflict in enumerate(conflicting_rules[:5]):  # Limit to 5 to avoid overwhelming the response
                    response_parts.append(f"\nConflict {i+1} ({conflict['conflict_type']}):")
                    response_parts.append(f"- Rule 1: {conflict['rule1']['name']} in package {conflict['rule1']['package']}")
                    response_parts.append(f"- Rule 2: {conflict['rule2']['name']} in package {conflict['rule2']['package']}")
                    response_parts.append(f"- Both rules operate on fact type: {conflict['fact_type']}")
                    response_parts.append(f"- Salience difference: {conflict['salience_difference']}")
                    
                    # Explain the type of conflict
                    if conflict['conflict_type'] == 'contradictory_constraints':
                        response_parts.append("  These rules have contradictory constraints on the same fields.")
                    elif conflict['conflict_type'] == 'potential_action_conflict':
                        response_parts.append("  These rules have similar conditions but different actions.")
                    elif conflict['conflict_type'] == 'potential_condition_overlap':
                        response_parts.append("  These rules have overlapping conditions and similar salience.")
                    elif conflict['conflict_type'] == 'redundant_rules':
                        response_parts.append("  These rules perform similar actions with different conditions.")
                
                if len(conflicting_rules) > 5:
                    response_parts.append(f"\n... and {len(conflicting_rules) - 5} more conflicts.")
                
                response_parts.append("\nConflicting rules may lead to inconsistent behavior or unexpected results.")
            else:
                response_parts.append("I didn't find any conflicting rules in the rule base.")
        
        # If no results were handled, return a generic message
        if not response_parts:
            return "I couldn't find any information about rule conflicts."
        
        return "\n".join(response_parts)
    
    def _generate_execution_order_response(self, results: Dict[str, Any]) -> str:
        """
        Generate a response for EXECUTION_ORDER intent.
        
        Args:
            results: The query results.
            
        Returns:
            A natural language response.
        """
        response_parts = []
        
        # Handle execution order
        if "execution_order" in results:
            execution_order = results["execution_order"]
            if execution_order:
                response_parts.append(f"Here's the likely execution order for {len(execution_order)} rules:")
                response_parts.append("(Based on salience values and dependencies)")
                
                for i, rule in enumerate(execution_order[:15]):  # Limit to 15 to avoid overwhelming the response
                    salience = f" (Salience: {rule['original_salience']})" if rule.get('original_salience') is not None else ""
                    rule_type = ""
                    if rule['rule_type'] == 'high_priority':
                        rule_type = " [High Priority]"
                    elif rule['rule_type'] == 'entry_point':
                        rule_type = " [Entry Point]"
                    elif rule['rule_type'] == 'aggregator':
                        rule_type = " [Aggregator]"
                    
                    response_parts.append(f"{i+1}. {rule['name']}{salience}{rule_type}")
                
                if len(execution_order) > 15:
                    response_parts.append(f"\n... and {len(execution_order) - 15} more rules.")
                
                response_parts.append("\nNote: The actual execution order may vary based on the facts in working memory.")
            else:
                response_parts.append("I couldn't determine the execution order for the rules.")
        
        # If no results were handled, return a generic message
        if not response_parts:
            return "I couldn't find information about rule execution order."
        
        return "\n".join(response_parts)
    
    def _generate_patterns_response(self, results: Dict[str, Any]) -> str:
        """
        Generate a response for FIND_PATTERNS intent.
        
        Args:
            results: The query results.
            
        Returns:
            A natural language response.
        """
        response_parts = []
        
        # Handle unused rules
        if "unused_rules" in results:
            unused_rules = results["unused_rules"]
            if unused_rules:
                response_parts.append(f"I found {len(unused_rules)} unused rules:")
                for i, rule in enumerate(unused_rules[:10]):  # Limit to 10 to avoid overwhelming the response
                    response_parts.append(f"{i+1}. {rule['name']} in package {rule['package']}")
                if len(unused_rules) > 10:
                    response_parts.append(f"... and {len(unused_rules) - 10} more unused rules.")
                response_parts.append("\nUnused rules may be candidates for removal or might indicate missing dependencies.")
            else:
                response_parts.append("I didn't find any unused rules in the rule base.")
        
        # Handle circular dependencies
        if "circular_dependencies" in results:
            circular_deps = results["circular_dependencies"]
            if circular_deps:
                response_parts.append(f"\nI found {len(circular_deps)} circular dependencies:")
                for i, dep in enumerate(circular_deps[:5]):  # Limit to 5 to avoid overwhelming the response
                    response_parts.append(f"{i+1}. {dep['from_rule']['name']} ↔ {dep['to_rule']['name']}")
                if len(circular_deps) > 5:
                    response_parts.append(f"... and {len(circular_deps) - 5} more circular dependencies.")
                response_parts.append("\nCircular dependencies can cause unpredictable behavior and should be resolved.")
            else:
                response_parts.append("\nI didn't find any circular dependencies in the rule base.")
        
        # Handle complex rules
        if "complex_rules" in results:
            complex_rules = results["complex_rules"]
            if complex_rules:
                response_parts.append(f"\nI found {len(complex_rules)} complex rules that might benefit from refactoring:")
                for i, rule in enumerate(complex_rules[:10]):  # Limit to 10 to avoid overwhelming the response
                    response_parts.append(
                        f"{i+1}. {rule['name']} (Complexity: {rule['total_complexity']}, "
                        f"{rule['condition_count']} conditions, {rule['constraint_count']} constraints)"
                    )
                if len(complex_rules) > 10:
                    response_parts.append(f"... and {len(complex_rules) - 10} more complex rules.")
                response_parts.append("\nComplex rules may be harder to maintain and understand.")
            else:
                response_parts.append("\nI didn't find any overly complex rules in the rule base.")
        
        # Handle conflicting rules
        if "conflicting_rules" in results:
            conflicting_rules = results["conflicting_rules"]
            if conflicting_rules:
                response_parts.append(f"\nI found {len(conflicting_rules)} potentially conflicting rules:")
                for i, conflict in enumerate(conflicting_rules[:5]):  # Limit to 5 to avoid overwhelming the response
                    response_parts.append(
                        f"{i+1}. {conflict['rule1']['name']} conflicts with {conflict['rule2']['name']} "
                        f"({conflict['conflict_type']})"
                    )
                if len(conflicting_rules) > 5:
                    response_parts.append(f"... and {len(conflicting_rules) - 5} more conflicts.")
                response_parts.append("\nConflicting rules may lead to inconsistent behavior.")
            else:
                response_parts.append("\nI didn't find any conflicting rules in the rule base.")
        
        # If no results were handled, return a generic message
        if not response_parts:
            return "I couldn't find any patterns or issues in the rule base."
        
        return "\n".join(response_parts)


class RuleExplainer:
    """
    Class for generating specialized explanations of rules and their relationships.
    """
    
    def __init__(self, response_generator: ResponseGenerator) -> None:
        """
        Initialize the rule explainer.
        
        Args:
            response_generator: The response generator to use for generating explanations.
        """
        self.response_generator = response_generator
    
    def explain_rule_context(self, rule_name: str, query_results: Dict[str, Any]) -> str:
        """
        Provide contextual explanation of a rule including when it fires and what it affects.
        
        Args:
            rule_name: The name of the rule to explain.
            query_results: The query results containing rule details and dependencies.
            
        Returns:
            A natural language explanation of the rule context.
        """
        # Create a synthetic query for the response generator
        synthetic_query = f"Explain the context of rule '{rule_name}'"
        
        # Generate the response
        return self.response_generator.generate_response(synthetic_query, {
            "intent": QueryIntent.EXPLAIN_RULE,
            "results": query_results
        })
    
    def explain_rule_conflicts(self, rule_names: List[str], query_results: Dict[str, Any]) -> str:
        """
        Explain conflicts between multiple rules and their resolution.
        
        Args:
            rule_names: The names of the rules to explain conflicts for.
            query_results: The query results containing conflict information.
            
        Returns:
            A natural language explanation of the rule conflicts.
        """
        # Create a synthetic query for the response generator
        if len(rule_names) == 1:
            synthetic_query = f"Explain conflicts involving rule '{rule_names[0]}'"
        else:
            synthetic_query = f"Explain conflicts between rules {', '.join([f\"'{name}'\" for name in rule_names])}"
        
        # Generate the response
        return self.response_generator.generate_response(synthetic_query, {
            "intent": QueryIntent.FIND_CONFLICTS,
            "results": query_results
        })
    
    def explain_execution_order(self, rule_names: List[str], query_results: Dict[str, Any]) -> str:
        """
        Explain the execution order of rules based on salience and dependencies.
        
        Args:
            rule_names: The names of the rules to explain execution order for.
            query_results: The query results containing execution order information.
            
        Returns:
            A natural language explanation of the rule execution order.
        """
        # Create a synthetic query for the response generator
        if len(rule_names) == 1:
            synthetic_query = f"Explain the execution order for rule '{rule_names[0]}'"
        else:
            synthetic_query = f"Explain the execution order for rules {', '.join([f\"'{name}'\" for name in rule_names])}"
        
        # Generate the response
        return self.response_generator.generate_response(synthetic_query, {
            "intent": QueryIntent.EXECUTION_ORDER,
            "results": query_results
        })