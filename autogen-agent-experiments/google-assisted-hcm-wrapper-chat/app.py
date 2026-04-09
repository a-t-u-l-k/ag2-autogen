from fastapi import FastAPI, WebSocketDisconnect, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import requests
import asyncio
from typing import List, Dict, Any
import autogen
from autogen import Agent, AssistantAgent, UserProxyAgent
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# External API configuration
EXTERNAL_API_URL = "https://example.com/completions"
EXTERNAL_API_USERNAME = "<set-api-username>"
EXTERNAL_API_PASSWORD = ""

# WebSocket connections store
active_connections: List[WebSocket] = []

# Create AutoGen agents
class AutoGenAgentManager:
    def __init__(self):
        # Create the assistant agent that connects to external API
        self.primary_agent = AssistantAgent(
            name="primary_agent",
            llm_config=False,  # Don't use default LLM
            system_message="You are a helpful assistant. You will receive queries from users and respond based on information from an external API. Your name is Atul Kumar",
        )
        
        # Create the research assistant agent
        self.research_agent = AssistantAgent(
            name="research_agent",
            # Configure Ollama for local LLaMA 3.2
            llm_config={
                "config_list": [
			        {
			            'model': 'llama3.2',
			            'base_url': 'http://localhost:11434/v1',
			            'api_key': 'NA',
			        }
				],
                "temperature": 0.7,
            },
            system_message="You are a research assistant. You help by searching for information when needed and providing it to the primary agent. Your name is Atul Kumar Google"
        )
        
        # Create user proxy for handling messages between agents
        self.user_proxy = UserProxyAgent(
            name="user_proxy",
            human_input_mode="NEVER",
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
            code_execution_config=False
        )
    
    def custom_generate_reply(self, messages, sender, config):
        """Custom method to call external API instead of default LLM"""
        # Extract the latest user message
        user_message = messages[-1]["content"] if messages else ""
        
        try:
            # Call the external API
            response = requests.post(
                EXTERNAL_API_URL,
                json={"prompt": user_message},
                auth=(EXTERNAL_API_USERNAME, EXTERNAL_API_PASSWORD),
                timeout=30
            )
            
            # Process the response
            if response.status_code == 200:
                response_data = response.json()
                if "choices" in response_data and len(response_data["choices"]) > 0:
                    reply_text = response_data["choices"][0]["text"]
                    return {"content": reply_text, "role": "assistant"}
                else:
                    return {"content": "Received empty response from external API", "role": "assistant"}
            else:
                return {"content": f"Error from external API: {response.status_code}", "role": "assistant"}
        except Exception as e:
            logger.error(f"Error calling external API: {str(e)}")
            return {"content": f"Error processing your request: {str(e)}", "role": "assistant"}
    
    async def get_research_info(self, query: str) -> str:
        """Simulate research agent getting information"""
        api_key = '<set-google-api-key>'
        cse_id = '<set-google-cse-id>'
        # FIXME- implement actual search functionality here
        #return f"Research results for: {query}"
        return google_search(query, api_key, cse_id)
    
    async def process_message(self, user_message: str) -> str:
        """Process user message through the agent system"""
        # First, check if research is needed (simple keyword check)
        needs_research = any(keyword in user_message.lower() for keyword in 
                            ["search", "news", "weather", "latest", "current", "recent", "stock"])
        
        if needs_research:
            # Ask research agent for information
            research_result = await self.get_research_info(user_message)
            print("google search result:", research_result)
            # Combine original query with research
            enhanced_query = f"{user_message}\n\nContextual information: {research_result}"
            
            # Send enhanced query to primary agent
            response = self.custom_generate_reply([{"content": enhanced_query, "role": "user"}], "user_proxy", {})
        else:
            # Direct query to primary agent
            response = self.custom_generate_reply([{"content": user_message, "role": "user"}], "user_proxy", {})
        
        # Return the content from the response
        return response.get("content", "No response generated")

# Create an instance of the agent manager
agent_manager = AutoGenAgentManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Process message through agents
            response = await agent_manager.process_message(message_data["message"])
            
            # Send response back to client
            await websocket.send_json({
                "message": response,
                "sender": "bot"
            })
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        logger.error(f"Error in websocket connection: {str(e)}")
        if websocket in active_connections:
            active_connections.remove(websocket)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

def google_search(query, api_key, cse_id, **kwargs):
    service_url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'q': query,
        'key': api_key,
        'cx': cse_id,
        **kwargs
    }
    response = requests.get(service_url, params=params)
    response.raise_for_status()  # Raise an error for bad status codes
    search_results = response.json()

    # Extract and format the results
    results = []
    if 'items' in search_results:
        for item in search_results['items']:
            results.append({
                'title': item.get('title', ''),
                'link': item.get('link', ''),
                'snippet': item.get('snippet', '')
            })
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
