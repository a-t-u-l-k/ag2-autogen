from ag2 import Agent, tool
import requests
import json
import re
from typing import Dict, Any, Union, List, Optional, Tuple

class ArithmeticOllamaAgent(Agent):
    """An agent that performs arithmetic operations using tools and processes queries with a local Ollama LLM."""
    
    def __init__(self, ollama_base_url: str = "http://localhost:11434", model: str = "llama3"):
        """
        Initialize the ArithmeticOllamaAgent.
        
        Args:
            ollama_base_url: Base URL for Ollama API (default: http://localhost:11434)
            model: Ollama model to use (default: llama3)
        """
        super().__init__()
        self.ollama_base_url = ollama_base_url
        self.model = model
    
    @tool
    def add(self, a: float, b: float) -> float:
        """
        Add two numbers.
        
        Args:
            a: First number
            b: Second number
            
        Returns:
            Sum of a and b
        """
        return a + b
    
    @tool
    def subtract(self, a: float, b: float) -> float:
        """
        Subtract second number from first number.
        
        Args:
            a: First number
            b: Second number
            
        Returns:
            Result of a - b
        """
        return a - b
    
    @tool
    def multiply(self, a: float, b: float) -> float:
        """
        Multiply two numbers.
        
        Args:
            a: First number
            b: Second number
            
        Returns:
            Product of a and b
        """
        return a * b
    
    @tool
    def divide(self, a: float, b: float) -> Union[float, str]:
        """
        Divide first number by second number.
        
        Args:
            a: First number (dividend)
            b: Second number (divisor)
            
        Returns:
            Result of a / b or an error message if b is zero
        """
        if b == 0:
            return "Error: Division by zero is not allowed"
        return a / b
    
    @tool
    def power(self, base: float, exponent: float) -> float:
        """
        Raise base to the power of exponent.
        
        Args:
            base: The base number
            exponent: The exponent
            
        Returns:
            Result of base^exponent
        """
        return base ** exponent
    
    @tool
    def square_root(self, number: float) -> Union[float, str]:
        """
        Calculate the square root of a number.
        
        Args:
            number: The number to find the square root of
            
        Returns:
            Square root of the number or an error for negative inputs
        """
        if number < 0:
            return "Error: Cannot calculate square root of a negative number"
        return number ** 0.5
    
    @tool
    def calculate_expression(self, expression: str) -> Union[float, str]:
        """
        Evaluate a simple arithmetic expression string.
        
        Args:
            expression: A string containing a simple arithmetic expression
            
        Returns:
            Result of the evaluated expression or an error message
        """
        # Remove whitespace and validate the expression
        expression = expression.replace(" ", "")
        if not re.match(r'^[0-9+\-*/().\^]+$', expression):
            return "Error: Invalid characters in expression"
        
        try:
            # Replace ^ with ** for exponentiation
            expression = expression.replace('^', '**')
            # Use eval (in a real-world application, you would want to use a safer alternative)
            result = eval(expression)
            return result
        except Exception as e:
            return f"Error evaluating expression: {str(e)}"
    
    @tool
    def process_with_ollama(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Process a prompt with the local Ollama LLM.
        
        Args:
            prompt: The user prompt to send to Ollama
            system_prompt: Optional system prompt to guide the model's behavior
            
        Returns:
            The model's response as a string
        """
        url = f"{self.ollama_base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        if system_prompt:
            payload["system"] = system_prompt
            
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except Exception as e:
            return f"Ollama processing failed: {str(e)}"
    
    def parse_query(self, query: str) -> Dict[str, Any]:
        """
        Parse a natural language query to identify arithmetic operations and numbers.
        
        Args:
            query: Natural language query about arithmetic
            
        Returns:
            Dictionary with parsed operation and numbers
        """
        system_prompt = """You are a math query parser. 
        Your job is to identify arithmetic operations and extract the numbers involved.
        Respond ONLY with a JSON object containing:
        1. "operation": one of "add", "subtract", "multiply", "divide", "power", "square_root", or "expression"
        2. "numbers": array of numbers involved (1-2 numbers depending on operation)
        3. "expression": the full mathematical expression if operation is "expression"
        
        If the query cannot be interpreted as an arithmetic operation, set "operation" to "unknown".
        """
        
        prompt = f"""Parse this mathematical query and extract the operation and numbers:
        
        "{query}"
        
        Return ONLY a JSON object with operation type and numbers."""
        
        # Get the LLM's interpretation
        response = self.process_with_ollama(prompt, system_prompt)
        
        # Try to extract the JSON response
        try:
            # Look for JSON-like content in the response
            json_match = re.search(r'({[\s\S]*})', response)
            if json_match:
                json_str = json_match.group(1)
                parsed = json.loads(json_str)
                return parsed
            else:
                # Fallback if no JSON structure found
                return {"operation": "unknown", "error": "Could not parse JSON from LLM response"}
        except json.JSONDecodeError:
            # If JSON parsing fails
            return {"operation": "unknown", "error": "Invalid JSON in LLM response"}
        except Exception as e:
            return {"operation": "unknown", "error": str(e)}
    
    def execute_operation(self, operation: str, numbers: List[float], expression: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the identified arithmetic operation.
        
        Args:
            operation: The name of the operation to perform
            numbers: List of numbers to use in the operation
            expression: Full expression string (for "expression" operation)
            
        Returns:
            Dictionary with operation results and metadata
        """
        result = None
        error = None
        
        try:
            if operation == "add" and len(numbers) >= 2:
                result = self.add(numbers[0], numbers[1])
            elif operation == "subtract" and len(numbers) >= 2:
                result = self.subtract(numbers[0], numbers[1])
            elif operation == "multiply" and len(numbers) >= 2:
                result = self.multiply(numbers[0], numbers[1])
            elif operation == "divide" and len(numbers) >= 2:
                result = self.divide(numbers[0], numbers[1])
            elif operation == "power" and len(numbers) >= 2:
                result = self.power(numbers[0], numbers[1])
            elif operation == "square_root" and len(numbers) >= 1:
                result = self.square_root(numbers[0])
            elif operation == "expression" and expression:
                result = self.calculate_expression(expression)
            else:
                error = "Unknown operation or insufficient numbers"
                
        except Exception as e:
            error = str(e)
            
        return {
            "operation": operation,
            "numbers": numbers,
            "expression": expression,
            "result": result,
            "error": error
        }
    
    def format_response(self, operation_result: Dict[str, Any], original_query: str) -> str:
        """
        Format the arithmetic results into a natural language response.
        
        Args:
            operation_result: Dictionary with operation results from execute_operation
            original_query: The original natural language query
            
        Returns:
            Formatted response string
        """
        system_prompt = """You are a helpful math assistant.
        Your job is to explain arithmetic calculations in a clear, natural way.
        You will receive the original query and the result of the calculation.
        Provide a friendly, helpful response that shows the calculation and explains the answer.
        """
        
        prompt = f"""Original query: "{original_query}"

Calculation details:
- Operation: {operation_result['operation']}
- Numbers: {operation_result['numbers']}
- Result: {operation_result['result']}
- Error: {operation_result['error']}

Please give a natural language response explaining the calculation and result."""
        
        response = self.process_with_ollama(prompt, system_prompt)
        return response
    
    def run(self, query: str) -> Dict[str, Any]:
        """
        Process a natural language query about arithmetic operations.
        
        Args:
            query: Natural language query about an arithmetic operation
            
        Returns:
            Dictionary with results and natural language response
        """
        # Step 1: Parse the query to identify operation and numbers
        parsed = self.parse_query(query)
        
        # Step 2: Execute the identified operation
        operation = parsed.get("operation", "unknown")
        numbers = parsed.get("numbers", [])
        expression = parsed.get("expression", None)
        
        operation_result = self.execute_operation(operation, numbers, expression)
        
        # Step 3: Generate a natural language response
        response_text = self.format_response(operation_result, query)
        
        # Return complete results including raw operation result and formatted response
        return {
            "original_query": query,
            "operation": operation,
            "numbers": numbers,
            "expression": expression,
            "result": operation_result["result"],
            "error": operation_result["error"],
            "response": response_text
        }


# Example usage
if __name__ == "__main__":
    # Create the agent
    agent = ArithmeticOllamaAgent()
    
    # Test with some sample queries
    test_queries = [
        "What is 25 plus 17?",
        "Calculate 125 divided by 5",
        "What's the square root of 144?",
        "If I have 7 apples and eat 3, how many do I have left?",
        "Multiply 12.5 by 6",
        "What is 2 raised to the power of 8?",
        "Calculate 3 + 4 * 2 - 1",
        "What is 10% of 250?"
    ]
    
    # Process each query
    for query in test_queries:
        print(f"\n===== QUERY: {query} =====")
        try:
            result = agent.run(query)
            if result["error"]:
                print(f"Error: {result['error']}")
            else:
                print(f"Operation: {result['operation']}")
                print(f"Numbers: {result['numbers']}")
                if result['expression']:
                    print(f"Expression: {result['expression']}")
                print(f"Result: {result['result']}")
                print("\nResponse:")
                print(result['response'])
        except Exception as e:
            print(f"Failed to process query: {str(e)}")
