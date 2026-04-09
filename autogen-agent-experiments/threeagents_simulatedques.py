import ollama
import requests
import base64
import json
import threading
import queue
import time
import random

class CustomerAgent:
    def __init__(self, name, issue_types):
        self.name = name
        self.issue_types = issue_types
        
    def generate_query(self):
        # Randomly select and generate a specific issue query
        issue_type = random.choice(self.issue_types)
        
        if self.name == 'Grocery Customer':
            grocery_queries = [
                f"I received {issue_type} that are not up to the expected quality. What should I do?",
                f"The {issue_type} I ordered are damaged during delivery. How can I get a replacement?",
                f"I'm concerned about the freshness of the {issue_type} I just received. What are my options?",
                f"The packaging for {issue_type} seems inappropriate. Can you help me with this issue?",
                f"I noticed discrepancies in the quantity of {issue_type} I ordered. How can this be resolved?"
            ]
            return random.choice(grocery_queries)
        
        elif self.name == 'Electronics Customer':
            electronics_queries = [
                f"I'm experiencing technical issues with my new {issue_type}. The device won't turn on properly.",
                f"The {issue_type} I purchased is not connecting to my home network. How can I troubleshoot this?",
                f"I need help with the setup of the {issue_type}. The user manual is not clear.",
                f"There seems to be a manufacturing defect in my {issue_type}. What are my options?",
                f"The software for my {issue_type} is not functioning as expected. Can you assist me?"
            ]
            return random.choice(electronics_queries)

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
    
    def simulate_conversation(self, num_rounds=3):
        for round in range(num_rounds):
            print(f"\n--- Round {round + 1} ---")
            
            # Each customer generates a new, random query
            for customer in self.customers:
                # Generate customer query
                customer_query = customer.generate_query()
                
                print(f"**************{customer.name} Query: {customer_query}")
                
                # External API resolves the query
                resolution = self.support_agent.resolve_query(customer_query)
                
                print(f"----------->{self.support_agent.name} Response: {resolution}")
                
                # Add to conversation history
                self.conversation_history.append({
                    'customer': customer.name,
                    'query': customer_query,
                    'resolution': resolution
                })
            
            # Small delay between rounds
            time.sleep(1)

def main():
    # Create customer agents with specific issue types
    grocery_customer = CustomerAgent(
        'Grocery Customer', 
        ['fruits', 'vegetables', 'dairy products', 'meat', 'bakery items']
    )
    
    electronics_customer = CustomerAgent(
        'Electronics Customer', 
        ['smart home device', 'smartphone', 'laptop', 'wireless earbuds', 'smart TV']
    )
    
    # Create external API support agent
    external_api_agent = ExternalAPIAgent(
        'FusionAI Agent', 
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
    group_chat.simulate_conversation(num_rounds=10)

if __name__ == '__main__':
    main()
