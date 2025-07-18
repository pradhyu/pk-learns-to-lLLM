"""
Tests for the RAG interface module.
"""
import unittest
from unittest.mock import MagicMock, patch

from drools_graph_rag.rag.interface import RAGInterface
from drools_graph_rag.rag.query_processor import QueryProcessor, QueryIntent
from drools_graph_rag.rag.response_generator import ResponseGenerator, RuleExplainer
from drools_graph_rag.query_engine.query_engine import GraphQueryEngine
from drools_graph_rag.graph.connection import Neo4jConnection


class TestRAGInterface(unittest.TestCase):
    """
    Test the RAGInterface class.
    """
    
    def setUp(self):
        """
        Set up the test environment.
        """
        # Create mocks
        self.mock_connection = MagicMock(spec=Neo4jConnection)
        self.mock_query_engine = MagicMock(spec=GraphQueryEngine)
        self.mock_query_processor = MagicMock(spec=QueryProcessor)
        self.mock_query_translator = MagicMock()
        self.mock_response_generator = MagicMock(spec=ResponseGenerator)
        self.mock_rule_explainer = MagicMock(spec=RuleExplainer)
        
        # Patch the GraphQueryEngine constructor
        with patch('drools_graph_rag.rag.interface.GraphQueryEngine') as mock_query_engine_class:
            mock_query_engine_class.return_value = self.mock_query_engine
            
            # Patch the QueryTranslator constructor
            with patch('drools_graph_rag.rag.interface.QueryTranslator') as mock_translator_class:
                mock_translator_class.return_value = self.mock_query_translator
                
                # Patch the RuleExplainer constructor
                with patch('drools_graph_rag.rag.interface.RuleExplainer') as mock_explainer_class:
                    mock_explainer_class.return_value = self.mock_rule_explainer
                    
                    # Create the interface
                    self.interface = RAGInterface(
                        neo4j_connection=self.mock_connection,
                        query_processor=self.mock_query_processor,
                        response_generator=self.mock_response_generator
                    )
    
    def test_init(self):
        """
        Test initialization of RAGInterface.
        """
        # Check that the components were initialized correctly
        self.assertEqual(self.interface.neo4j_connection, self.mock_connection)
        self.assertEqual(self.interface.query_engine, self.mock_query_engine)
        self.assertEqual(self.interface.query_processor, self.mock_query_processor)
        self.assertEqual(self.interface.query_translator, self.mock_query_translator)
        self.assertEqual(self.interface.response_generator, self.mock_response_generator)
        self.assertEqual(self.interface.rule_explainer, self.mock_rule_explainer)
    
    @patch('drools_graph_rag.rag.interface.Neo4jConnection')
    def test_init_with_defaults(self, mock_connection_class):
        """
        Test initialization with default components.
        """
        # Mock the Neo4jConnection constructor
        mock_connection = MagicMock(spec=Neo4jConnection)
        mock_connection_class.return_value = mock_connection
        
        # Patch the GraphQueryEngine constructor
        with patch('drools_graph_rag.rag.interface.GraphQueryEngine') as mock_query_engine_class:
            mock_query_engine = MagicMock(spec=GraphQueryEngine)
            mock_query_engine_class.return_value = mock_query_engine
            
            # Patch the QueryProcessor constructor
            with patch('drools_graph_rag.rag.interface.QueryProcessor') as mock_processor_class:
                mock_processor = MagicMock(spec=QueryProcessor)
                mock_processor_class.return_value = mock_processor
                
                # Patch the QueryTranslator constructor
                with patch('drools_graph_rag.rag.interface.QueryTranslator') as mock_translator_class:
                    mock_translator = MagicMock()
                    mock_translator_class.return_value = mock_translator
                    
                    # Patch the ResponseGenerator constructor
                    with patch('drools_graph_rag.rag.interface.ResponseGenerator') as mock_generator_class:
                        mock_generator = MagicMock(spec=ResponseGenerator)
                        mock_generator_class.return_value = mock_generator
                        
                        # Patch the RuleExplainer constructor
                        with patch('drools_graph_rag.rag.interface.RuleExplainer') as mock_explainer_class:
                            mock_explainer = MagicMock(spec=RuleExplainer)
                            mock_explainer_class.return_value = mock_explainer
                            
                            # Create the interface with defaults
                            interface = RAGInterface()
                            
                            # Check that the components were initialized correctly
                            self.assertEqual(interface.neo4j_connection, mock_connection)
                            self.assertEqual(interface.query_engine, mock_query_engine)
                            self.assertEqual(interface.query_processor, mock_processor)
                            self.assertEqual(interface.query_translator, mock_translator)
                            self.assertEqual(interface.response_generator, mock_generator)
                            self.assertEqual(interface.rule_explainer, mock_explainer)
    
    def test_process_query(self):
        """
        Test processing a query.
        """
        # Set up mock return values
        mock_intent = MagicMock()
        mock_intent.intent_type = QueryIntent.FIND_RULE
        mock_intent.confidence = 0.9
        self.mock_query_processor.process_query.return_value = mock_intent
        
        mock_query_results = {"intent": QueryIntent.FIND_RULE, "results": {}}
        self.mock_query_translator.translate_intent.return_value = mock_query_results
        
        self.mock_response_generator.generate_response.return_value = "This is a response"
        
        # Process a query
        query = "Find rule named 'Test'"
        response = self.interface.process_query(query)
        
        # Check the response
        self.assertEqual(response, "This is a response")
        
        # Verify mock calls
        self.mock_query_processor.process_query.assert_called_once_with(query)
        self.mock_query_translator.translate_intent.assert_called_once_with(mock_intent)
        self.mock_response_generator.generate_response.assert_called_once_with(query, mock_query_results)
    
    def test_process_query_error(self):
        """
        Test processing a query with an error.
        """
        # Set up mock to raise an exception
        self.mock_query_processor.process_query.side_effect = Exception("Test error")
        
        # Process a query
        query = "Find rule named 'Test'"
        response = self.interface.process_query(query)
        
        # Check the response
        self.assertIn("Error processing query", response)
        self.assertIn("Test error", response)
    
    def test_explain_rule_context(self):
        """
        Test explaining rule context.
        """
        # Set up mock return values
        self.mock_query_engine.find_rule_by_exact_name.return_value = {
            "name": "Test Rule", "package": "com.example", "salience": 100, "id": 1
        }
        self.mock_query_engine.get_rule_details.return_value = {
            "name": "Test Rule", "package": "com.example", "salience": 100,
            "conditions": [], "actions": []
        }
        self.mock_query_engine.find_rule_dependencies.return_value = {
            "rule": {"name": "Test Rule", "package": "com.example"},
            "parents": [], "depends_on": [], "dependent_rules": []
        }
        self.mock_rule_explainer.explain_rule_context.return_value = "Rule context explanation"
        
        # Explain rule context
        rule_name = "Test Rule"
        explanation = self.interface.explain_rule_context(rule_name)
        
        # Check the explanation
        self.assertEqual(explanation, "Rule context explanation")
        
        # Verify mock calls
        self.mock_query_engine.find_rule_by_exact_name.assert_called_once_with(rule_name)
        self.mock_query_engine.get_rule_details.assert_called_once_with(1)
        self.mock_query_engine.find_rule_dependencies.assert_called_once_with("Test Rule", "com.example")
        self.mock_rule_explainer.explain_rule_context.assert_called_once()
        args = self.mock_rule_explainer.explain_rule_context.call_args[0]
        self.assertEqual(args[0], rule_name)
        self.assertIn("rule_details", args[1])
        self.assertIn("rule_dependencies", args[1])
    
    def test_explain_rule_context_fuzzy_match(self):
        """
        Test explaining rule context with fuzzy matching.
        """
        # Set up mock return values
        self.mock_query_engine.find_rule_by_exact_name.return_value = None
        self.mock_query_engine.find_rules_by_name.return_value = [
            {"name": "Test Rule", "package": "com.example", "salience": 100, "id": 1}
        ]
        self.mock_query_engine.get_rule_details.return_value = {
            "name": "Test Rule", "package": "com.example", "salience": 100,
            "conditions": [], "actions": []
        }
        self.mock_query_engine.find_rule_dependencies.return_value = {
            "rule": {"name": "Test Rule", "package": "com.example"},
            "parents": [], "depends_on": [], "dependent_rules": []
        }
        self.mock_rule_explainer.explain_rule_context.return_value = "Rule context explanation"
        
        # Explain rule context
        rule_name = "Test"
        explanation = self.interface.explain_rule_context(rule_name)
        
        # Check the explanation
        self.assertEqual(explanation, "Rule context explanation")
        
        # Verify mock calls
        self.mock_query_engine.find_rule_by_exact_name.assert_called_once_with(rule_name)
        self.mock_query_engine.find_rules_by_name.assert_called_once_with(".*Test.*")
        self.mock_query_engine.get_rule_details.assert_called_once_with(1)
        self.mock_query_engine.find_rule_dependencies.assert_called_once_with("Test Rule", "com.example")
    
    def test_explain_rule_context_not_found(self):
        """
        Test explaining rule context when the rule is not found.
        """
        # Set up mock return values
        self.mock_query_engine.find_rule_by_exact_name.return_value = None
        self.mock_query_engine.find_rules_by_name.return_value = []
        
        # Explain rule context
        rule_name = "Nonexistent Rule"
        explanation = self.interface.explain_rule_context(rule_name)
        
        # Check the explanation
        self.assertIn("not found", explanation)
    
    def test_explain_rule_conflicts(self):
        """
        Test explaining rule conflicts.
        """
        # Set up mock return values
        self.mock_query_engine.find_conflicting_rules.return_value = [
            {
                "rule1": {"name": "Rule 1", "package": "com.example", "salience": 100},
                "rule2": {"name": "Rule 2", "package": "com.example", "salience": 90},
                "conflict_type": "contradictory_constraints",
                "fact_type": "Customer",
                "salience_difference": 10
            }
        ]
        self.mock_rule_explainer.explain_rule_conflicts.return_value = "Rule conflicts explanation"
        
        # Explain rule conflicts
        rule_names = ["Rule 1", "Rule 2"]
        explanation = self.interface.explain_rule_conflicts(rule_names)
        
        # Check the explanation
        self.assertEqual(explanation, "Rule conflicts explanation")
        
        # Verify mock calls
        self.mock_query_engine.find_conflicting_rules.assert_called_once()
        self.mock_rule_explainer.explain_rule_conflicts.assert_called_once()
        args = self.mock_rule_explainer.explain_rule_conflicts.call_args[0]
        self.assertEqual(args[0], rule_names)
        self.assertIn("conflicting_rules", args[1])
    
    def test_explain_rule_conflicts_single_rule(self):
        """
        Test explaining rule conflicts for a single rule.
        """
        # Set up mock return values
        self.mock_query_engine.find_conflicting_rules.return_value = [
            {
                "rule1": {"name": "Test Rule", "package": "com.example", "salience": 100},
                "rule2": {"name": "Other Rule", "package": "com.example", "salience": 90},
                "conflict_type": "contradictory_constraints",
                "fact_type": "Customer",
                "salience_difference": 10
            }
        ]
        self.mock_rule_explainer.explain_rule_conflicts.return_value = "Rule conflicts explanation"
        
        # Explain rule conflicts
        rule_name = "Test Rule"
        explanation = self.interface.explain_rule_conflicts(rule_name)
        
        # Check the explanation
        self.assertEqual(explanation, "Rule conflicts explanation")
        
        # Verify mock calls
        self.mock_query_engine.find_conflicting_rules.assert_called_once()
        self.mock_rule_explainer.explain_rule_conflicts.assert_called_once()
        args = self.mock_rule_explainer.explain_rule_conflicts.call_args[0]
        self.assertEqual(args[0], [rule_name])
        self.assertIn("conflicting_rules", args[1])
    
    def test_explain_execution_order(self):
        """
        Test explaining execution order.
        """
        # Set up mock return values
        self.mock_query_engine.find_rule_by_exact_name.return_value = {
            "name": "Test Rule", "package": "com.example", "salience": 100, "id": 1
        }
        self.mock_query_engine.analyze_execution_order.return_value = [
            {
                "name": "Test Rule",
                "package": "com.example",
                "original_salience": 100,
                "effective_salience": 100,
                "rule_type": "high_priority"
            },
            {
                "name": "Other Rule",
                "package": "com.example",
                "original_salience": 90,
                "effective_salience": 90,
                "rule_type": "normal"
            }
        ]
        self.mock_rule_explainer.explain_execution_order.return_value = "Execution order explanation"
        
        # Explain execution order
        rule_names = ["Test Rule", "Other Rule"]
        explanation = self.interface.explain_execution_order(rule_names)
        
        # Check the explanation
        self.assertEqual(explanation, "Execution order explanation")
        
        # Verify mock calls
        self.mock_query_engine.find_rule_by_exact_name.assert_called()
        self.mock_query_engine.analyze_execution_order.assert_called_once()
        self.mock_rule_explainer.explain_execution_order.assert_called_once()
        args = self.mock_rule_explainer.explain_execution_order.call_args[0]
        self.assertEqual(args[0], rule_names)
        self.assertIn("execution_order", args[1])
    
    def test_explain_execution_order_single_rule(self):
        """
        Test explaining execution order for a single rule.
        """
        # Set up mock return values
        self.mock_query_engine.find_rule_by_exact_name.return_value = {
            "name": "Test Rule", "package": "com.example", "salience": 100, "id": 1
        }
        self.mock_query_engine.analyze_execution_order.return_value = [
            {
                "name": "Test Rule",
                "package": "com.example",
                "original_salience": 100,
                "effective_salience": 100,
                "rule_type": "high_priority"
            }
        ]
        self.mock_rule_explainer.explain_execution_order.return_value = "Execution order explanation"
        
        # Explain execution order
        rule_name = "Test Rule"
        explanation = self.interface.explain_execution_order(rule_name)
        
        # Check the explanation
        self.assertEqual(explanation, "Execution order explanation")
        
        # Verify mock calls
        self.mock_query_engine.find_rule_by_exact_name.assert_called_once_with(rule_name)
        self.mock_query_engine.analyze_execution_order.assert_called_once()
        self.mock_rule_explainer.explain_execution_order.assert_called_once()
        args = self.mock_rule_explainer.explain_execution_order.call_args[0]
        self.assertEqual(args[0], [rule_name])
        self.assertIn("execution_order", args[1])
    
    def test_explain_execution_order_all_rules(self):
        """
        Test explaining execution order for all rules.
        """
        # Set up mock return values
        self.mock_query_engine.analyze_execution_order.return_value = [
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
        self.mock_rule_explainer.explain_execution_order.return_value = "Execution order explanation"
        
        # Explain execution order for all rules
        explanation = self.interface.explain_execution_order()
        
        # Check the explanation
        self.assertEqual(explanation, "Execution order explanation")
        
        # Verify mock calls
        self.mock_query_engine.analyze_execution_order.assert_called_once_with(None)
        self.mock_rule_explainer.explain_execution_order.assert_called_once()
        args = self.mock_rule_explainer.explain_execution_order.call_args[0]
        self.assertEqual(args[0], [])
        self.assertIn("execution_order", args[1])


if __name__ == "__main__":
    unittest.main()