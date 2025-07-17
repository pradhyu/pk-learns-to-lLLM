"""
Parser for Drools rule files (.drl).
"""
import logging
import os
import re
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from drools_graph_rag.parser.error_handler import (
    ParserErrorHandler,
    extract_line_number,
    find_line_for_pattern,
    extract_context,
)
from drools_graph_rag.parser.exceptions import (
    ActionParsingError,
    ConditionParsingError,
    DeclaredTypeParsingError,
    DroolsParserError,
    FileParsingError,
    FunctionParsingError,
    MalformedActionError,
    MalformedConditionError,
    MalformedDeclaredTypeError,
    MalformedFunctionError,
    MalformedQueryError,
    MalformedRuleError,
    QueryParsingError,
    RuleParsingError,
)
from drools_graph_rag.parser.models import (
    Action,
    Condition,
    Constraint,
    DeclaredType,
    Field,
    Function,
    Global,
    Import,
    Parameter,
    Query,
    Rule,
    RuleFile,
)

# Main logger for the parser
logger = logging.getLogger(__name__)


class DroolsParser:
    """
    Parser for Drools rule files (.drl).
    """

    def __init__(self, log_level: str = "INFO") -> None:
        """
        Initialize the parser.
        
        Args:
            log_level: The logging level to use.
        """
        # Initialize error handler
        self.error_handler = ParserErrorHandler(log_level)
        
        # Regular expressions for parsing
        self.package_pattern = re.compile(r'package\s+([^;]+);?')
        self.import_pattern = re.compile(r'import\s+([^;]+);?')
        self.global_pattern = re.compile(r'global\s+([^\s]+)\s+([^;]+);?')
        self.rule_pattern = re.compile(r'rule\s+"([^"]+)"')
        self.extends_pattern = re.compile(r'extends\s+"([^"]+)"')
        self.salience_pattern = re.compile(r'salience\s+(-?\d+)')
        self.attribute_pattern = re.compile(r'\s+(\w+)\s+([^,]+)')
        self.when_pattern = re.compile(r'\s+when')
        self.then_pattern = re.compile(r'\s+then')
        self.end_pattern = re.compile(r'end')
        self.condition_pattern = re.compile(r'\s+\$?(\w+)\s*:\s*([^\(]+)\(([^\)]*)\)')
        self.constraint_pattern = re.compile(r'(\w+)\s*([=!<>]+|==|!=|<=|>=|matches)\s*([^,&\)]+)')
        self.action_method_pattern = re.compile(r'\s+([^.;]+)\.(\w+)\(([^;]*)\);?')
        self.action_assignment_pattern = re.compile(r'\s+([^=;]+)\s*=\s*([^;]+);?')
        self.action_statement_pattern = re.compile(r'\s+([^;]+);?')
        
        # Additional patterns for advanced parsing
        self.query_pattern = re.compile(r'query\s+"([^"]+)"')
        self.function_pattern = re.compile(r'function\s+([^\s(]+)\s+([^\s(]+)\s*\(([^)]*)\)')
        self.declare_pattern = re.compile(r'declare\s+([^\s]+)')
        self.end_declare_pattern = re.compile(r'end\s*declare')
        
        # Pattern to identify a Drools file
        self.drools_identifier_patterns = [
            self.package_pattern,
            self.import_pattern,
            self.global_pattern,
            self.rule_pattern,
            self.query_pattern,
            self.function_pattern,
            self.declare_pattern
        ]
        
    def is_drools_file(self, file_path: str) -> bool:
        """
        Check if a file is likely to be a Drools rule file.
        
        Args:
            file_path: Path to the file to check.
            
        Returns:
            True if the file is likely to be a Drools rule file, False otherwise.
        """
        try:
            # Check file extension
            if not file_path.lower().endswith('.drl'):
                return False
                
            # Read the first few KB of the file to check for Drools patterns
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read(4096)  # Read first 4KB
                
            # Check for common Drools patterns
            for pattern in self.drools_identifier_patterns:
                if pattern.search(content):
                    return True
                    
            return False
        except Exception as e:
            logger.warning(f"Error checking if {file_path} is a Drools file: {e}")
            return False

    def parse_directory(self, directory_path: Union[str, Path], recursive: bool = True, file_pattern: str = "*.drl", validate_files: bool = True) -> List[RuleFile]:
        """
        Parse all .drl files in a directory and return a list of RuleFile objects.

        Args:
            directory_path: Path to the directory containing .drl files.
            recursive: Whether to scan subdirectories recursively.
            file_pattern: File pattern to match (default: "*.drl").
            validate_files: Whether to validate that files are Drools files before parsing.

        Returns:
            A list of RuleFile objects representing the parsed files.
            
        Raises:
            FileParsingError: If there's an error scanning the directory.
        """
        logger.info(f"Parsing directory: {directory_path} (recursive={recursive}, pattern={file_pattern}, validate={validate_files})")
        
        # Reset error handler for this operation
        self.error_handler.reset_counts()
        
        if isinstance(directory_path, str):
            directory_path = Path(directory_path)
        
        if not directory_path.exists():
            logger.error(f"Directory {directory_path} does not exist")
            return []
        
        if not directory_path.is_dir():
            logger.error(f"{directory_path} is not a directory")
            return []
        
        rule_files = []
        
        try:
            # Find all matching files in the directory
            pattern = "**/" + file_pattern if recursive else file_pattern
            matching_files = list(directory_path.glob(pattern))
            
            if not matching_files:
                logger.warning(f"No files matching '{file_pattern}' found in {directory_path}")
                return []
            
            logger.info(f"Found {len(matching_files)} files matching '{file_pattern}'")
            
            # Filter files if validation is enabled
            if validate_files and file_pattern != "*.drl":
                valid_files = []
                for file_path in matching_files:
                    if self.is_drools_file(str(file_path)):
                        valid_files.append(file_path)
                    else:
                        logger.debug(f"Skipping non-Drools file: {file_path}")
                
                if len(valid_files) < len(matching_files):
                    logger.info(f"Filtered out {len(matching_files) - len(valid_files)} non-Drools files")
                
                matching_files = valid_files
            
            # Parse each file
            for file_path in matching_files:
                try:
                    logger.debug(f"Parsing file: {file_path}")
                    rule_file = self.parse_file(str(file_path))
                    rule_files.append(rule_file)
                    logger.debug(f"Successfully parsed {file_path}")
                except FileNotFoundError as e:
                    self.error_handler.handle_error(
                        e, 
                        error_type="file", 
                        file_path=str(file_path),
                        context="File not found during directory parsing"
                    )
                except PermissionError as e:
                    self.error_handler.handle_error(
                        e, 
                        error_type="file", 
                        file_path=str(file_path),
                        context="Permission denied during directory parsing"
                    )
                except DroolsParserError as e:
                    self.error_handler.handle_error(
                        e, 
                        error_type="file", 
                        file_path=str(file_path),
                        context="Parser error during directory parsing"
                    )
                except Exception as e:
                    self.error_handler.handle_error(
                        e, 
                        error_type="file", 
                        file_path=str(file_path),
                        context="Unexpected error during directory parsing",
                        recoverable=True
                    )
                    # Continue with other files
            
            # Log summary of parsing results
            error_summary = self.error_handler.get_error_summary()
            if error_summary["total"] > 0:
                self.error_handler.log_error_summary()
            else:
                logger.info(f"Successfully parsed all {len(matching_files)} files")
            
            return rule_files
        
        except Exception as e:
            self.error_handler.handle_error(
                e, 
                error_type="file", 
                file_path=str(directory_path),
                context="Error scanning directory",
                recoverable=False
            )
            raise FileParsingError(f"Error scanning directory {directory_path}: {str(e)}")
    
    def parse_file(self, file_path: str) -> RuleFile:
        """
        Parse a .drl file and return a RuleFile object.

        Args:
            file_path: Path to the .drl file.

        Returns:
            A RuleFile object representing the parsed file.

        Raises:
            FileNotFoundError: If the file does not exist.
            PermissionError: If the file cannot be read due to permissions.
            FileParsingError: If there's an error parsing the file.
            DroolsParserError: Base class for all parser errors.
        """
        logger.info(f"Parsing file: {file_path}")
        
        # Reset error handler for this operation
        self.error_handler.reset_counts()
        
        # Validate file path
        if not os.path.exists(file_path):
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        if not os.path.isfile(file_path):
            error_msg = f"Not a file: {file_path}"
            logger.error(error_msg)
            raise FileParsingError(error_msg, file_path)
        
        # Check file extension
        if not file_path.lower().endswith('.drl'):
            logger.warning(f"File {file_path} does not have .drl extension, but attempting to parse anyway")
        
        try:
            # Read file content
            content = ""
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
            except UnicodeDecodeError:
                # Try with different encoding if UTF-8 fails
                logger.warning(f"UTF-8 decoding failed for {file_path}, trying with latin-1")
                try:
                    with open(file_path, 'r', encoding='latin-1') as file:
                        content = file.read()
                except UnicodeDecodeError as e:
                    error_msg = f"Failed to decode file with UTF-8 and latin-1 encodings"
                    self.error_handler.handle_error(
                        e, 
                        error_type="file", 
                        file_path=file_path,
                        context="Failed to decode file with multiple encodings",
                        recoverable=False
                    )
                    raise FileParsingError(error_msg, file_path) from e
            except PermissionError as e:
                error_msg = f"Permission denied when reading file"
                self.error_handler.handle_error(
                    e, 
                    error_type="file", 
                    file_path=file_path,
                    context="Permission denied when reading file",
                    recoverable=False
                )
                raise PermissionError(error_msg) from e
            except IOError as e:
                error_msg = f"IO error when reading file"
                self.error_handler.handle_error(
                    e, 
                    error_type="file", 
                    file_path=file_path,
                    context="IO error when reading file",
                    recoverable=False
                )
                raise FileParsingError(error_msg, file_path) from e
            
            # Check if file is empty
            if not content.strip():
                logger.warning(f"File {file_path} is empty")
                # Return an empty RuleFile
                return RuleFile(path=file_path, package="")
            
            # Parse package
            package_match = self.package_pattern.search(content)
            package = ""
            if package_match:
                try:
                    package = package_match.group(1).strip()
                    # Make sure we only get the package name, not any following content
                    if package and "\n" in package:
                        package = package.split("\n")[0].strip()
                except Exception as e:
                    self.error_handler.handle_error(
                        e, 
                        error_type="file", 
                        file_path=file_path,
                        context="Error parsing package declaration",
                        recoverable=True
                    )
            else:
                self.error_handler.handle_error(
                    Exception("No package declaration found"), 
                    error_type="file", 
                    file_path=file_path,
                    context="Missing package declaration",
                    recoverable=True
                )
            
            # Create RuleFile
            rule_file = RuleFile(
                path=file_path,
                package=package
            )
            
            # Parse imports
            for import_match in self.import_pattern.finditer(content):
                try:
                    import_str = import_match.group(1).strip()
                    package_parts = import_str.split('.')
                    class_name = package_parts[-1]
                    package_name = '.'.join(package_parts[:-1])
                    rule_file.imports.append(Import(package=package_name, class_name=class_name))
                except Exception as e:
                    import_text = import_match.group(0).strip()
                    line_number = find_line_for_pattern(content, import_text)
                    self.error_handler.handle_error(
                        e, 
                        error_type="file", 
                        file_path=file_path,
                        line_number=line_number,
                        context=f"Error parsing import: '{import_text}'",
                        recoverable=True
                    )
                    # Continue with other imports
            
            # Parse globals
            for global_match in self.global_pattern.finditer(content):
                try:
                    type_str = global_match.group(1).strip()
                    name = global_match.group(2).strip()
                    rule_file.globals.append(Global(type=type_str, name=name))
                except Exception as e:
                    global_text = global_match.group(0).strip()
                    line_number = find_line_for_pattern(content, global_text)
                    self.error_handler.handle_error(
                        e, 
                        error_type="file", 
                        file_path=file_path,
                        line_number=line_number,
                        context=f"Error parsing global: '{global_text}'",
                        recoverable=True
                    )
                    # Continue with other globals
            
            # Parse rules, queries, functions, and declared types
            try:
                self._parse_rules(content, rule_file, file_path)
            except DroolsParserError as e:
                self.error_handler.handle_error(
                    e, 
                    error_type="rule", 
                    file_path=file_path,
                    context="Error parsing rules section",
                    recoverable=True
                )
                # Continue with what we have parsed so far
            except Exception as e:
                self.error_handler.handle_error(
                    e, 
                    error_type="rule", 
                    file_path=file_path,
                    context="Unexpected error parsing rules section",
                    recoverable=True
                )
                # Continue with what we have parsed so far
            
            # Log parsing summary
            error_summary = self.error_handler.get_error_summary()
            if error_summary["total"] > 0:
                self.error_handler.log_error_summary()
            else:
                logger.info(f"Successfully parsed {file_path}: {len(rule_file.rules)} rules, "
                            f"{len(rule_file.imports)} imports, {len(rule_file.globals)} globals, "
                            f"{len(rule_file.queries)} queries, {len(rule_file.functions)} functions, "
                            f"{len(rule_file.declared_types)} declared types")
            
            return rule_file
        
        except DroolsParserError as e:
            self.error_handler.handle_error(
                e, 
                error_type="file", 
                file_path=file_path,
                context="Parser error in file",
                recoverable=False
            )
            raise
        except (FileNotFoundError, PermissionError):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            self.error_handler.handle_error(
                e, 
                error_type="file", 
                file_path=file_path,
                context="Unexpected error parsing file",
                recoverable=False
            )
            raise FileParsingError(f"Unexpected error parsing file {file_path}: {str(e)}", file_path) from e

    def _parse_rules(self, content: str, rule_file: RuleFile, file_path: str = None) -> None:
        """
        Parse rules from the content and add them to the rule file.

        Args:
            content: The content of the .drl file.
            rule_file: The RuleFile object to add the rules to.
            file_path: The path to the file being parsed (for error reporting).
        """
        # Find all rule blocks
        rule_blocks = self._extract_rule_blocks(content)
        
        for rule_block in rule_blocks:
            try:
                rule = self._parse_rule_block(rule_block, file_path)
                if rule:
                    rule_file.rules.append(rule)
            except RuleParsingError as e:
                # Get line number for better error reporting
                line_number = None
                if rule_block:
                    line_number = find_line_for_pattern(content, rule_block.split('\n')[0])
                
                self.error_handler.handle_error(
                    e, 
                    error_type="rule", 
                    file_path=file_path,
                    line_number=line_number,
                    rule_name=getattr(e, "rule_name", None),
                    context=f"Error parsing rule block: {rule_block[:100]}...",
                    recoverable=True
                )
                # Continue with other rules
            except Exception as e:
                # Get line number for better error reporting
                line_number = None
                if rule_block:
                    line_number = find_line_for_pattern(content, rule_block.split('\n')[0])
                
                self.error_handler.handle_error(
                    e, 
                    error_type="rule", 
                    file_path=file_path,
                    line_number=line_number,
                    context=f"Unexpected error parsing rule block: {rule_block[:100]}...",
                    recoverable=True
                )
                # Continue with other rules
        
        # Parse queries
        try:
            self._parse_queries(content, rule_file, file_path)
        except Exception as e:
            self.error_handler.handle_error(
                e, 
                error_type="query", 
                file_path=file_path,
                context="Error parsing queries section",
                recoverable=True
            )
        
        # Parse functions
        try:
            self._parse_functions(content, rule_file, file_path)
        except Exception as e:
            self.error_handler.handle_error(
                e, 
                error_type="function", 
                file_path=file_path,
                context="Error parsing functions section",
                recoverable=True
            )
        
        # Parse declared types
        try:
            self._parse_declared_types(content, rule_file, file_path)
        except Exception as e:
            self.error_handler.handle_error(
                e, 
                error_type="declared_type", 
                file_path=file_path,
                context="Error parsing declared types section",
                recoverable=True
            )

    def _extract_rule_blocks(self, content: str) -> List[str]:
        """
        Extract rule blocks from the content.

        Args:
            content: The content of the .drl file.

        Returns:
            A list of rule blocks.
        """
        rule_blocks = []
        lines = content.split('\n')
        current_block = []
        in_rule = False
        
        for line in lines:
            if self.rule_pattern.match(line):
                if in_rule:
                    # End previous rule if a new one starts without 'end'
                    rule_blocks.append('\n'.join(current_block))
                    current_block = []
                in_rule = True
                current_block.append(line)
            elif in_rule:
                current_block.append(line)
                if self.end_pattern.match(line.strip()):
                    rule_blocks.append('\n'.join(current_block))
                    current_block = []
                    in_rule = False
        
        # Add the last rule if there is one
        if current_block:
            rule_blocks.append('\n'.join(current_block))
        
        return rule_blocks

    def _parse_rule_block(self, rule_block: str, file_path: str = None) -> Optional[Rule]:
        """
        Parse a rule block and return a Rule object.

        Args:
            rule_block: The rule block to parse.
            file_path: The path to the file being parsed (for error reporting).

        Returns:
            A Rule object representing the parsed rule, or None if parsing fails.
            
        Raises:
            RuleParsingError: If there's an error parsing the rule.
            MalformedRuleError: If the rule is malformed.
        """
        rule_name = None
        try:
            # Parse rule name
            rule_match = self.rule_pattern.search(rule_block)
            if not rule_match:
                error_msg = f"Could not find rule name in block"
                logger.warning(f"{error_msg}: {rule_block[:100]}...")
                raise MalformedRuleError(error_msg, file_path)
            
            rule_name = rule_match.group(1)
            rule = Rule(name=rule_name)
            
            # Parse extends
            extends_match = self.extends_pattern.search(rule_block)
            if extends_match:
                rule.extends = extends_match.group(1)
            
            # Parse salience
            salience_match = self.salience_pattern.search(rule_block)
            if salience_match:
                try:
                    rule.salience = int(salience_match.group(1))
                except ValueError as e:
                    error_msg = f"Invalid salience value: {salience_match.group(1)}"
                    logger.warning(f"{error_msg} in rule '{rule_name}'")
                    # Continue without setting salience
            
            # Parse other attributes
            for attr_match in self.attribute_pattern.finditer(rule_block):
                attr_name = attr_match.group(1)
                attr_value = attr_match.group(2).strip()
                if attr_name not in ["extends", "salience", "when", "then"]:
                    rule.attributes[attr_name] = attr_value
            
            # Split into when and then parts
            when_match = self.when_pattern.search(rule_block)
            then_match = self.then_pattern.search(rule_block)
            end_match = self.end_pattern.search(rule_block)
            
            if not when_match:
                error_msg = f"Missing 'when' section in rule"
                logger.warning(f"{error_msg} '{rule_name}'")
                raise MalformedRuleError(error_msg, file_path, rule_name=rule_name)
                
            if not then_match:
                error_msg = f"Missing 'then' section in rule"
                logger.warning(f"{error_msg} '{rule_name}'")
                raise MalformedRuleError(error_msg, file_path, rule_name=rule_name)
                
            if not end_match:
                error_msg = f"Missing 'end' statement in rule"
                logger.warning(f"{error_msg} '{rule_name}'")
                raise MalformedRuleError(error_msg, file_path, rule_name=rule_name)
            
            when_start = when_match.end()
            when_end = then_match.start()
            then_start = then_match.end()
            then_end = end_match.start()
            
            when_part = rule_block[when_start:when_end]
            then_part = rule_block[then_start:then_end]
            
            # Parse conditions
            try:
                self._parse_conditions(when_part, rule, file_path, rule_name)
            except ConditionParsingError as e:
                logger.error(f"Error parsing conditions in rule '{rule_name}': {e}")
                # Continue with what we have parsed so far
            
            # Parse actions
            try:
                self._parse_actions(then_part, rule, file_path, rule_name)
            except ActionParsingError as e:
                logger.error(f"Error parsing actions in rule '{rule_name}': {e}")
                # Continue with what we have parsed so far
            
            return rule
        
        except MalformedRuleError:
            # Re-raise specific exceptions
            raise
        except Exception as e:
            error_msg = f"Unexpected error parsing rule"
            if rule_name:
                error_msg = f"{error_msg} '{rule_name}'"
            logger.error(f"{error_msg}: {e}")
            logger.debug(f"Rule block: {rule_block}")
            logger.debug(f"Stack trace: {traceback.format_exc()}")
            raise RuleParsingError(error_msg, file_path, rule_name=rule_name) from e

    def _parse_conditions(self, when_part: str, rule: Rule, file_path: str = None, rule_name: str = None) -> None:
        """
        Parse conditions from the when part and add them to the rule.

        Args:
            when_part: The when part of the rule.
            rule: The Rule object to add the conditions to.
            file_path: The path to the file being parsed (for error reporting).
            rule_name: The name of the rule being parsed (for error reporting).
            
        Raises:
            ConditionParsingError: If there's an error parsing a condition.
            MalformedConditionError: If a condition is malformed.
        """
        condition_count = 0
        
        for condition_match in self.condition_pattern.finditer(when_part):
            try:
                variable = condition_match.group(1)
                type_name = condition_match.group(2).strip()
                constraints_str = condition_match.group(3).strip()
                
                condition = Condition(variable=variable, type=type_name)
                
                # Parse constraints
                if constraints_str:
                    try:
                        self._parse_constraints(constraints_str, condition, file_path, rule_name, variable)
                    except ConditionParsingError as e:
                        logger.error(f"Error parsing constraints for condition '{variable}' in rule '{rule_name}': {e}")
                        # Continue with what we have parsed so far
                
                rule.conditions.append(condition)
                condition_count += 1
            except Exception as e:
                error_msg = f"Error parsing condition '{condition_match.group(0).strip()}'"
                logger.error(f"{error_msg} in rule '{rule_name}': {e}")
                logger.debug(f"Stack trace: {traceback.format_exc()}")
                raise ConditionParsingError(error_msg, file_path, rule_name=rule_name) from e
        
        if condition_count == 0:
            logger.warning(f"No conditions found in rule '{rule_name}'")
            # This is not necessarily an error, as some rules might use 'eval' or other constructs

    def _parse_constraints(self, constraints_str: str, condition: Condition, file_path: str = None, rule_name: str = None, variable: str = None) -> None:
        """
        Parse constraints from the constraints string and add them to the condition.

        Args:
            constraints_str: The constraints string.
            condition: The Condition object to add the constraints to.
            file_path: The path to the file being parsed (for error reporting).
            rule_name: The name of the rule being parsed (for error reporting).
            variable: The variable name of the condition (for error reporting).
            
        Raises:
            ConditionParsingError: If there's an error parsing a constraint.
            MalformedConditionError: If a constraint is malformed.
        """
        # Handle complex constraints with &&
        try:
            constraint_parts = self._split_constraints(constraints_str)
            
            for part in constraint_parts:
                try:
                    constraint_match = self.constraint_pattern.search(part)
                    if constraint_match:
                        field = constraint_match.group(1)
                        operator = constraint_match.group(2)
                        value = constraint_match.group(3).strip()
                        
                        # Remove quotes if present
                        if (value.startswith('"') and value.endswith('"')) or \
                           (value.startswith("'") and value.endswith("'")):
                            value = value[1:-1]
                        
                        condition.constraints.append(Constraint(field=field, operator=operator, value=value))
                    else:
                        # This part doesn't match our constraint pattern
                        self.error_handler.handle_error(
                            Exception(f"Could not parse constraint part '{part}'"),
                            error_type="condition",
                            file_path=file_path,
                            rule_name=rule_name,
                            context=f"Unparseable constraint in condition '{variable}'",
                            recoverable=True
                        )
                except Exception as e:
                    self.error_handler.handle_error(
                        e,
                        error_type="condition",
                        file_path=file_path,
                        rule_name=rule_name,
                        context=f"Error parsing constraint part '{part}' in condition '{variable}'",
                        recoverable=True
                    )
                    # Continue with other constraint parts
        except Exception as e:
            self.error_handler.handle_error(
                e,
                error_type="condition",
                file_path=file_path,
                rule_name=rule_name,
                context=f"Error parsing constraints '{constraints_str}' in condition '{variable}'",
                recoverable=False
            )
            raise ConditionParsingError(f"Error parsing constraints '{constraints_str}'", file_path, rule_name=rule_name) from e

    def _split_constraints(self, constraints_str: str) -> List[str]:
        """
        Split constraints by && operator, handling nested parentheses.

        Args:
            constraints_str: The constraints string.

        Returns:
            A list of constraint strings.
        """
        result = []
        current = ""
        paren_level = 0
        
        for char in constraints_str:
            if char == '(':
                paren_level += 1
                current += char
            elif char == ')':
                paren_level -= 1
                current += char
            elif char == '&' and paren_level == 0:
                # Skip && operator
                if current.strip():
                    result.append(current.strip())
                current = ""
            else:
                current += char
        
        if current.strip():
            result.append(current.strip())
        
        return result

    def _parse_actions(self, then_part: str, rule: Rule, file_path: str = None, rule_name: str = None) -> None:
        """
        Parse actions from the then part and add them to the rule.

        Args:
            then_part: The then part of the rule.
            rule: The Rule object to add the actions to.
            file_path: The path to the file being parsed (for error reporting).
            rule_name: The name of the rule being parsed (for error reporting).
            
        Raises:
            ActionParsingError: If there's an error parsing an action.
            MalformedActionError: If an action is malformed.
        """
        try:
            # Clean up the then part
            lines = then_part.split('\n')
            cleaned_lines = []
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                # Remove trailing semicolons
                if line.endswith(';'):
                    line = line[:-1]
                cleaned_lines.append(line)
            
            # Join lines back for multi-line statements
            then_text = ' '.join(cleaned_lines)
            
            # Split by semicolons that might be in the middle of statements
            statements = then_text.split(';')
            
            for statement in statements:
                try:
                    statement = statement.strip()
                    if not statement:
                        continue
                    
                    # Try to match method call: target.method(args)
                    method_match = re.search(r'([^.]+)\.(\w+)\(([^)]*)\)', statement)
                    if method_match:
                        target = method_match.group(1).strip()
                        method = method_match.group(2).strip()
                        args_str = method_match.group(3).strip()
                        
                        # Parse arguments
                        try:
                            args = self._parse_arguments(args_str, file_path, rule_name)
                            action = Action(type="method_call", target=target, method=method, arguments=args)
                            rule.actions.append(action)
                        except ActionParsingError as e:
                            logger.error(f"Error parsing arguments for method call '{target}.{method}' in rule '{rule_name}': {e}")
                            # Add a simplified action without parsed arguments
                            action = Action(type="method_call", target=target, method=method)
                            rule.actions.append(action)
                        continue
                    
                    # Try to match assignment: target = value
                    assignment_match = re.search(r'([^=]+)\s*=\s*(.+)', statement)
                    if assignment_match:
                        target = assignment_match.group(1).strip()
                        value = assignment_match.group(2).strip()
                        
                        action = Action(type="assignment", target=target, arguments=[value])
                        rule.actions.append(action)
                        continue
                    
                    # If no specific pattern matches, treat as a general statement
                    action = Action(type="statement", target=statement)
                    rule.actions.append(action)
                except Exception as e:
                    error_msg = f"Error parsing action statement '{statement}'"
                    logger.error(f"{error_msg} in rule '{rule_name}': {e}")
                    logger.debug(f"Stack trace: {traceback.format_exc()}")
                    # Continue with other statements
            
            if not rule.actions:
                logger.warning(f"No actions found in rule '{rule_name}'")
        except Exception as e:
            error_msg = f"Error parsing actions"
            logger.error(f"{error_msg} in rule '{rule_name}': {e}")
            logger.debug(f"Stack trace: {traceback.format_exc()}")
            raise ActionParsingError(error_msg, file_path, rule_name=rule_name) from e

    def _parse_arguments(self, args_str: str, file_path: str = None, rule_name: str = None) -> List[str]:
        """
        Parse arguments from an arguments string.

        Args:
            args_str: The arguments string.
            file_path: The path to the file being parsed (for error reporting).
            rule_name: The name of the rule being parsed (for error reporting).

        Returns:
            A list of argument strings.
            
        Raises:
            ActionParsingError: If there's an error parsing arguments.
        """
        if not args_str:
            return []
        
        try:
            args = []
            current = ""
            paren_level = 0
            quote_char = None
            
            for char in args_str:
                if char == '"' or char == "'":
                    if quote_char is None:
                        quote_char = char
                    elif quote_char == char:
                        quote_char = None
                    current += char
                elif char == '(' and quote_char is None:
                    paren_level += 1
                    current += char
                elif char == ')' and quote_char is None:
                    paren_level -= 1
                    current += char
                elif char == ',' and paren_level == 0 and quote_char is None:
                    args.append(current.strip())
                    current = ""
                else:
                    current += char
            
            if current.strip():
                args.append(current.strip())
            
            # Check for unbalanced quotes or parentheses
            if quote_char is not None:
                logger.warning(f"Unbalanced quotes in arguments '{args_str}' in rule '{rule_name}'")
            
            if paren_level != 0:
                logger.warning(f"Unbalanced parentheses in arguments '{args_str}' in rule '{rule_name}'")
            
            return args
        except Exception as e:
            error_msg = f"Error parsing arguments '{args_str}'"
            logger.error(f"{error_msg} in rule '{rule_name}': {e}")
            logger.debug(f"Stack trace: {traceback.format_exc()}")
            raise ActionParsingError(error_msg, file_path, rule_name=rule_name) from e
        
    def _parse_queries(self, content: str, rule_file: RuleFile, file_path: str = None) -> None:
        """
        Parse queries from the content and add them to the rule file.

        Args:
            content: The content of the .drl file.
            rule_file: The RuleFile object to add the queries to.
            file_path: The path to the file being parsed (for error reporting).
        """
        # Find all query blocks
        try:
            # Extract query blocks using regex
            query_blocks = []
            lines = content.split('\n')
            current_block = []
            in_query = False
            
            for line in lines:
                if self.query_pattern.match(line):
                    if in_query:
                        # End previous query if a new one starts without 'end'
                        query_blocks.append('\n'.join(current_block))
                        current_block = []
                    in_query = True
                    current_block.append(line)
                elif in_query:
                    current_block.append(line)
                    if self.end_pattern.match(line.strip()):
                        query_blocks.append('\n'.join(current_block))
                        current_block = []
                        in_query = False
            
            # Add the last query if there is one
            if current_block and in_query:
                query_blocks.append('\n'.join(current_block))
            
            # Parse each query block
            for query_block in query_blocks:
                try:
                    # Extract query name
                    query_match = self.query_pattern.search(query_block)
                    if not query_match:
                        self.error_handler.handle_error(
                            Exception("Could not find query name in block"),
                            error_type="query",
                            file_path=file_path,
                            context=f"Malformed query block: {query_block[:100]}...",
                            recoverable=True
                        )
                        continue
                    
                    query_name = query_match.group(1)
                    query = Query(name=query_name)
                    
                    # Parse conditions
                    for condition_match in self.condition_pattern.finditer(query_block):
                        try:
                            variable = condition_match.group(1)
                            type_name = condition_match.group(2).strip()
                            constraints_str = condition_match.group(3).strip()
                            
                            condition = Condition(variable=variable, type=type_name)
                            
                            # Parse constraints
                            if constraints_str:
                                try:
                                    self._parse_constraints(constraints_str, condition, file_path, None, variable)
                                except Exception as e:
                                    self.error_handler.handle_error(
                                        e,
                                        error_type="query",
                                        file_path=file_path,
                                        context=f"Error parsing constraints in query '{query_name}'",
                                        recoverable=True
                                    )
                            
                            query.conditions.append(condition)
                        except Exception as e:
                            self.error_handler.handle_error(
                                e,
                                error_type="query",
                                file_path=file_path,
                                context=f"Error parsing condition in query '{query_name}'",
                                recoverable=True
                            )
                    
                    rule_file.queries.append(query)
                except Exception as e:
                    self.error_handler.handle_error(
                        e,
                        error_type="query",
                        file_path=file_path,
                        context=f"Error parsing query block: {query_block[:100]}...",
                        recoverable=True
                    )
        except Exception as e:
            self.error_handler.handle_error(
                e,
                error_type="query",
                file_path=file_path,
                context="Error parsing queries section",
                recoverable=True
            )

    def _parse_query_block(self, query_block: str, file_path: str = None) -> Optional[Query]:
        """
        Parse a query block and return a Query object.

        Args:
            query_block: The query block to parse.
            file_path: The path to the file being parsed (for error reporting).

        Returns:
            A Query object representing the parsed query, or None if parsing fails.
            
        Raises:
            QueryParsingError: If there's an error parsing the query.
            MalformedQueryError: If the query is malformed.
        """
        query_name = None
        try:
            # Parse query name
            query_match = self.query_pattern.search(query_block)
            if not query_match:
                error_msg = f"Could not find query name in block"
                logger.warning(f"{error_msg}: {query_block[:100]}...")
                raise MalformedQueryError(error_msg, file_path)
            
            query_name = query_match.group(1)
            query = Query(name=query_name)
            
            # Parse conditions
            condition_count = 0
            for condition_match in self.condition_pattern.finditer(query_block):
                try:
                    variable = condition_match.group(1)
                    type_name = condition_match.group(2).strip()
                    constraints_str = condition_match.group(3).strip()
                    
                    condition = Condition(variable=variable, type=type_name)
                    
                    # Parse constraints
                    if constraints_str:
                        try:
                            self._parse_constraints(constraints_str, condition, file_path, query_name, variable)
                        except ConditionParsingError as e:
                            logger.error(f"Error parsing constraints for condition '{variable}' in query '{query_name}': {e}")
                            # Continue with what we have parsed so far
                    
                    query.conditions.append(condition)
                    condition_count += 1
                except Exception as e:
                    error_msg = f"Error parsing condition '{condition_match.group(0).strip()}'"
                    logger.error(f"{error_msg} in query '{query_name}': {e}")
                    logger.debug(f"Stack trace: {traceback.format_exc()}")
                    # Continue with other conditions
            
            if condition_count == 0:
                logger.warning(f"No conditions found in query '{query_name}'")
            
            return query
        
        except MalformedQueryError:
            # Re-raise specific exceptions
            raise
        except Exception as e:
            error_msg = f"Unexpected error parsing query"
            if query_name:
                error_msg = f"{error_msg} '{query_name}'"
            logger.error(f"{error_msg}: {e}")
            logger.debug(f"Query block: {query_block}")
            logger.debug(f"Stack trace: {traceback.format_exc()}")
            raise QueryParsingError(error_msg, file_path, query_name=query_name) from e

    def _parse_functions(self, content: str, rule_file: RuleFile, file_path: str = None) -> None:
        """
        Parse functions from the content and add them to the rule file.

        Args:
            content: The content of the .drl file.
            rule_file: The RuleFile object to add the functions to.
            file_path: The path to the file being parsed (for error reporting).
        """
        try:
            # Extract function blocks using regex
            function_blocks = []
            lines = content.split('\n')
            current_block = []
            in_function = False
            brace_count = 0
            
            for line in lines:
                if self.function_pattern.match(line):
                    in_function = True
                    current_block = [line]
                    brace_count = line.count('{') - line.count('}')
                elif in_function:
                    current_block.append(line)
                    brace_count += line.count('{') - line.count('}')
                    if brace_count == 0:
                        function_blocks.append('\n'.join(current_block))
                        current_block = []
                        in_function = False
            
            # Add the last function if there is one
            if current_block and in_function:
                function_blocks.append('\n'.join(current_block))
            
            # Parse each function block
            for function_block in function_blocks:
                try:
                    # Extract function details
                    function_match = self.function_pattern.search(function_block)
                    if not function_match:
                        self.error_handler.handle_error(
                            Exception("Could not find function declaration in block"),
                            error_type="function",
                            file_path=file_path,
                            context=f"Malformed function block: {function_block[:100]}...",
                            recoverable=True
                        )
                        continue
                    
                    return_type = function_match.group(1)
                    function_name = function_match.group(2)
                    params_str = function_match.group(3).strip()
                    
                    function = Function(return_type=return_type, name=function_name)
                    
                    # Parse parameters
                    if params_str:
                        param_parts = params_str.split(',')
                        for param_part in param_parts:
                            param_part = param_part.strip()
                            if param_part:
                                try:
                                    param_parts = param_part.split()
                                    if len(param_parts) >= 2:
                                        param_type = param_parts[0]
                                        param_name = param_parts[1]
                                        function.parameters.append(Parameter(type=param_type, name=param_name))
                                except Exception as e:
                                    self.error_handler.handle_error(
                                        e,
                                        error_type="function",
                                        file_path=file_path,
                                        context=f"Error parsing parameter '{param_part}' in function '{function_name}'",
                                        recoverable=True
                                    )
                    
                    # Extract function body
                    body_start = function_block.find('{')
                    body_end = function_block.rfind('}')
                    if body_start != -1 and body_end != -1 and body_end > body_start:
                        function.body = function_block[body_start+1:body_end].strip()
                    
                    rule_file.functions.append(function)
                except Exception as e:
                    self.error_handler.handle_error(
                        e,
                        error_type="function",
                        file_path=file_path,
                        context=f"Error parsing function block: {function_block[:100]}...",
                        recoverable=True
                    )
        except Exception as e:
            self.error_handler.handle_error(
                e,
                error_type="function",
                file_path=file_path,
                context="Error parsing functions section",
                recoverable=True
            )
            
        # Find all function declarations
        for function_match in self.function_pattern.finditer(content):
            function_name = None
            try:
                return_type = function_match.group(1).strip()
                function_name = function_match.group(2).strip()
                params_str = function_match.group(3).strip()
                
                # Find the function body
                start_pos = function_match.end()
                # Look for the opening brace
                open_brace_pos = content.find('{', start_pos)
                if open_brace_pos == -1:
                    error_msg = f"Missing opening brace for function"
                    logger.warning(f"{error_msg} '{function_name}'")
                    parsing_errors.append(error_msg)
                    continue
                
                # Find the matching closing brace
                brace_level = 1
                close_brace_pos = -1
                for i in range(open_brace_pos + 1, len(content)):
                    if content[i] == '{':
                        brace_level += 1
                    elif content[i] == '}':
                        brace_level -= 1
                        if brace_level == 0:
                            close_brace_pos = i
                            break
                
                if close_brace_pos == -1:
                    error_msg = f"Missing closing brace for function"
                    logger.warning(f"{error_msg} '{function_name}'")
                    parsing_errors.append(error_msg)
                    continue
                
                # Extract the function body
                body = content[open_brace_pos + 1:close_brace_pos].strip()
                
                # Parse parameters
                parameters = []
                if params_str:
                    param_parts = params_str.split(',')
                    for part in param_parts:
                        try:
                            part = part.strip()
                            if ' ' in part:
                                param_type, param_name = part.rsplit(' ', 1)
                                parameters.append(Parameter(type=param_type.strip(), name=param_name.strip()))
                            else:
                                logger.warning(f"Malformed parameter '{part}' in function '{function_name}'")
                        except Exception as e:
                            error_msg = f"Error parsing parameter '{part}'"
                            logger.error(f"{error_msg} in function '{function_name}': {e}")
                            logger.debug(f"Stack trace: {traceback.format_exc()}")
                            # Continue with other parameters
                
                function = Function(return_type=return_type, name=function_name, parameters=parameters, body=body)
                rule_file.functions.append(function)
                logger.debug(f"Successfully parsed function '{function_name}'")
            
            except Exception as e:
                error_msg = f"Error parsing function"
                if function_name:
                    error_msg = f"{error_msg} '{function_name}'"
                logger.error(f"{error_msg}: {e}")
                logger.debug(f"Stack trace: {traceback.format_exc()}")
                parsing_errors.append(error_msg)
                # Continue with other functions

    def _parse_declared_types(self, content: str, rule_file: RuleFile, file_path: str = None) -> None:
        """
        Parse declared types from the content and add them to the rule file.

        Args:
            content: The content of the .drl file.
            rule_file: The RuleFile object to add the declared types to.
            file_path: The path to the file being parsed (for error reporting).
        """
        # Find all declare blocks
        declare_blocks = self._extract_blocks(content, self.declare_pattern, self.end_declare_pattern)
        
        for declare_block in declare_blocks:
            declared_type = self._parse_declare_block(declare_block)
            if declared_type:
                rule_file.declared_types.append(declared_type)

    def _parse_declare_block(self, declare_block: str) -> Optional[DeclaredType]:
        """
        Parse a declare block and return a DeclaredType object.

        Args:
            declare_block: The declare block to parse.

        Returns:
            A DeclaredType object representing the parsed declared type, or None if parsing fails.
        """
        try:
            # Parse type name
            declare_match = self.declare_pattern.search(declare_block)
            if not declare_match:
                logger.warning(f"Could not find type name in block: {declare_block}")
                return None
            
            type_name = declare_match.group(1)
            declared_type = DeclaredType(name=type_name)
            
            # Parse annotations
            annotation_pattern = re.compile(r'@(\w+)(?:\(([^)]*)\))?')
            for annotation_match in annotation_pattern.finditer(declare_block):
                annotation_name = annotation_match.group(1)
                annotation_value = annotation_match.group(2) or ""
                declared_type.annotations[annotation_name] = annotation_value
            
            # Parse fields
            field_pattern = re.compile(r'\s+(\w+)\s+(\w+)(?:\s*:\s*(.+))?')
            for field_match in field_pattern.finditer(declare_block):
                field_type = field_match.group(1)
                field_name = field_match.group(2)
                field_annotations_str = field_match.group(3) or ""
                
                field = Field(type=field_type, name=field_name)
                
                # Parse field annotations
                field_annotation_pattern = re.compile(r'@(\w+)(?:\(([^)]*)\))?')
                for field_annotation_match in field_annotation_pattern.finditer(field_annotations_str):
                    annotation_name = field_annotation_match.group(1)
                    annotation_value = field_annotation_match.group(2) or ""
                    field.annotations[annotation_name] = annotation_value
                
                declared_type.fields.append(field)
            
            return declared_type
        
        except Exception as e:
            logger.error(f"Error parsing declare block: {e}")
            logger.debug(f"Declare block: {declare_block}")
            return None

    def _extract_blocks(self, content: str, start_pattern: re.Pattern, end_pattern: re.Pattern) -> List[str]:
        """
        Extract blocks from the content based on start and end patterns.

        Args:
            content: The content of the .drl file.
            start_pattern: The pattern to match the start of a block.
            end_pattern: The pattern to match the end of a block.

        Returns:
            A list of blocks.
        """
        blocks = []
        lines = content.split('\n')
        current_block = []
        in_block = False
        
        for line in lines:
            if start_pattern.search(line):
                if in_block:
                    # End previous block if a new one starts without end marker
                    blocks.append('\n'.join(current_block))
                    current_block = []
                in_block = True
                current_block.append(line)
            elif in_block:
                current_block.append(line)
                if end_pattern.search(line.strip()):
                    blocks.append('\n'.join(current_block))
                    current_block = []
                    in_block = False
        
        # Add the last block if there is one
        if current_block:
            blocks.append('\n'.join(current_block))
        
        return blocks