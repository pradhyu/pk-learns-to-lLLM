"""
Data models for Drools rule parsing.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class Import:
    """
    Represents an import statement in a Drools rule file.
    """
    package: str
    class_name: str
    
    @property
    def full_name(self) -> str:
        """
        Get the full class name including package.
        
        Returns:
            The full class name.
        """
        return f"{self.package}.{self.class_name}"


@dataclass
class Global:
    """
    Represents a global variable declaration in a Drools rule file.
    """
    type: str
    name: str


@dataclass
class Constraint:
    """
    Represents a constraint in a rule condition.
    """
    field: str
    operator: str
    value: str
    
    def __str__(self) -> str:
        """
        String representation of the constraint.
        
        Returns:
            The constraint as a string.
        """
        return f"{self.field} {self.operator} {self.value}"


@dataclass
class Condition:
    """
    Represents a condition in a rule.
    """
    variable: str
    type: str
    constraints: List[Constraint] = field(default_factory=list)
    
    def __str__(self) -> str:
        """
        String representation of the condition.
        
        Returns:
            The condition as a string.
        """
        constraints_str = " && ".join(str(c) for c in self.constraints)
        return f"{self.variable} : {self.type}({constraints_str})"


@dataclass
class Action:
    """
    Represents an action in a rule.
    """
    type: str  # method_call, assignment, etc.
    target: str
    method: Optional[str] = None
    arguments: List[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        """
        String representation of the action.
        
        Returns:
            The action as a string.
        """
        if self.type == "method_call" and self.method:
            args_str = ", ".join(self.arguments)
            return f"{self.target}.{self.method}({args_str})"
        elif self.type == "assignment":
            return f"{self.target} = {self.arguments[0] if self.arguments else ''}"
        else:
            return f"{self.target}"


@dataclass
class Rule:
    """
    Represents a rule in a Drools rule file.
    """
    name: str
    extends: Optional[str] = None
    salience: Optional[int] = None
    conditions: List[Condition] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)
    
    def __str__(self) -> str:
        """
        String representation of the rule.
        
        Returns:
            The rule as a string.
        """
        result = [f"rule \"{self.name}\""]
        
        if self.extends:
            result.append(f"    extends \"{self.extends}\"")
        
        if self.salience is not None:
            result.append(f"    salience {self.salience}")
            
        for key, value in self.attributes.items():
            if key != "salience":  # Already handled above
                result.append(f"    {key} {value}")
        
        result.append("    when")
        for condition in self.conditions:
            result.append(f"        {condition}")
        
        result.append("    then")
        for action in self.actions:
            result.append(f"        {action};")
        
        result.append("end")
        return "\n".join(result)


@dataclass
class Parameter:
    """
    Represents a parameter in a function or query.
    """
    type: str
    name: str
    
    def __str__(self) -> str:
        """
        String representation of the parameter.
        
        Returns:
            The parameter as a string.
        """
        return f"{self.type} {self.name}"


@dataclass
class Function:
    """
    Represents a function in a Drools rule file.
    """
    return_type: str
    name: str
    parameters: List[Parameter] = field(default_factory=list)
    body: str = ""
    
    def __str__(self) -> str:
        """
        String representation of the function.
        
        Returns:
            The function as a string.
        """
        params_str = ", ".join(str(p) for p in self.parameters)
        result = [f"function {self.return_type} {self.name}({params_str}) {{"]
        result.append(f"    {self.body}")
        result.append("}")
        return "\n".join(result)


@dataclass
class Query:
    """
    Represents a query in a Drools rule file.
    """
    name: str
    conditions: List[Condition] = field(default_factory=list)
    
    def __str__(self) -> str:
        """
        String representation of the query.
        
        Returns:
            The query as a string.
        """
        result = [f"query \"{self.name}\""]
        for condition in self.conditions:
            result.append(f"    {condition}")
        result.append("end")
        return "\n".join(result)


@dataclass
class Field:
    """
    Represents a field in a declared type.
    """
    type: str
    name: str
    annotations: Dict[str, str] = field(default_factory=dict)
    
    def __str__(self) -> str:
        """
        String representation of the field.
        
        Returns:
            The field as a string.
        """
        annotations_str = ""
        for key, value in self.annotations.items():
            annotations_str += f"@{key}({value})\n    "
        
        return f"{annotations_str}{self.type} {self.name}"


@dataclass
class DeclaredType:
    """
    Represents a declared type in a Drools rule file.
    """
    name: str
    fields: List[Field] = field(default_factory=list)
    annotations: Dict[str, str] = field(default_factory=dict)
    
    def __str__(self) -> str:
        """
        String representation of the declared type.
        
        Returns:
            The declared type as a string.
        """
        result = []
        
        for key, value in self.annotations.items():
            result.append(f"@{key}({value})")
        
        result.append(f"declare {self.name}")
        
        for field in self.fields:
            result.append(f"    {field}")
        
        result.append("end declare")
        return "\n".join(result)


@dataclass
class RuleFile:
    """
    Represents a Drools rule file (.drl).
    """
    path: str
    package: str
    imports: List[Import] = field(default_factory=list)
    globals: List[Global] = field(default_factory=list)
    rules: List[Rule] = field(default_factory=list)
    queries: List[Query] = field(default_factory=list)
    functions: List[Function] = field(default_factory=list)
    declared_types: List[DeclaredType] = field(default_factory=list)
    
    def __str__(self) -> str:
        """
        String representation of the rule file.
        
        Returns:
            The rule file as a string.
        """
        result = [f"package {self.package}"]
        result.append("")
        
        for imp in self.imports:
            result.append(f"import {imp.full_name};")
        
        if self.imports:
            result.append("")
        
        for glob in self.globals:
            result.append(f"global {glob.type} {glob.name};")
        
        if self.globals:
            result.append("")
        
        for declared_type in self.declared_types:
            result.append(str(declared_type))
            result.append("")
        
        for function in self.functions:
            result.append(str(function))
            result.append("")
        
        for rule in self.rules:
            result.append(str(rule))
            result.append("")
        
        for query in self.queries:
            result.append(str(query))
            result.append("")
        
        return "\n".join(result)