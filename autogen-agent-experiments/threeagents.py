import ollama
import requests
import base64
import json
import threading
import queue
import time
import uuid

class Agent:
    def __init__(self, name, role, initial_context, model='llama3.2'):
        self.name = name
        self.role = role
        self.initial_context = initial_context
        self.model = model
        
    def generate_response(self, messages):
        try:
            system_prompt = f"You are {self.name}, {self.role}. {self.initial_context}"
            
            response = ollama.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system_prompt}
                ] + messages
            )
            return response['message']['content']
        except Exception as e:
            print(f"Error in {self.name}'s response generation: {e}")
            return f"Error: {str(e)}"

class ExternalAPIAgent(Agent):
    def __init__(self, name, url, username, password):
        super().__init__(name, "customer support resolver", "Help resolve customer issues")
        self.url = url
        self.username = username
        self.password = password
    
    def call_external_api(self, prompt):
        try:
            # Create Basic Authentication header
            credentials = f"{self.username}:{self.password}"
            encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Basic {encoded_credentials}'
            }
            
            payload = {
                "prompt": prompt
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
    def __init__(self, agents):
        self.agents = agents
        self.message_queue = queue.Queue()
        self.conversation_history = []
    
    def simulate_conversation(self, num_rounds=30):
        for round in range(num_rounds):
            print(f"\n--- Round {round + 1} ---")
            round_messages = []
            
            # Each agent generates a message
            for i, agent in enumerate(self.agents):
                if isinstance(agent, ExternalAPIAgent):
                    # External API agent resolves issues from other agents
                    if len(round_messages) > 0:
                        # Combine previous messages as context for resolution
                        external_prompt = " ".join([
                            f"{msg.get('name', 'Agent')}: {msg['content']}" 
                            for msg in round_messages
                        ])
                        resolution = agent.call_external_api(external_prompt)
                        round_messages.append({
                            'role': 'assistant', 
                            'name': agent.name, 
                            'content': resolution
                        })
                else:
                    # Regular agents generate their responses
                    if i == 0:
                        # First agent (grocery customer) initiates with initial issue
                        initial_message = {
                            'role': 'user', 
                            'name': agent.name, 
                            'content': agent.initial_context
                        }
                        round_messages.append(initial_message)
                        
                        response = agent.generate_response([initial_message])
                        round_messages.append({
                            'role': 'assistant', 
                            'name': agent.name, 
                            'content': response
                        })
                    else:
                        # Other agents respond based on conversation history
                        response = agent.generate_response(self.conversation_history + round_messages)
                        round_messages.append({
                            'role': 'assistant', 
                            'name': agent.name, 
                            'content': response
                        })
            
            # Update conversation history
            self.conversation_history.extend(round_messages)
            
            # Print messages for this round
            for msg in round_messages:
                print(f"{msg.get('name', 'Agent')}: {msg['content']}")
            
            # Small delay between rounds
            time.sleep(1)

def main():
    # Create agents with specific contexts and roles
    grocery_customer = Agent(
        'Grocery Customer', 
        'an online grocery shopper facing product issues', 
        'I recently ordered fresh produce online, but the fruits and vegetables arrived in poor condition. Some are bruised, and a few items seem to have been packed incorrectly.'
    )
    
    electronics_customer = Agent(
        'Electronics Customer', 
        'an online electronics shopper experiencing technical problems', 
        'I purchased a smart home device online, but I am having trouble setting it up. The device does not connect to my home Wi-Fi network, and the accompanying app seems unresponsive.'
    )
    
    external_api_agent = ExternalAPIAgent(
        'FusionAI Agent', 
        url='https://example.com/completions',
        username='<set-api-username>', 
        password=''
    )

    # Create group chat with agents
    agents = [grocery_customer, electronics_customer, external_api_agent]
    group_chat = GroupChatManager(agents)

    # Run the simulation
    group_chat.simulate_conversation(num_rounds=3)

if __name__ == '__main__':
    main()
