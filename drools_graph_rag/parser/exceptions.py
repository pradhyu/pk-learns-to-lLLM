"""
Custom exceptions for the Drools parser.
"""


class DroolsParserError(Exception):
    """Base exception for all parser errors."""
    
    def __init__(self, message: str, file_path: str = None, line_number: int = None):
        """
        Initialize the exception.
        
        Args:
            message: The error message.
            file_path: The path to the file where the error occurred.
            line_number: The line number where the error occurred.
        """
        self.file_path = file_path
        self.line_number = line_number
        
        # Format the message with file and line information if available
        formatted_message = message
        if file_path:
            formatted_message = f"{file_path}: {formatted_message}"
        if line_number is not None:
            formatted_message = f"{formatted_message} (line {line_number})"
            
        super().__init__(formatted_message)


class FileParsingError(DroolsParserError):
    """Exception raised when there's an error parsing a file."""
    pass


class RuleParsingError(DroolsParserError):
    """Exception raised when there's an error parsing a rule."""
    
    def __init__(self, message: str, file_path: str = None, line_number: int = None, rule_name: str = None):
        """
        Initialize the exception.
        
        Args:
            message: The error message.
            file_path: The path to the file where the error occurred.
            line_number: The line number where the error occurred.
            rule_name: The name of the rule being parsed.
        """
        self.rule_name = rule_name
        
        # Add rule name to message if available
        if rule_name:
            message = f"Rule '{rule_name}': {message}"
            
        super().__init__(message, file_path, line_number)


class ConditionParsingError(RuleParsingError):
    """Exception raised when there's an error parsing a condition."""
    pass


class ActionParsingError(RuleParsingError):
    """Exception raised when there's an error parsing an action."""
    pass


class QueryParsingError(DroolsParserError):
    """Exception raised when there's an error parsing a query."""
    
    def __init__(self, message: str, file_path: str = None, line_number: int = None, query_name: str = None):
        """
        Initialize the exception.
        
        Args:
            message: The error message.
            file_path: The path to the file where the error occurred.
            line_number: The line number where the error occurred.
            query_name: The name of the query being parsed.
        """
        self.query_name = query_name
        
        # Add query name to message if available
        if query_name:
            message = f"Query '{query_name}': {message}"
            
        super().__init__(message, file_path, line_number)


class FunctionParsingError(DroolsParserError):
    """Exception raised when there's an error parsing a function."""
    
    def __init__(self, message: str, file_path: str = None, line_number: int = None, function_name: str = None):
        """
        Initialize the exception.
        
        Args:
            message: The error message.
            file_path: The path to the file where the error occurred.
            line_number: The line number where the error occurred.
            function_name: The name of the function being parsed.
        """
        self.function_name = function_name
        
        # Add function name to message if available
        if function_name:
            message = f"Function '{function_name}': {message}"
            
        super().__init__(message, file_path, line_number)


class DeclaredTypeParsingError(DroolsParserError):
    """Exception raised when there's an error parsing a declared type."""
    
    def __init__(self, message: str, file_path: str = None, line_number: int = None, type_name: str = None):
        """
        Initialize the exception.
        
        Args:
            message: The error message.
            file_path: The path to the file where the error occurred.
            line_number: The line number where the error occurred.
            type_name: The name of the declared type being parsed.
        """
        self.type_name = type_name
        
        # Add type name to message if available
        if type_name:
            message = f"Declared type '{type_name}': {message}"
            
        super().__init__(message, file_path, line_number)


class MalformedRuleError(RuleParsingError):
    """Exception raised when a rule is malformed."""
    pass


class MalformedConditionError(ConditionParsingError):
    """Exception raised when a condition is malformed."""
    pass


class MalformedActionError(ActionParsingError):
    """Exception raised when an action is malformed."""
    pass


class MalformedQueryError(QueryParsingError):
    """Exception raised when a query is malformed."""
    pass


class MalformedFunctionError(FunctionParsingError):
    """Exception raised when a function is malformed."""
    pass


class MalformedDeclaredTypeError(DeclaredTypeParsingError):
    """Exception raised when a declared type is malformed."""
    pass