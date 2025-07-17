"""
Tests for the error handling functionality in the Drools parser.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add the parent directory to the path so we can import the package
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from drools_graph_rag.parser.parser import DroolsParser
from drools_graph_rag.parser.error_handler import ParserErrorHandler
from drools_graph_rag.parser.exceptions import (
    DroolsParserError,
    FileParsingError,
    RuleParsingError,
    MalformedRuleError,
)


class TestErrorHandling(unittest.TestCase):
    """Test cases for error handling in the parser."""

    def setUp(self):
        """Set up test environment."""
        self.parser = DroolsParser(log_level="DEBUG")
        self.test_dir = tempfile.mkdtemp()
        
        # Create test files with various errors
        self.malformed_rule_file = os.path.join(self.test_dir, "malformed_rule.drl")
        with open(self.malformed_rule_file, "w") as f:
            f.write("""
package com.example.rules

import com.example.model.Customer;

rule "Missing When Section"
    salience 100
    // Missing 'when' section
    then
        System.out.println("This rule is malformed");
end

rule "Missing Then Section"
    when
        $customer : Customer(age < 18)
    // Missing 'then' section
end

rule "Missing End Statement"
    when
        $customer : Customer(age < 18)
    then
        System.out.println("This rule is missing an end statement");
// Missing 'end' statement

rule "Valid Rule"
    when
        $customer : Customer(age < 18)
    then
        System.out.println("This rule is valid");
end
            """)
        
        self.malformed_constraint_file = os.path.join(self.test_dir, "malformed_constraint.drl")
        with open(self.malformed_constraint_file, "w") as f:
            f.write("""
package com.example.rules

import com.example.model.Customer;

rule "Malformed Constraint"
    when
        $customer : Customer(age < "not a number")
        $customer : Customer(invalid constraint syntax)
    then
        System.out.println("This rule has malformed constraints");
end
            """)
        
        self.syntax_error_file = os.path.join(self.test_dir, "syntax_error.drl")
        with open(self.syntax_error_file, "w") as f:
            f.write("""
package com.example.rules

import com.example.model.Customer

// Missing semicolon above

global ValidationResult validationResult

// Missing semicolon above

rule "Syntax Error Rule"
    when
        $customer : Customer(age < 18)
    then
        validationResult.addError("Error")
end
            """)
        
        # Create a directory with multiple files for testing directory parsing
        self.multi_file_dir = os.path.join(self.test_dir, "multi")
        os.makedirs(self.multi_file_dir)
        
        self.valid_file = os.path.join(self.multi_file_dir, "valid.drl")
        with open(self.valid_file, "w") as f:
            f.write("""
package com.example.rules

rule "Valid Rule"
    when
        eval(true)
    then
        System.out.println("Valid rule");
end
            """)
        
        self.error_file = os.path.join(self.multi_file_dir, "error.drl")
        with open(self.error_file, "w") as f:
            f.write("""
package com.example.rules

rule "Error Rule
    // Missing closing quote
    when
        eval(true)
    then
        System.out.println("Error rule");
end
            """)

    def tearDown(self):
        """Clean up test environment."""
        # Remove test files
        for file_path in [self.malformed_rule_file, self.malformed_constraint_file, 
                         self.syntax_error_file, self.valid_file, self.error_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)
        
        # Remove directories
        if os.path.exists(self.multi_file_dir):
            os.rmdir(self.multi_file_dir)
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)

    def test_malformed_rule_handling(self):
        """Test handling of malformed rules."""
        # Parse file with malformed rules
        rule_file = self.parser.parse_file(self.malformed_rule_file)
        
        # Check that error handler recorded errors
        error_summary = self.parser.error_handler.get_error_summary()
        self.assertGreater(error_summary["total"], 0)
        self.assertGreater(error_summary["counts"]["rule"], 0)
        
        # We expect only the valid rule to be parsed successfully
        valid_rules = [rule for rule in rule_file.rules if rule.name == "Valid Rule"]
        self.assertEqual(len(valid_rules), 1)

    def test_malformed_constraint_handling(self):
        """Test handling of malformed constraints."""
        # Parse file with malformed constraints
        rule_file = self.parser.parse_file(self.malformed_constraint_file)
        
        # Check that error handler recorded errors
        error_summary = self.parser.error_handler.get_error_summary()
        self.assertGreater(error_summary["total"], 0)
        
        # Check that the rule was still parsed despite constraint errors
        self.assertGreaterEqual(len(rule_file.rules), 1)
        rule_names = [rule.name for rule in rule_file.rules]
        self.assertIn("Malformed Constraint", rule_names)

    def test_syntax_error_handling(self):
        """Test handling of syntax errors."""
        # Parse file with syntax errors
        rule_file = self.parser.parse_file(self.syntax_error_file)
        
        # For syntax errors, we might not get errors in the error handler
        # but we should still be able to parse the rule
        self.assertGreaterEqual(len(rule_file.rules), 1)
        rule_names = [rule.name for rule in rule_file.rules]
        self.assertIn("Syntax Error Rule", rule_names)

    def test_directory_error_handling(self):
        """Test error handling when parsing a directory."""
        # First, let's create a file with a syntax error that will definitely cause an error
        error_file_path = os.path.join(self.multi_file_dir, "definite_error.drl")
        with open(error_file_path, "w") as f:
            f.write("""
package com.example.rules

rule "Malformed Rule
    // Missing closing quote and other syntax
    when
        $customer : Customer(
    then
        System.out.println("This will cause an error");
end
            """)
        
        try:
            # Parse directory with both valid and error files
            rule_files = self.parser.parse_directory(self.multi_file_dir)
            
            # Check that valid files were still parsed
            self.assertGreaterEqual(len(rule_files), 1)  # At least the valid file should be parsed
            
            # Check that valid rules were extracted from valid files
            valid_rules = []
            for rf in rule_files:
                for rule in rf.rules:
                    if rule.name == "Valid Rule":
                        valid_rules.append(rule)
            
            self.assertGreaterEqual(len(valid_rules), 1)  # At least the valid rule should be parsed
        finally:
            # Clean up the additional file
            if os.path.exists(error_file_path):
                os.unlink(error_file_path)

    def test_error_handler_reset(self):
        """Test that error handler resets between operations."""
        # Parse file with errors
        self.parser.parse_file(self.malformed_rule_file)
        
        # Check that errors were recorded
        error_summary1 = self.parser.error_handler.get_error_summary()
        self.assertGreater(error_summary1["total"], 0)
        
        # Reset error handler
        self.parser.error_handler.reset_counts()
        
        # Check that errors were reset
        error_summary2 = self.parser.error_handler.get_error_summary()
        self.assertEqual(error_summary2["total"], 0)

    def test_error_details(self):
        """Test that error details are properly recorded."""
        # Parse file with malformed rules
        self.parser.parse_file(self.malformed_rule_file)
        
        # Check error details
        error_summary = self.parser.error_handler.get_error_summary()
        errors = error_summary["errors"]
        
        # Check that we have error details
        self.assertGreater(len(errors), 0)
        
        # Check that error details include required fields
        for error in errors:
            self.assertIn("type", error)
            self.assertIn("message", error)
            self.assertIn("file_path", error)
            self.assertIn("recoverable", error)


if __name__ == "__main__":
    unittest.main()