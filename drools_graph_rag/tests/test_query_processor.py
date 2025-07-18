"""
Tests for the query processor module.
"""
import unittest
from unittest.mock import MagicMock, patch

from drools_graph_rag.rag.query_processor import QueryProcessor, QueryIntent, QueryTranslator
from drools_graph_rag.query_engine.query_engine import GraphQueryEngine


class TestQueryIntent(unittest.TestCase):
    """
    Test the QueryIntent class.
    """
    
    def test_init(self):
        """
        Test initialization of QueryIntent.
        """
        intent = QueryIntent(QueryIntent.FIND_RULE, {"rule_name": "test"}, 0.9)
        self.assertEqual(intent.intent_type, QueryIntent.FIND_RULE)
        self.assertEqual(intent.entities, {"rule_name": "test"})
        self.assertEqual(intent.confidence, 0.9)
    
    def test_str(self):
        """
        Test string representation of QueryIntent.
        """
        intent = QueryIntent(QueryIntent.FIND_RULE, {"rule_name": "test"}, 0.9)
        self.assertIn("Intent: find_rule", str(intent))
        self.assertIn("Entities: {'rule_name': 'test'}", str(intent))
        self.assertIn("Confidence: 0.90", str(intent))


class TestQueryProcessor(unittest.TestCase):
    """
    Test the QueryProcessor class.
    """
    
    @patch("sentence_transformers.SentenceTransformer")
    def setUp(self, mock_transformer):
        """
        Set up the test environment.
        """
        # Mock the embedding model
        self.mock_model = mock_transformer.return_value
        self.mock_model.encode.return_value = [[0.1, 0.2, 0.3]]
        
        # Create a query processor with the mock model
        self.processor = QueryProcessor(self.mock_model)
        
        # Override the intent embeddings for testing
        self.processor.intent_embeddings = {
            QueryIntent.FIND_RULE: [[0.9, 0.1, 0.1]],
            QueryIntent.EXPLAIN_RULE: [[0.1, 0.9, 0.1]],
            QueryIntent.FIND_DEPENDENCIES: [[0.1, 0.1, 0.9]],
            QueryIntent.FIND_CONFLICTS: [[0.5, 0.5, 0.1]],
            QueryIntent.EXECUTION_ORDER: [[0.5, 0.1, 0.5]],
            QueryIntent.FIND_PATTERNS: [[0.3, 0.3, 0.3]],
        }
    
    def test_extract_intent_rule_based_find_rule(self):
        """
        Test rule-based intent extraction for FIND_RULE.
        """
        query = 'Find rule named "Customer Validation"'
        intent = self.processor._extract_intent_rule_based(query)
        self.assertEqual(intent.intent_type, QueryIntent.FIND_RULE)
        self.assertEqual(intent.entities.get("rule_name"), "Customer Validation")
        self.assertGreaterEqual(intent.confidence, 0.7)
    
    def test_extract_intent_rule_based_explain_rule(self):
        """
        Test rule-based intent extraction for EXPLAIN_RULE.
        """
        query = 'Explain rule "Order Processing"'
        intent = self.processor._extract_intent_rule_based(query)
        self.assertEqual(intent.intent_type, QueryIntent.EXPLAIN_RULE)
        self.assertEqual(intent.entities.get("rule_name"), "Order Processing")
        self.assertGreaterEqual(intent.confidence, 0.7)
    
    def test_extract_intent_rule_based_find_dependencies(self):
        """
        Test rule-based intent extraction for FIND_DEPENDENCIES.
        """
        query = 'What are the dependencies of rule "Customer Validation"?'
        intent = self.processor._extract_intent_rule_based(query)
        self.assertEqual(intent.intent_type, QueryIntent.FIND_DEPENDENCIES)
        self.assertEqual(intent.entities.get("rule_name"), "Customer Validation")
        self.assertGreaterEqual(intent.confidence, 0.7)
    
    def test_extract_intent_rule_based_find_conflicts(self):
        """
        Test rule-based intent extraction for FIND_CONFLICTS.
        """
        query = 'Are there any conflicting rules?'
        intent = self.processor._extract_intent_rule_based(query)
        self.assertEqual(intent.intent_type, QueryIntent.FIND_CONFLICTS)
        self.assertGreaterEqual(intent.confidence, 0.7)
    
    def test_extract_intent_rule_based_execution_order(self):
        """
        Test rule-based intent extraction for EXECUTION_ORDER.
        """
        query = 'What is the execution order of rules?'
        intent = self.processor._extract_intent_rule_based(query)
        self.assertEqual(intent.intent_type, QueryIntent.EXECUTION_ORDER)
        self.assertGreaterEqual(intent.confidence, 0.7)
    
    def test_extract_intent_rule_based_find_patterns(self):
        """
        Test rule-based intent extraction for FIND_PATTERNS.
        """
        query = 'Find unused rules'
        intent = self.processor._extract_intent_rule_based(query)
        self.assertEqual(intent.intent_type, QueryIntent.FIND_PATTERNS)
        self.assertGreaterEqual(intent.confidence, 0.7)
    
    def test_extract_intent_rule_based_unknown(self):
        """
        Test rule-based intent extraction for unknown intent.
        """
        query = 'What is the meaning of life?'
        intent = self.processor._extract_intent_rule_based(query)
        self.assertEqual(intent.intent_type, QueryIntent.UNKNOWN)
        self.assertLessEqual(intent.confidence, 0.1)
    
    @patch("numpy.dot")
    @patch("numpy.linalg.norm")
    def test_extract_intent_embedding_based(self, mock_norm, mock_dot):
        """
        Test embedding-based intent extraction.
        """
        # Mock numpy functions
        mock_dot.return_value = [0.1, 0.8, 0.3, 0.2, 0.1, 0.1]
        mock_norm.return_value = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        
        query = 'Tell me about rule execution'
        intent = self.processor._extract_intent_embedding_based(query)
        self.assertEqual(intent.intent_type, QueryIntent.EXPLAIN_RULE)
        self.assertGreaterEqual(intent.confidence, 0.7)
    
    def test_extract_entities_rule_name(self):
        """
        Test entity extraction for rule names.
        """
        # Test with quoted rule name
        query = 'Find rule "Customer Validation"'
        entities = self.processor._extract_entities(query, QueryIntent.FIND_RULE)
        self.assertEqual(entities.get("rule_name"), "Customer Validation")
        
        # Test with rule name after keyword
        query = 'Find rule named Customer Validation'
        entities = self.processor._extract_entities(query, QueryIntent.FIND_RULE)
        self.assertEqual(entities.get("rule_name"), "Customer Validation")
    
    def test_extract_entities_class_name(self):
        """
        Test entity extraction for class names.
        """
        query = 'Find rules using class Customer'
        entities = self.processor._extract_entities(query, QueryIntent.FIND_RULE)
        self.assertEqual(entities.get("class_name"), "Customer")
    
    def test_extract_entities_complexity_threshold(self):
        """
        Test entity extraction for complexity threshold.
        """
        query = 'Find complex rules with complexity threshold of 10'
        entities = self.processor._extract_entities(query, QueryIntent.FIND_PATTERNS)
        self.assertEqual(entities.get("complexity_threshold"), 10)
    
    def test_process_query_rule_based(self):
        """
        Test processing a query using rule-based intent extraction.
        """
        query = 'Find rule named "Customer Validation"'
        intent = self.processor.process_query(query)
        self.assertEqual(intent.intent_type, QueryIntent.FIND_RULE)
        self.assertEqual(intent.entities.get("rule_name"), "Customer Validation")
        self.assertGreaterEqual(intent.confidence, 0.7)
    
    @patch("numpy.dot")
    @patch("numpy.linalg.norm")
    def test_process_query_embedding_based(self, mock_norm, mock_dot):
        """
        Test processing a query using embedding-based intent extraction.
        """
        # Mock numpy functions to force embedding-based extraction
        mock_dot.return_value = [0.1, 0.9, 0.3, 0.2, 0.1, 0.1]
        mock_norm.return_value = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        
        query = 'What does this rule do?'
        intent = self.processor.process_query(query)
        self.assertEqual(intent.intent_type, QueryIntent.EXPLAIN_RULE)
        self.assertGreaterEqual(intent.confidence, 0.7)


class TestQueryTranslator(unittest.TestCase):
    """
    Test the QueryTranslator class.
    """
    
    def setUp(self):
        """
        Set up the test environment.
        """
        # Create a mock query engine
        self.mock_engine = MagicMock(spec=GraphQueryEngine)
        
        # Create a query translator with the mock engine
        self.translator = QueryTranslator(self.mock_engine)
    
    def test_translate_intent_find_rule_by_name(self):
        """
        Test translating FIND_RULE intent with rule name.
        """
        # Set up mock return values
        self.mock_engine.find_rules_by_name.return_value = [
            {"name": "Test Rule", "package": "com.example", "salience": 100, "id": 1}
        ]
        
        # Create intent
        intent = QueryIntent(QueryIntent.FIND_RULE, {"rule_name": "Test"}, 0.9)
        
        # Translate intent
        result = self.translator.translate_intent(intent)
        
        # Check result
        self.assertEqual(result["intent"], QueryIntent.FIND_RULE)
        self.assertIn("rules_by_name", result["results"])
        self.assertEqual(len(result["results"]["rules_by_name"]), 1)
        self.assertEqual(result["results"]["rules_by_name"][0]["name"], "Test Rule")
        
        # Verify mock calls
        self.mock_engine.find_rules_by_name.assert_called_once_with(".*Test.*")
    
    def test_translate_intent_find_rule_by_class(self):
        """
        Test translating FIND_RULE intent with class name.
        """
        # Set up mock return values
        self.mock_engine.find_rules_by_class_reference.return_value = [
            {"name": "Test Rule", "package": "com.example", "salience": 100, "id": 1}
        ]
        
        # Create intent
        intent = QueryIntent(QueryIntent.FIND_RULE, {"class_name": "Customer"}, 0.9)
        
        # Translate intent
        result = self.translator.translate_intent(intent)
        
        # Check result
        self.assertEqual(result["intent"], QueryIntent.FIND_RULE)
        self.assertIn("rules_by_class", result["results"])
        self.assertEqual(len(result["results"]["rules_by_class"]), 1)
        self.assertEqual(result["results"]["rules_by_class"][0]["name"], "Test Rule")
        
        # Verify mock calls
        self.mock_engine.find_rules_by_class_reference.assert_called_once_with("Customer")
    
    def test_translate_intent_find_rule_all(self):
        """
        Test translating FIND_RULE intent with no entities.
        """
        # Set up mock return values
        self.mock_engine.get_all_rules.return_value = [
            {"name": "Rule 1", "package": "com.example", "salience": 100, "id": 1},
            {"name": "Rule 2", "package": "com.example", "salience": 90, "id": 2}
        ]
        
        # Create intent
        intent = QueryIntent(QueryIntent.FIND_RULE, {}, 0.9)
        
        # Translate intent
        result = self.translator.translate_intent(intent)
        
        # Check result
        self.assertEqual(result["intent"], QueryIntent.FIND_RULE)
        self.assertIn("all_rules", result["results"])
        self.assertEqual(len(result["results"]["all_rules"]), 2)
        
        # Verify mock calls
        self.mock_engine.get_all_rules.assert_called_once()
    
    def test_translate_intent_explain_rule(self):
        """
        Test translating EXPLAIN_RULE intent.
        """
        # Set up mock return values
        self.mock_engine.find_rule_by_exact_name.return_value = {
            "name": "Test Rule", "package": "com.example", "salience": 100, "id": 1
        }
        self.mock_engine.get_rule_details.return_value = {
            "name": "Test Rule", "package": "com.example", "salience": 100,
            "conditions": [], "actions": []
        }
        self.mock_engine.find_rule_dependencies.return_value = {
            "rule": {"name": "Test Rule", "package": "com.example"},
            "parents": [], "depends_on": [], "dependent_rules": []
        }
        
        # Create intent
        intent = QueryIntent(QueryIntent.EXPLAIN_RULE, {"rule_name": "Test Rule"}, 0.9)
        
        # Translate intent
        result = self.translator.translate_intent(intent)
        
        # Check result
        self.assertEqual(result["intent"], QueryIntent.EXPLAIN_RULE)
        self.assertIn("rule_details", result["results"])
        self.assertIn("rule_dependencies", result["results"])
        
        # Verify mock calls
        self.mock_engine.find_rule_by_exact_name.assert_called_once_with("Test Rule")
        self.mock_engine.get_rule_details.assert_called_once_with(1)
        self.mock_engine.find_rule_dependencies.assert_called_once_with("Test Rule", "com.example")
    
    def test_translate_intent_find_dependencies(self):
        """
        Test translating FIND_DEPENDENCIES intent.
        """
        # Set up mock return values
        self.mock_engine.find_rule_by_exact_name.return_value = {
            "name": "Test Rule", "package": "com.example", "salience": 100, "id": 1
        }
        self.mock_engine.find_rule_dependencies.return_value = {
            "rule": {"name": "Test Rule", "package": "com.example"},
            "parents": [], "depends_on": [], "dependent_rules": []
        }
        
        # Create intent
        intent = QueryIntent(QueryIntent.FIND_DEPENDENCIES, {"rule_name": "Test Rule"}, 0.9)
        
        # Translate intent
        result = self.translator.translate_intent(intent)
        
        # Check result
        self.assertEqual(result["intent"], QueryIntent.FIND_DEPENDENCIES)
        self.assertIn("rule_dependencies", result["results"])
        
        # Verify mock calls
        self.mock_engine.find_rule_by_exact_name.assert_called_once_with("Test Rule")
        self.mock_engine.find_rule_dependencies.assert_called_once_with("Test Rule", "com.example")
    
    def test_translate_intent_find_dependencies_circular(self):
        """
        Test translating FIND_DEPENDENCIES intent for circular dependencies.
        """
        # Set up mock return values
        self.mock_engine.find_circular_dependencies.return_value = [
            {
                "from_rule": {"name": "Rule 1", "package": "com.example"},
                "to_rule": {"name": "Rule 2", "package": "com.example"},
                "shared_classes": ["Customer"]
            }
        ]
        
        # Create intent
        intent = QueryIntent(QueryIntent.FIND_DEPENDENCIES, {}, 0.9)
        
        # Translate intent
        result = self.translator.translate_intent(intent)
        
        # Check result
        self.assertEqual(result["intent"], QueryIntent.FIND_DEPENDENCIES)
        self.assertIn("circular_dependencies", result["results"])
        self.assertEqual(len(result["results"]["circular_dependencies"]), 1)
        
        # Verify mock calls
        self.mock_engine.find_circular_dependencies.assert_called_once()
    
    def test_translate_intent_find_conflicts(self):
        """
        Test translating FIND_CONFLICTS intent.
        """
        # Set up mock return values
        self.mock_engine.find_conflicting_rules.return_value = [
            {
                "rule1": {"name": "Rule 1", "package": "com.example", "salience": 100},
                "rule2": {"name": "Rule 2", "package": "com.example", "salience": 90},
                "conflict_type": "potential_action_conflict",
                "fact_type": "Customer",
                "salience_difference": 10,
                "details": {}
            }
        ]
        
        # Create intent
        intent = QueryIntent(QueryIntent.FIND_CONFLICTS, {}, 0.9)
        
        # Translate intent
        result = self.translator.translate_intent(intent)
        
        # Check result
        self.assertEqual(result["intent"], QueryIntent.FIND_CONFLICTS)
        self.assertIn("conflicting_rules", result["results"])
        self.assertEqual(len(result["results"]["conflicting_rules"]), 1)
        
        # Verify mock calls
        self.mock_engine.find_conflicting_rules.assert_called_once()
    
    def test_translate_intent_execution_order(self):
        """
        Test translating EXECUTION_ORDER intent.
        """
        # Set up mock return values
        self.mock_engine.analyze_execution_order.return_value = [
            {
                "name": "Rule 1", "package": "com.example", "original_salience": 100,
                "effective_salience": 100, "depends_on": [], "dependency_count": 0,
                "rule_type": "high_priority"
            },
            {
                "name": "Rule 2", "package": "com.example", "original_salience": 90,
                "effective_salience": 90, "depends_on": [], "dependency_count": 0,
                "rule_type": "normal"
            }
        ]
        
        # Create intent
        intent = QueryIntent(QueryIntent.EXECUTION_ORDER, {}, 0.9)
        
        # Translate intent
        result = self.translator.translate_intent(intent)
        
        # Check result
        self.assertEqual(result["intent"], QueryIntent.EXECUTION_ORDER)
        self.assertIn("execution_order", result["results"])
        self.assertEqual(len(result["results"]["execution_order"]), 2)
        
        # Verify mock calls
        self.mock_engine.analyze_execution_order.assert_called_once()
    
    def test_translate_intent_find_patterns(self):
        """
        Test translating FIND_PATTERNS intent.
        """
        # Set up mock return values
        self.mock_engine.find_unused_rules.return_value = [
            {"name": "Unused Rule", "package": "com.example", "salience": 100, "id": 1}
        ]
        self.mock_engine.find_circular_dependencies.return_value = []
        self.mock_engine.find_complex_rules.return_value = [
            {
                "name": "Complex Rule", "package": "com.example", "salience": 100, "id": 2,
                "condition_count": 5, "constraint_count": 10, "action_count": 3,
                "class_count": 2, "total_complexity": 20
            }
        ]
        self.mock_engine.find_conflicting_rules.return_value = []
        
        # Create intent
        intent = QueryIntent(QueryIntent.FIND_PATTERNS, {}, 0.9)
        
        # Translate intent
        result = self.translator.translate_intent(intent)
        
        # Check result
        self.assertEqual(result["intent"], QueryIntent.FIND_PATTERNS)
        self.assertIn("unused_rules", result["results"])
        self.assertIn("circular_dependencies", result["results"])
        self.assertIn("complex_rules", result["results"])
        self.assertIn("conflicting_rules", result["results"])
        
        # Verify mock calls
        self.mock_engine.find_unused_rules.assert_called_once()
        self.mock_engine.find_circular_dependencies.assert_called_once()
        self.mock_engine.find_complex_rules.assert_called_once_with(5)
        self.mock_engine.find_conflicting_rules.assert_called_once()
    
    def test_translate_intent_unknown(self):
        """
        Test translating unknown intent.
        """
        # Create intent
        intent = QueryIntent(QueryIntent.UNKNOWN, {}, 0.1)
        
        # Translate intent
        result = self.translator.translate_intent(intent)
        
        # Check result
        self.assertIn("error", result)
        self.assertIn("Could not understand", result["error"])


if __name__ == "__main__":
    unittest.main()