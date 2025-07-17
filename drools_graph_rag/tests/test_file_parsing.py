"""
Tests for the file parsing logic in the Drools parser.
"""
import os
import sys
import tempfile
from pathlib import Path
import unittest

# Add the parent directory to the path so we can import the package
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from drools_graph_rag.parser.parser import DroolsParser


class TestFileParsing(unittest.TestCase):
    """Test cases for file parsing logic."""

    def setUp(self):
        """Set up test environment."""
        self.parser = DroolsParser()
        self.test_dir = tempfile.mkdtemp()
        
        # Create test files
        self.valid_file = os.path.join(self.test_dir, "valid.drl")
        with open(self.valid_file, "w") as f:
            f.write("""
package com.example.rules

import com.example.model.Customer;
import com.example.model.ValidationResult;

global ValidationResult validationResult;

rule "Test Rule"
    when
        $customer : Customer(age < 18)
    then
        validationResult.addError("Customer must be at least 18 years old");
end
            """)
        
        self.empty_file = os.path.join(self.test_dir, "empty.drl")
        with open(self.empty_file, "w") as f:
            f.write("")
        
        self.invalid_file = os.path.join(self.test_dir, "invalid.drl")
        with open(self.invalid_file, "w") as f:
            f.write("""
package com.example.rules

This is not a valid Drools file.
            """)
        
        # Create subdirectory with more files
        self.sub_dir = os.path.join(self.test_dir, "subdir")
        os.makedirs(self.sub_dir)
        
        self.sub_file = os.path.join(self.sub_dir, "sub.drl")
        with open(self.sub_file, "w") as f:
            f.write("""
package com.example.subrules

rule "Sub Rule"
    when
        eval(true)
    then
        System.out.println("Sub rule executed");
end
            """)
        
        # Create a non-drl file
        self.non_drl_file = os.path.join(self.test_dir, "not_drl.txt")
        with open(self.non_drl_file, "w") as f:
            f.write("This is not a .drl file")

    def tearDown(self):
        """Clean up test environment."""
        # Remove test files
        for file_path in [self.valid_file, self.empty_file, self.invalid_file, self.sub_file, self.non_drl_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)
        
        # Remove directories
        if os.path.exists(self.sub_dir):
            os.rmdir(self.sub_dir)
        if os.path.exists(self.test_dir):
            os.rmdir(self.test_dir)

    def test_parse_valid_file(self):
        """Test parsing a valid Drools file."""
        rule_file = self.parser.parse_file(self.valid_file)
        self.assertEqual(rule_file.package, "com.example.rules")
        self.assertEqual(len(rule_file.imports), 2)
        self.assertEqual(len(rule_file.globals), 1)
        self.assertEqual(len(rule_file.rules), 1)
        self.assertEqual(rule_file.rules[0].name, "Test Rule")

    def test_parse_empty_file(self):
        """Test parsing an empty file."""
        rule_file = self.parser.parse_file(self.empty_file)
        self.assertEqual(rule_file.package, "")
        self.assertEqual(len(rule_file.imports), 0)
        self.assertEqual(len(rule_file.globals), 0)
        self.assertEqual(len(rule_file.rules), 0)

    def test_parse_invalid_file(self):
        """Test parsing an invalid file."""
        rule_file = self.parser.parse_file(self.invalid_file)
        # The package pattern will match the first line with "package" in it
        self.assertTrue(rule_file.package.startswith("com.example.rules"))
        self.assertEqual(len(rule_file.imports), 0)
        self.assertEqual(len(rule_file.globals), 0)
        self.assertEqual(len(rule_file.rules), 0)

    def test_parse_nonexistent_file(self):
        """Test parsing a nonexistent file."""
        with self.assertRaises(FileNotFoundError):
            self.parser.parse_file(os.path.join(self.test_dir, "nonexistent.drl"))

    def test_parse_directory(self):
        """Test parsing a directory."""
        rule_files = self.parser.parse_directory(self.test_dir)
        # The parser finds all 4 .drl files (including the one in the subdirectory)
        self.assertEqual(len(rule_files), 4)  # valid.drl, empty.drl, invalid.drl, subdir/sub.drl
        
        # Check that we found the right files
        file_paths = [os.path.basename(rf.path) for rf in rule_files]
        self.assertIn("valid.drl", file_paths)
        self.assertIn("empty.drl", file_paths)
        self.assertIn("invalid.drl", file_paths)
        self.assertIn("sub.drl", file_paths)

    def test_parse_directory_recursive(self):
        """Test parsing a directory recursively."""
        rule_files = self.parser.parse_directory(self.test_dir, recursive=True)
        self.assertEqual(len(rule_files), 4)  # valid.drl, empty.drl, invalid.drl, subdir/sub.drl
        
        # Check that we found the right files
        file_paths = [rf.path for rf in rule_files]
        self.assertIn(self.valid_file, file_paths)
        self.assertIn(self.empty_file, file_paths)
        self.assertIn(self.invalid_file, file_paths)
        self.assertIn(self.sub_file, file_paths)

    def test_parse_directory_non_recursive(self):
        """Test parsing a directory non-recursively."""
        rule_files = self.parser.parse_directory(self.test_dir, recursive=False)
        self.assertEqual(len(rule_files), 3)  # valid.drl, empty.drl, invalid.drl
        
        # Check that we found the right files
        file_paths = [rf.path for rf in rule_files]
        self.assertIn(self.valid_file, file_paths)
        self.assertIn(self.empty_file, file_paths)
        self.assertIn(self.invalid_file, file_paths)
        self.assertNotIn(self.sub_file, file_paths)

    def test_parse_directory_with_pattern(self):
        """Test parsing a directory with a specific file pattern."""
        # Create a different file extension
        custom_file = os.path.join(self.test_dir, "custom.rules")
        with open(custom_file, "w") as f:
            f.write("""
package com.example.custom

rule "Custom Rule"
    when
        eval(true)
    then
        System.out.println("Custom rule executed");
end
            """)
        
        try:
            # Test with default pattern (*.drl)
            rule_files = self.parser.parse_directory(self.test_dir)
            # The parser finds all 4 .drl files (including the one in the subdirectory)
            self.assertEqual(len(rule_files), 4)
            
            # Test with custom pattern
            rule_files = self.parser.parse_directory(self.test_dir, file_pattern="*.rules")
            self.assertEqual(len(rule_files), 1)
            self.assertEqual(os.path.basename(rule_files[0].path), "custom.rules")
            
            # Test with multiple patterns
            rule_files = self.parser.parse_directory(self.test_dir, file_pattern="*.[dr]*")
            self.assertEqual(len(rule_files), 5)  # 4 .drl files + 1 .rules file
        
        finally:
            # Clean up
            if os.path.exists(custom_file):
                os.unlink(custom_file)

    def test_parse_nonexistent_directory(self):
        """Test parsing a nonexistent directory."""
        rule_files = self.parser.parse_directory(os.path.join(self.test_dir, "nonexistent"))
        self.assertEqual(len(rule_files), 0)

    def test_parse_file_as_directory(self):
        """Test parsing a file as a directory."""
        rule_files = self.parser.parse_directory(self.valid_file)
        self.assertEqual(len(rule_files), 0)
        
    def test_is_drools_file(self):
        """Test the is_drools_file method."""
        # Valid Drools file
        self.assertTrue(self.parser.is_drools_file(self.valid_file))
        
        # Empty file
        self.assertFalse(self.parser.is_drools_file(self.empty_file))
        
        # Invalid file (has package but no rules)
        self.assertTrue(self.parser.is_drools_file(self.invalid_file))
        
        # Non-DRL file
        self.assertFalse(self.parser.is_drools_file(self.non_drl_file))
        
        # Nonexistent file
        self.assertFalse(self.parser.is_drools_file(os.path.join(self.test_dir, "nonexistent.drl")))


if __name__ == "__main__":
    unittest.main()