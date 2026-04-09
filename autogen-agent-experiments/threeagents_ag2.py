import autogen
import requests
import base64
from typing import Dict, Optional

class ExternalAPIHandler:
    def __init__(self, url: str, username: str, password: str):
        """
        Initialize the External API Handler
        
        :param url: URL of the external API endpoint
        :param username: Basic auth username
        :param password: Basic auth password
        """
        self.url = url
        self.username = username
        self.password = password
        
    def send_to_external_api(self, message: str) -> Optional[str]:
        """
        Send message to external API and retrieve response
        
        :param message: Message to send to the API
        :return: Processed response text or None
        """
        try:
            # Prepare basic authentication
            credentials = f"{self.username}:{self.password}"
            encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
            
            # Prepare request headers and body
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "prompt": message
            }
            
            # Make the API request
            response = requests.post(self.url, json=payload, headers=headers)
            response.raise_for_status()
            
            # Parse the response
            response_data = response.json()
            if 'choices' in response_data and len(response_data['choices']) > 0:
                return response_data['choices'][0].get('text', '')
            
            return None
        
        except requests.RequestException as e:
            print(f"API Request Error: {e}")
            return None

def create_multi_agent_system():
    """
    Create a multi-agent system with manager and external API integration
    """
    # External API configuration
    API_URL = "https://example.com/completions"
    USERNAME = "<set-api-username>"
    PASSWORD = ""
    
    # Initialize external API handler
    api_handler = ExternalAPIHandler(API_URL, USERNAME, PASSWORD)
    
    # Configure Ollama for local LLaMA 3.2
    config_list = [
        {
            'model': 'llama3.2',
            'base_url': 'http://localhost:11434/v1',
            'api_type': 'open_ai',
            'api_key': 'NA',
        }
    ]
    
    # Agent: Software Engineer 
    data_analyzer = autogen.ConversableAgent(
        name="SE",
        system_message="You are a software engineer. You want to learn about Large language models and autogen",
        llm_config={
            "config_list": config_list,
            "temperature": 0.7
        },
        human_input_mode="NEVER"
    )
    
    # Agent: Autogen Expert
    strategy_planner = autogen.ConversableAgent(
        name="AG",
        system_message="You are an autogen expert, you need to respond to questions related to LLMs and autogen.",
        llm_config={
            "config_list": config_list,
            "temperature": 0.7
        },
        human_input_mode="NEVER"
    )
    
    # Agent: External API Communicator
    external_communicator = autogen.ConversableAgent(
        name="ExternalCommunicator",
        system_message="You are a langchain expert, you need to respond to questions related to LLMs and langchain.",
        llm_config={
            "config_list": config_list,
            "temperature": 0.5
        },
        human_input_mode="NEVER",
        function_map={
            "send_to_external_api": api_handler.send_to_external_api
        }
    )
    
    # Group Chat Manager
    group_chat_manager = autogen.ConversableAgent(
        name="GroupChatManager",
        system_message="You manage the conversation flow between agents, ensuring smooth communication and goal achievement.",
        llm_config={
            "config_list": config_list,
            "temperature": 0.6
        },
        human_input_mode="NEVER"
    )
    
    # Define group chat
    groupchat = autogen.GroupChat(
        agents=[data_analyzer, strategy_planner, external_communicator, group_chat_manager],
        messages=[],
        max_round=10
    )
    
    # Create group chat manager
    group_chat_runner = autogen.GroupChatManager(
        groupchat=groupchat,
        llm_config={
            "config_list": config_list,
            "temperature": 0.6
        }
    )
    
    return {
        'data_analyzer': data_analyzer,
        'strategy_planner': strategy_planner,
        'external_communicator': external_communicator,
        'group_chat_manager': group_chat_manager,
        'group_chat_runner': group_chat_runner
    }

def main():
    # Create multi-agent system
    agents = create_multi_agent_system()
    
    # Example workflow demonstration
    agents['group_chat_manager'].initiate_chat(
        agents['group_chat_runner'],
        message="Let's learn about large language models using autogen and langchain"
    )

if __name__ == "__main__":
    main()
