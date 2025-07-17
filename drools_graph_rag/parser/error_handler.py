"""
Error handling utilities for the Drools parser.

This module provides utilities for handling and logging errors that occur during
the parsing of Drools rule files.
"""
import logging
import os
import traceback
from typing import Dict, List, Optional, Tuple, Union

from drools_graph_rag.parser.exceptions import (
    DroolsParserError,
    FileParsingError,
    RuleParsingError,
    ConditionParsingError,
    ActionParsingError,
    QueryParsingError,
    FunctionParsingError,
    DeclaredTypeParsingError,
    MalformedRuleError,
    MalformedConditionError,
    MalformedActionError,
    MalformedQueryError,
    MalformedFunctionError,
    MalformedDeclaredTypeError,
)

# Create a dedicated logger for parser errors
logger = logging.getLogger("drools_parser.errors")


class ParserErrorHandler:
    """
    Handler for parser errors with detailed logging and recovery strategies.
    """

    def __init__(self, log_level: str = "INFO") -> None:
        """
        Initialize the error handler.
        
        Args:
            log_level: The logging level to use.
        """
        self.log_level = log_level
        self._configure_logger()
        self.error_counts: Dict[str, int] = {
            "file": 0,
            "rule": 0,
            "condition": 0,
            "action": 0,
            "query": 0,
            "function": 0,
            "declared_type": 0,
            "other": 0,
        }
        self.errors: List[Dict] = []
        
    def _configure_logger(self) -> None:
        """Configure the error logger with appropriate handlers and formatters."""
        # Set the log level
        level = getattr(logging, self.log_level.upper(), logging.INFO)
        logger.setLevel(level)
        
        # Create console handler if not already present
        if not logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            
            # Add handler to logger
            logger.addHandler(console_handler)
    
    def reset_counts(self) -> None:
        """Reset error counts."""
        for key in self.error_counts:
            self.error_counts[key] = 0
        self.errors = []
    
    def handle_error(
        self, 
        error: Exception, 
        error_type: str = "other", 
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        rule_name: Optional[str] = None,
        context: Optional[str] = None,
        recoverable: bool = True
    ) -> None:
        """
        Handle an error by logging it and updating error counts.
        
        Args:
            error: The exception that occurred.
            error_type: The type of error (file, rule, condition, etc.).
            file_path: The path to the file where the error occurred.
            line_number: The line number where the error occurred.
            rule_name: The name of the rule where the error occurred.
            context: Additional context about the error.
            recoverable: Whether the error is recoverable.
        """
        # Update error counts
        if error_type in self.error_counts:
            self.error_counts[error_type] += 1
        else:
            self.error_counts["other"] += 1
        
        # Format error message
        error_msg = str(error)
        location_info = []
        
        if file_path:
            location_info.append(f"File: {os.path.basename(file_path)}")
        
        if rule_name:
            location_info.append(f"Rule: {rule_name}")
            
        if line_number is not None:
            location_info.append(f"Line: {line_number}")
            
        location_str = " | ".join(location_info) if location_info else "Unknown location"
        
        # Log the error
        if isinstance(error, DroolsParserError):
            # DroolsParserError already includes file and line information
            if recoverable:
                logger.warning(f"{error_type.upper()} ERROR: {error}")
            else:
                logger.error(f"{error_type.upper()} ERROR: {error}")
        else:
            # For other exceptions, add location information
            if recoverable:
                logger.warning(f"{error_type.upper()} ERROR in {location_str}: {error_msg}")
            else:
                logger.error(f"{error_type.upper()} ERROR in {location_str}: {error_msg}")
        
        # Log stack trace for unexpected errors
        if not isinstance(error, DroolsParserError):
            logger.debug(f"Stack trace: {traceback.format_exc()}")
        
        # Log additional context if provided
        if context:
            logger.debug(f"Context: {context}")
        
        # Store error details
        error_details = {
            "type": error_type,
            "message": error_msg,
            "file_path": file_path,
            "line_number": line_number,
            "rule_name": rule_name,
            "recoverable": recoverable,
            "exception_type": type(error).__name__,
        }
        self.errors.append(error_details)
    
    def get_error_summary(self) -> Dict[str, Union[int, List[Dict]]]:
        """
        Get a summary of errors encountered.
        
        Returns:
            A dictionary with error counts and details.
        """
        total_errors = sum(self.error_counts.values())
        
        return {
            "total": total_errors,
            "counts": self.error_counts.copy(),
            "errors": self.errors.copy(),
        }
    
    def log_error_summary(self) -> None:
        """Log a summary of errors encountered."""
        summary = self.get_error_summary()
        total = summary["total"]
        
        if total == 0:
            logger.info("No errors encountered during parsing.")
            return
        
        logger.warning(f"Encountered {total} errors during parsing:")
        for error_type, count in summary["counts"].items():
            if count > 0:
                logger.warning(f"  - {error_type.upper()} errors: {count}")
        
        # Log details of the first few errors
        max_details = min(5, len(self.errors))
        if max_details > 0:
            logger.warning(f"First {max_details} error details:")
            for i in range(max_details):
                error = self.errors[i]
                location = []
                if error["file_path"]:
                    location.append(f"file={os.path.basename(error['file_path'])}")
                if error["rule_name"]:
                    location.append(f"rule={error['rule_name']}")
                if error["line_number"] is not None:
                    location.append(f"line={error['line_number']}")
                
                location_str = ", ".join(location) if location else "unknown location"
                logger.warning(f"  {i+1}. [{error['type']}] {error['message']} ({location_str})")


def extract_line_number(content: str, position: int) -> int:
    """
    Extract the line number from a position in the content.
    
    Args:
        content: The content string.
        position: The position in the content.
        
    Returns:
        The line number (1-based).
    """
    if position < 0 or position >= len(content):
        return -1
    
    return content[:position].count('\n') + 1


def find_line_for_pattern(content: str, pattern: str) -> int:
    """
    Find the line number for a pattern in the content.
    
    Args:
        content: The content string.
        pattern: The pattern to search for.
        
    Returns:
        The line number (1-based) or -1 if not found.
    """
    if not pattern or not content:
        return -1
    
    position = content.find(pattern)
    if position == -1:
        return -1
    
    return extract_line_number(content, position)


def extract_context(content: str, position: int, context_lines: int = 2) -> str:
    """
    Extract context around a position in the content.
    
    Args:
        content: The content string.
        position: The position in the content.
        context_lines: The number of lines of context to include before and after.
        
    Returns:
        The context string.
    """
    if not content or position < 0 or position >= len(content):
        return ""
    
    lines = content.split('\n')
    line_number = extract_line_number(content, position)
    
    if line_number <= 0:
        return ""
    
    # Convert to 0-based index
    line_idx = line_number - 1
    
    # Calculate start and end lines
    start_idx = max(0, line_idx - context_lines)
    end_idx = min(len(lines) - 1, line_idx + context_lines)
    
    # Extract context lines
    context_lines = []
    for i in range(start_idx, end_idx + 1):
        prefix = ">> " if i == line_idx else "   "
        context_lines.append(f"{prefix}{i+1}: {lines[i]}")
    
    return "\n".join(context_lines)