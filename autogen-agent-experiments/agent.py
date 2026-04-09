import requests
import json
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the Ollama API endpoint
OLLAMA_API_ENDPOINT = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2"

# Define the specific REST API endpoint
REST_API_ENDPOINT = "https://api.restful-api.dev/objects/7"

class RestApiAgent:
    """An agent that calls a REST API and uses Ollama llama3.2 to process the response."""
    
    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self.name = "RestApiAgent"
        logger.info(f"Initialized {self.name} with model {self.model_name}")
    
    def call_rest_api(self) -> Dict:
        """Call the REST API and return the response as a dictionary."""
        try:
            logger.info(f"Calling REST API: {REST_API_ENDPOINT}")
            
            response = requests.get(
                REST_API_ENDPOINT,
                headers={
                    'Accept': 'application/json'
                }
            )
            
            # Check if the request was successful
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            # Extract and print name and price
            name = data.get('name', 'Name not found')
            price = data.get('data', {}).get('price', 'Price not found')
            
            print(f"Product Name: {name}")
            print(f"Price: ${price}")
            
            logger.info(f"REST API response received and processed")
            return data
            
        except Exception as e:
            logger.error(f"Error calling REST API: {str(e)}")
            raise
    
    def process_with_llm(self, text: str) -> str:
        """Process text using Ollama's llama3.2 model."""
        try:
            logger.info(f"Processing with {self.model_name}: {text}")
            
            # Prepare the prompt for Ollama
            payload = {
                "model": self.model_name,
                "prompt": text,
                "stream": False
            }
            
            # Call Ollama API
            response = requests.post(OLLAMA_API_ENDPOINT, json=payload)
            response.raise_for_status()
            
            result = response.json()
            response_text = result.get("response", "")
            
            logger.info(f"LLM processing complete")
            return response_text
            
        except Exception as e:
            logger.error(f"Error processing with LLM: {str(e)}")
            raise
    
    def process(self, task: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a task, call the REST API, and use LLM to enhance the response."""
        logger.info(f"Processing task")
        
        try:
            # Call the REST API
            api_response = self.call_rest_api()
            
            # Extract the relevant information for the LLM
            name = api_response.get('name', 'Name not found')
            price = api_response.get('data', {}).get('price', 'Price not found')
            
            # Process the API response with the LLM
            prompt = f"""
            I have a product with the following details:
            - Name: {name}
            - Price: ${price}
            
            Please provide a brief market analysis of this product considering its price point.
            """
            
            llm_processed_response = self.process_with_llm(prompt)
            
            # Return both the raw API response and the LLM-processed response
            return {
                "output": llm_processed_response,
                "raw_api_response": api_response,
                "name": name,
                "price": price
            }
            
        except Exception as e:
            error_message = f"Error processing request: {str(e)}"
            logger.error(error_message)
            return {
                "output": error_message,
                "error": True
            }


def main():
    """Example usage of the RestApiAgent."""
    try:
        # Create the agent
        agent = RestApiAgent()
        
        # Process without needing input since we're using a fixed URL
        result = agent.process()
        
        # Print the key information
        print("\nAgent result summary:")
        print(f"Product: {result.get('name')}")
        print(f"Price: ${result.get('price')}")
        print("\nLLM Analysis:")
        print(result.get('output'))
        
    except Exception as e:
        logger.error(f"Error running agent: {str(e)}")


if __name__ == "__main__":
    main()
