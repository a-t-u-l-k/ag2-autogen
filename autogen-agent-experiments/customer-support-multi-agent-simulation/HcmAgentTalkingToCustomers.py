import autogen
import requests
import base64
import time
import random
from typing import Dict, Optional, List

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
            return f"I apologize, but I'm having trouble connecting to our knowledge base. Let me help you with what I know. {str(e)}"

def create_multi_agent_system():
    """
    Create a multi-agent system with updated roles and external API integration
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
            'api_key': 'NA'
        }
    ]
    
    # Agent: Internet Customer
    internet_customer = autogen.ConversableAgent(
        name="ServicesCustomer",
        system_message="""You are a customer facing issues with Internet services. 
        Your role is to ask questions about your internet connection problems, express frustration when appropriate, 
        and provide details when asked. Be specific about your issues such as connection drops, slow speeds, 
        or router problems. Respond naturally as a customer seeking help. Limit your questions to 100 words.""",
        llm_config={
            "config_list": config_list,
            "temperature": 0.7
        },
        human_input_mode="NEVER"
    )
    
    # Agent: Electronics Customer 
    electronics_customer = autogen.ConversableAgent(
        name="GadgetsCustomer",
        system_message="""You are a customer facing issues with electronic products.
        Your role is to ask questions about your electronic device problems, express concerns when appropriate,
        and provide details when asked. Focus on issues with smartphones, laptops, TVs, or other consumer electronics.
        Be specific about problems like battery issues, software glitches, or hardware malfunctions. 
        Respond naturally as a customer seeking technical support. Limit your questions to 100 words.""",
        llm_config={
            "config_list": config_list,
            "temperature": 0.7
        },
        human_input_mode="NEVER"
    )
    
    # Agent: Support Agent
    support_agent = autogen.ConversableAgent(
        name="FusionAI-Agent",
        system_message="""You are a customer support specialist who answers questions about both internet services 
        and electronic products. For complex or specialized questions, you consult an external knowledge base API 
        by calling the send_to_external_api function. Ensure you format customer questions appropriately before 
        sending them to the API. When you receive a response, interpret it and communicate it clearly to the customer.
        Be empathetic, professional, and solution-oriented. Limit your response to 100 words""",
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
        name="Supervisor",
        system_message="""You manage the conversation flow between customers and support agents. 
        Your job is to ensure smooth communication, introduce new topics when conversations conclude,
        and help transition between different customer issues. Do not take human input but operate 
        autonomously to facilitate productive conversations.""",
        llm_config={
            "config_list": config_list,
            "temperature": 0.6
        },
        human_input_mode="NEVER",
        code_execution_config=False
    )
    
    # Define group chat
    groupchat = autogen.GroupChat(
        agents=[internet_customer, electronics_customer, support_agent, group_chat_manager],
        messages=[],
        max_round=5  # Increased to accommodate more exchanges
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
        'internet_customer': internet_customer,
        'electronics_customer': electronics_customer,
        'support_agent': support_agent,
        'group_chat_manager': group_chat_manager,
        'group_chat_runner': group_chat_runner
    }

# Test data for 10 chat sessions
def generate_test_sessions() -> List[Dict[str, List[str]]]:
    """Generate test data for 10 chat sessions"""
    
    internet_customer_questions = [
        "My internet keeps dropping every few minutes. I've restarted the router but it's not helping.",
        "I'm only getting 10Mbps download speed when I'm paying for 100Mbps. What's going on?",
        "My Wi-Fi signal is very weak in certain parts of my house. How can I extend the range?",
        "I'm experiencing very high latency when gaming online. Is there something wrong with my connection?",
        "I just moved to a new apartment and need to set up my internet service. What are the steps?",
        "After the thunderstorm yesterday, my internet hasn't been working at all.",
        "I noticed unauthorized devices connected to my Wi-Fi network. How can I secure it better?",
        "My internet bill is higher than expected this month. Can you explain the charges?",
        "I'm trying to connect my smart TV to Wi-Fi but it keeps failing. Can you help?",
        "When I try to stream HD videos, they keep buffering constantly. Is this a bandwidth issue?"
    ]
    
    electronics_customer_questions = [
        "My new smartphone battery drains completely in just 4 hours. Is this normal?",
        "My laptop won't turn on at all. The power light blinks once then nothing happens.",
        "The screen on my tablet has strange colored lines appearing. Can this be fixed?",
        "My wireless headphones won't pair with my phone anymore after the latest update.",
        "I purchased a smart thermostat but I'm having trouble connecting it to my home network.",
        "My printer keeps showing a 'paper jam' error but there's no paper stuck in it.",
        "The touchscreen on my smartphone has become unresponsive in certain areas.",
        "My digital camera is showing a 'memory card error' even with a brand new card.",
        "The sound on my smart TV cuts out randomly during shows. How can I troubleshoot this?",
        "After spilling water on my keyboard, several keys aren't working. Is there a fix?"
    ]
    
    sessions = []
    
    for i in range(10):
        session = {
            "internet_customer": [random.choice(internet_customer_questions)],
            "electronics_customer": [random.choice(electronics_customer_questions)]
        }
        sessions.append(session)
    
    return sessions

def run_simulation(agents, sessions):
    """
    Run a simulation of customer support sessions
    
    :param agents: Dictionary of agent objects
    :param sessions: List of session data dictionaries
    """
    for i, session in enumerate(sessions):
        print(f"\n{'='*80}\nSTARTING SESSION {i+1}\n{'='*80}")
        
        # Determine which customer goes first (alternate)
        first_customer = "internet_customer" if i % 2 == 0 else "electronics_customer"
        
        if first_customer == "internet_customer":
            initial_message = f"[Session {i+1}] InternetCustomer: {session['internet_customer'][0]}"
        else:
            initial_message = f"[Session {i+1}] ElectronicsCustomer: {session['electronics_customer'][0]}"
        
        # Start the chat with a specific issue
        agents['group_chat_manager'].initiate_chat(
            agents['group_chat_runner'],
            message=initial_message
        )
        
        # Allow some time before starting the next session
        time.sleep(2)

def main():
    # Create multi-agent system
    agents = create_multi_agent_system()
    
    # Generate test sessions
    sessions = generate_test_sessions()
    
    # Run simulation
    run_simulation(agents, sessions)

if __name__ == "__main__":
    main()
