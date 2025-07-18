"""
Tests for the response generator module.
"""
import unittest
from unittest.mock import MagicMock, patch

from drools_graph_rag.rag.response_generator import ResponseGenerator, RuleExplainer
from drools_graph_rag.rag.query_processor import QueryIntent


class TestResponseGenerator(unittest.TestCase):
    """
    Test the ResponseGenerator class.
    """
    
    def setUp(self):
        """
        Set up the test environment.
        """
        # Create a response generator
        self.response_generator = ResponseGenerator()
        
        # Mock the LLM
        self.response_generator.llm = None
    
    @patch("drools_graph_rag.rag.response_generator.LANGCHAIN_AVAILABLE", True)
    @patch("langchain.chat_models.ChatOpenAI")
    def test_init_with_llm(self, mock_chat_openai):
        """
        Test initialization with LLM.
        """
        # Mock the LLM
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm
        
        # Create a response generator with LLM
        with patch("drools_graph_rag.rag.response_generator.config") as mock_config:
            mock_config.llm.api_key = "test_key"
            mock_config.llm.model_name = "gpt-3.5-turbo"
            mock_config.llm.temperature = 0.7
            mock_config.llm.max_tokens = 1024
            
            response_generator = ResponseGenerator()
            
            # Check that the LLM was initialized
            self.assertIsNotNone(response_generator.llm)
            mock_chat_openai.assert_called_once_with(
                model_name="gpt-3.5-turbo",
                temperature=0.7,
                max_tokens=1024,
                openai_api_key="test_key"
            )
    
    def test_generate_response_error(self):
        """
        Test generating a response for an error.
        """
        # Test with error in query_results
        query = "Find rule named 'Test'"
        query_results = {"error": "Rule not found"}
        response = self.response_generator.generate_response(query, query_results)
        self.assertIn("Error", response)
        self.assertIn("Rule not found", response)
        
        # Test with error in results
        query_results = {"intent": QueryIntent.FIND_RULE, "results": {"error": "Rule not found"}}
        response = self.response_generator.generate_response(query, query_results)
        self.assertIn("Error", response)
        self.assertIn("Rule not found", response)
    
    @patch("drools_graph_rag.rag.response_generator.ResponseGenerator._generate_llm_response")
    def test_generate_response_with_llm(self, mock_generate_llm_response):
        """
        Test generating a response with LLM.
        """
        # Mock the LLM response
        mock_generate_llm_response.return_value = "This is an LLM response"
        
        # Set up the LLM
        self.response_generator.llm = MagicMock()
        
        # Generate a response
        query = "Find rule named 'Test'"
        query_results = {"intent": QueryIntent.FIND_RULE, "results": {}}
        response = self.response_generator.generate_response(query, query_results)
        
        # Check that the LLM was used
        self.assertEqual(response, "This is an LLM response")
        mock_generate_llm_response.assert_called_once_with(query, QueryIntent.FIND_RULE, {})
    
    def test_generate_response_without_llm(self):
        """
        Test generating a response without LLM.
        """
        # Ensure no LLM is set
        self.response_generator.llm = None
        
        # Generate a response
        query = "Find rule named 'Test'"
        query_results = {
            "intent": QueryIntent.FIND_RULE,
            "results": {
                "rules_by_name": [
                    {"name": "Test Rule", "package": "com.example", "salience": 100, "id": 1}
                ]
            }
        }
        response = self.response_generator.generate_response(query, query_results)
        
        # Check that a template-based response was generated
        self.assertIn("I found 1 rule", response)
        self.assertIn("Test Rule", response)
        self.assertIn("com.example", response)
    
    def test_get_prompt_template(self):
        """
        Test getting prompt templates for different intents.
        """
        # Test for each intent type
        for intent_type in [
            QueryIntent.FIND_RULE,
            QueryIntent.EXPLAIN_RULE,
            QueryIntent.FIND_DEPENDENCIES,
            QueryIntent.FIND_CONFLICTS,
            QueryIntent.EXECUTION_ORDER,
            QueryIntent.FIND_PATTERNS,
            "unknown"
        ]:
            template = self.response_generator._get_prompt_template(intent_type)
            self.assertIsInstance(template, str)
            self.assertIn("{query}", template)
            self.assertIn("{results}", template)
    
    def test_format_results_for_llm(self):
        """
        Test formatting results for LLM.
        """
        # Test with rules by name
        results = {
            "rules_by_name": [
                {"name": "Rule 1", "package": "com.example", "salience": 100, "id": 1},
                {"name": "Rule 2", "package": "com.example", "salience": 90, "id": 2}
            ]
        }
        formatted = self.response_generator._format_results_for_llm(results)
        self.assertIn("Rules found by name (2):", formatted)
        self.assertIn("Rule 1", formatted)
        self.assertIn("Rule 2", formatted)
        
        # Test with rule details
        results = {
            "rule_details": {
                "name": "Test Rule",
                "package": "com.example",
                "salience": 100,
                "conditions": [
                    {
                        "variable": "$customer",
                        "type": "Customer",
                        "constraints": [
                            {"field": "age", "operator": ">", "value": "18"}
                        ]
                    }
                ],
                "actions": [
                    {"type": "method_call", "target": "validationResult", "method": "addError"}
                ]
            }
        }
        formatted = self.response_generator._format_results_for_llm(results)
        self.assertIn("Rule details for 'Test Rule':", formatted)
        self.assertIn("Package: com.example", formatted)
        self.assertIn("Salience: 100", formatted)
        self.assertIn("Variable: $customer", formatted)
        self.assertIn("age > 18", formatted)
        self.assertIn("Call method: addError", formatted)
    
    def test_generate_find_rule_response(self):
        """
        Test generating a response for FIND_RULE intent.
        """
        # Test with rules by name
        results = {
            "rules_by_name": [
                {"name": "Rule 1", "package": "com.example", "salience": 100, "id": 1},
                {"name": "Rule 2", "package": "com.example", "salience": 90, "id": 2}
            ]
        }
        response = self.response_generator._generate_find_rule_response(results)
        self.assertIn("I found 2 rule(s)", response)
        self.assertIn("Rule 1", response)
        self.assertIn("Rule 2", response)
        
        # Test with no rules
        results = {"rules_by_name": []}
        response = self.response_generator._generate_find_rule_response(results)
        self.assertIn("couldn't find any rules", response)
    
    def test_generate_explain_rule_response(self):
        """
        Test generating a response for EXPLAIN_RULE intent.
        """
        # Test with rule details and dependencies
        results = {
            "rule_details": {
                "name": "Test Rule",
                "package": "com.example",
                "salience": 100,
                "conditions": [
                    {
                        "variable": "$customer",
                        "type": "Customer",
                        "constraints": [
                            {"field": "age", "operator": ">", "value": "18"}
                        ]
                    }
                ],
                "actions": [
                    {"type": "method_call", "target": "validationResult", "method": "addError"}
                ]
            },
            "rule_dependencies": {
                "rule": {"name": "Test Rule", "package": "com.example"},
                "parents": [],
                "depends_on": [],
                "dependent_rules": []
            }
        }
        response = self.response_generator._generate_explain_rule_response(results)
        self.assertIn("explanation of rule 'Test Rule'", response)
        self.assertIn("Package: com.example", response)
        self.assertIn("Salience: 100", response)
        self.assertIn("When there is a Customer object", response)
        self.assertIn("age > 18", response)
        self.assertIn("Calls method addError", response)
        self.assertIn("doesn't extend any parent rules", response)
        self.assertIn("doesn't depend on other rules", response)
        self.assertIn("No other rules depend on this rule", response)
    
    def test_generate_dependencies_response(self):
        """
        Test generating a response for FIND_DEPENDENCIES intent.
        """
        # Test with rule dependencies
        results = {
            "rule_dependencies": {
                "rule": {"name": "Test Rule", "package": "com.example"},
                "parents": [
                    {"name": "Parent Rule", "package": "com.example"}
                ],
                "depends_on": [
                    {"name": "Dependency Rule", "package": "com.example"}
                ],
                "dependent_rules": [
                    {"name": "Dependent Rule", "package": "com.example"}
                ]
            }
        }
        response = self.response_generator._generate_dependencies_response(results)
        self.assertIn("dependencies for rule 'Test Rule'", response)
        self.assertIn("Parent rules", response)
        self.assertIn("Parent Rule", response)
        self.assertIn("Rules this rule depends on", response)
        self.assertIn("Dependency Rule", response)
        self.assertIn("Rules that depend on this rule", response)
        self.assertIn("Dependent Rule", response)
        
        # Test with circular dependencies
        results = {
            "circular_dependencies": [
                {
                    "from_rule": {"name": "Rule 1", "package": "com.example"},
                    "to_rule": {"name": "Rule 2", "package": "com.example"},
                    "shared_classes": ["Customer"]
                }
            ]
        }
        response = self.response_generator._generate_dependencies_response(results)
        self.assertIn("circular dependencies", response)
        self.assertIn("Rule 1", response)
        self.assertIn("Rule 2", response)
        self.assertIn("Customer", response)
    
    def test_generate_conflicts_response(self):
        """
        Test generating a response for FIND_CONFLICTS intent.
        """
        # Test with conflicting rules
        results = {
            "conflicting_rules": [
                {
                    "rule1": {"name": "Rule 1", "package": "com.example", "salience": 100},
                    "rule2": {"name": "Rule 2", "package": "com.example", "salience": 90},
                    "conflict_type": "contradictory_constraints",
                    "fact_type": "Customer",
                    "salience_difference": 10
                }
            ]
        }
        response = self.response_generator._generate_conflicts_response(results)
        self.assertIn("potentially conflicting rules", response)
        self.assertIn("Rule 1", response)
        self.assertIn("Rule 2", response)
        self.assertIn("contradictory_constraints", response)
        self.assertIn("Customer", response)
        
        # Test with no conflicts
        results = {"conflicting_rules": []}
        response = self.response_generator._generate_conflicts_response(results)
        self.assertIn("didn't find any conflicting rules", response)
    
    def test_generate_execution_order_response(self):
        """
        Test generating a response for EXECUTION_ORDER intent.
        """
        # Test with execution order
        results = {
            "execution_order": [
                {
                    "name": "Rule 1",
                    "package": "com.example",
                    "original_salience": 100,
                    "effective_salience": 100,
                    "rule_type": "high_priority"
                },
                {
                    "name": "Rule 2",
                    "package": "com.example",
                    "original_salience": 90,
                    "effective_salience": 90,
                    "rule_type": "normal"
                }
            ]
        }
        response = self.response_generator._generate_execution_order_response(results)
        self.assertIn("execution order", response)
        self.assertIn("Rule 1", response)
        self.assertIn("Rule 2", response)
        self.assertIn("High Priority", response)
        
        # Test with no execution order
        results = {"execution_order": []}
        response = self.response_generator._generate_execution_order_response(results)
        self.assertIn("couldn't determine the execution order", response)
    
    def test_generate_patterns_response(self):
        """
        Test generating a response for FIND_PATTERNS intent.
        """
        # Test with various patterns
        results = {
            "unused_rules": [
                {"name": "Unused Rule", "package": "com.example", "salience": 100, "id": 1}
            ],
            "circular_dependencies": [
                {
                    "from_rule": {"name": "Rule 1", "package": "com.example"},
                    "to_rule": {"name": "Rule 2", "package": "com.example"},
                    "shared_classes": ["Customer"]
                }
            ],
            "complex_rules": [
                {
                    "name": "Complex Rule",
                    "package": "com.example",
                    "total_complexity": 20,
                    "condition_count": 5,
                    "constraint_count": 10,
                    "action_count": 3,
                    "class_count": 2
                }
            ],
            "conflicting_rules": [
                {
                    "rule1": {"name": "Rule 1", "package": "com.example", "salience": 100},
                    "rule2": {"name": "Rule 2", "package": "com.example", "salience": 90},
                    "conflict_type": "contradictory_constraints",
                    "fact_type": "Customer",
                    "salience_difference": 10
                }
            ]
        }
        response = self.response_generator._generate_patterns_response(results)
        self.assertIn("unused rules", response)
        self.assertIn("Unused Rule", response)
        self.assertIn("circular dependencies", response)
        self.assertIn("Rule 1", response)
        self.assertIn("Rule 2", response)
        self.assertIn("complex rules", response)
        self.assertIn("Complex Rule", response)
        self.assertIn("conflicting rules", response)
        self.assertIn("contradictory_constraints", response)


class TestRuleExplainer(unittest.TestCase):
    """
    Test the RuleExplainer class.
    """
    
    def setUp(self):
        """
        Set up the test environment.
        """
        # Create a mock response generator
        self.mock_response_generator = MagicMock(spec=ResponseGenerator)
        
        # Create a rule explainer
        self.rule_explainer = RuleExplainer(self.mock_response_generator)
    
    def test_explain_rule_context(self):
        """
        Test explaining rule context.
        """
        # Set up mock return value
        self.mock_response_generator.generate_response.return_value = "Rule context explanation"
        
        # Call the method
        rule_name = "Test Rule"
        query_results = {"rule_details": {}, "rule_dependencies": {}}
        result = self.rule_explainer.explain_rule_context(rule_name, query_results)
        
        # Check the result
        self.assertEqual(result, "Rule context explanation")
        
        # Verify mock calls
        self.mock_response_generator.generate_response.assert_called_once()
        args = self.mock_response_generator.generate_response.call_args[0]
        self.assertIn("Explain the context of rule 'Test Rule'", args[0])
        self.assertEqual(args[1]["intent"], QueryIntent.EXPLAIN_RULE)
        self.assertEqual(args[1]["results"], query_results)
    
    def test_explain_rule_conflicts(self):
        """
        Test explaining rule conflicts.
        """
        # Set up mock return value
        self.mock_response_generator.generate_response.return_value = "Rule conflicts explanation"
        
        # Call the method with a single rule
        rule_names = ["Test Rule"]
        query_results = {"conflicting_rules": []}
        result = self.rule_explainer.explain_rule_conflicts(rule_names, query_results)
        
        # Check the result
        self.assertEqual(result, "Rule conflicts explanation")
        
        # Verify mock calls
        self.mock_response_generator.generate_response.assert_called_once()
        args = self.mock_response_generator.generate_response.call_args[0]
        self.assertIn("Explain conflicts involving rule 'Test Rule'", args[0])
        self.assertEqual(args[1]["intent"], QueryIntent.FIND_CONFLICTS)
        self.assertEqual(args[1]["results"], query_results)
        
        # Reset mock
        self.mock_response_generator.generate_response.reset_mock()
        
        # Call the method with multiple rules
        rule_names = ["Rule 1", "Rule 2"]
        result = self.rule_explainer.explain_rule_conflicts(rule_names, query_results)
        
        # Check the result
        self.assertEqual(result, "Rule conflicts explanation")
        
        # Verify mock calls
        self.mock_response_generator.generate_response.assert_called_once()
        args = self.mock_response_generator.generate_response.call_args[0]
        self.assertIn("Explain conflicts between rules 'Rule 1', 'Rule 2'", args[0])
    
    def test_explain_execution_order(self):
        """
        Test explaining execution order.
        """
        # Set up mock return value
        self.mock_response_generator.generate_response.return_value = "Execution order explanation"
        
        # Call the method with a single rule
        rule_names = ["Test Rule"]
        query_results = {"execution_order": []}
        result = self.rule_explainer.explain_execution_order(rule_names, query_results)
        
        # Check the result
        self.assertEqual(result, "Execution order explanation")
        
        # Verify mock calls
        self.mock_response_generator.generate_response.assert_called_once()
        args = self.mock_response_generator.generate_response.call_args[0]
        self.assertIn("Explain the execution order for rule 'Test Rule'", args[0])
        self.assertEqual(args[1]["intent"], QueryIntent.EXECUTION_ORDER)
        self.assertEqual(args[1]["results"], query_results)
        
        # Reset mock
        self.mock_response_generator.generate_response.reset_mock()
        
        # Call the method with multiple rules
        rule_names = ["Rule 1", "Rule 2"]
        result = self.rule_explainer.explain_execution_order(rule_names, query_results)
        
        # Check the result
        self.assertEqual(result, "Execution order explanation")
        
        # Verify mock calls
        self.mock_response_generator.generate_response.assert_called_once()
        args = self.mock_response_generator.generate_response.call_args[0]
        self.assertIn("Explain the execution order for rules 'Rule 1', 'Rule 2'", args[0])


if __name__ == "__main__":
    unittest.main()