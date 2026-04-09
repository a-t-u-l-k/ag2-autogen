import ollama
import requests
import base64
import json
import threading
import queue
import time
import uuid

class CustomerAgent:
    def __init__(self, name, initial_issue):
        self.name = name
        self.initial_issue = initial_issue
        
    def generate_query(self):
        return self.initial_issue

class ExternalAPIAgent:
    def __init__(self, name, url, username, password):
        self.name = name
        self.url = url
        self.username = username
        self.password = password
    
    def resolve_query(self, customer_query):
        try:
            # Create Basic Authentication header
            credentials = f"{self.username}:{self.password}"
            encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Basic {encoded_credentials}'
            }
            
            payload = {
                "prompt": customer_query
            }
            
            response = requests.post(
                self.url, 
                headers=headers, 
                data=json.dumps(payload)
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract the text from the response
            return result['choices'][0]['text']
        except Exception as e:
            print(f"Error calling external API: {e}")
            return f"API Error: {str(e)}"

class GroupChatManager:
    def __init__(self, customers, support_agent):
        self.customers = customers
        self.support_agent = support_agent
        self.conversation_history = []
    
    def simulate_conversation(self, num_rounds=30):
        for round in range(num_rounds):
            print(f"\n--- Round {round + 1} ---")
            
            # Each customer generates a query
            for customer in self.customers:
                # Generate customer query
                customer_query = customer.generate_query()
                
                print(f"{customer.name} Query: {customer_query}")
                
                # External API resolves the query
                resolution = self.support_agent.resolve_query(customer_query)
                
                print(f"{self.support_agent.name} Response: {resolution}")
                
                # Add to conversation history
                self.conversation_history.append({
                    'customer': customer.name,
                    'query': customer_query,
                    'resolution': resolution
                })
            
            # Small delay between rounds
            time.sleep(1)

def main():
    # Create customer agents with specific issues
    grocery_customer = CustomerAgent(
        'Grocery Customer', 
        'I recently ordered fresh produce online, but the fruits and vegetables arrived in poor condition. Some are bruised, and a few items seem to have been packed incorrectly. What can I do to resolve this issue?'
    )
    
    electronics_customer = CustomerAgent(
        'Electronics Customer', 
        'I purchased a smart home device online, but I am having trouble setting it up. The device does not connect to my home Wi-Fi network, and the accompanying app seems unresponsive. How can I troubleshoot this?'
    )
    
    # Create external API support agent
    external_api_agent = ExternalAPIAgent(
        'Fusion AI Agent', 
        url='https://example.com/completions',
        username='<set-api-username>', 
        password=''
    )

    # Create group chat manager
    group_chat = GroupChatManager(
        customers=[grocery_customer, electronics_customer], 
        support_agent=external_api_agent
    )

    # Run the simulation
    group_chat.simulate_conversation(num_rounds=30)

if __name__ == '__main__':
    main()
