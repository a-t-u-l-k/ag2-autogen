# Server-side code (app.py)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import autogen
import json
import httpx
import asyncio
import uvicorn
import base64
import logging
import ssl
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure external API for completions
class ExternalLLM:
    def __init__(self, 
                 api_url="https://example.com/completions",
                 username="<set-api-username>", 
                 password="",
                 timeout=30.0):
        self.api_url = api_url
        self.username = username
        self.password = password
        self.timeout = timeout
        
        # Configure client with SSL verification disabled for testing
        # For production, proper SSL certificates should be used
        self.client = httpx.AsyncClient(
            timeout=timeout,
            verify=False,  # Disable SSL verification for testing
            follow_redirects=True
        )
        
        # Prepare authentication headers
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.auth_header = f"Basic {encoded_credentials}"
    
    async def generate(self, prompt):
        try:
            logger.info(f"Sending request to: {self.api_url}")
            
            headers = {
                "Authorization": self.auth_header,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Log the request (excluding sensitive information)
            logger.info(f"Request headers: Content-Type and Accept headers set")
            logger.info(f"Request body: {{\"prompt\": \"{prompt[:20]}...\" (truncated)}}")
            
            response = await self.client.post(
                self.api_url,
                json={"prompt": prompt},
                headers=headers
            )
            
            # Log the response status
            logger.info(f"Response status: {response.status_code}")
            
            # Check if the request was successful
            if response.status_code == 200:
                result = response.json()
                logger.info("Successfully parsed JSON response")
                
                # Extract the response text from the specified format
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["text"]
                else:
                    logger.error(f"Invalid response format: {result}")
                    return "Error: Invalid response format from API"
            else:
                # Log the error response
                logger.error(f"API error: {response.status_code} - {response.text}")
                return f"Error: API returned status code {response.status_code}. Response: {response.text}"
        except httpx.ConnectError as e:
            logger.error(f"Connection error: {str(e)}")
            return f"Error connecting to API: Connection refused or timed out"
        except httpx.SSLError as e:
            logger.error(f"SSL error: {str(e)}")
            return f"Error connecting to API: SSL certificate verification failed"
        except httpx.TimeoutException as e:
            logger.error(f"Timeout error: {str(e)}")
            return f"Error connecting to API: Request timed out after {self.timeout} seconds"
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return f"Error: Invalid JSON response from API"
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return f"Error connecting to API: {str(e)}"
    
    async def close(self):
        await self.client.aclose()

# Initialize External LLM
external_llm = ExternalLLM()

# Create AutoGen assistant agent
assistant_config = {
    "name": "Assistant",
    "system_message": "You are a helpful AI assistant. Provide clear, concise, and accurate responses."
}

class CustomAssistantAgent(autogen.AssistantAgent):
    async def generate_reply(self, messages, sender):
        prompt = self._construct_prompt(messages)
        response = await external_llm.generate(prompt)
        return response
    
    def _construct_prompt(self, messages):
        """Convert messages to a single prompt string"""
        prompt = ""
        for message in messages[-5:]:  # Using last 5 messages for context
            role = message["role"]
            content = message["content"]
            prompt += f"{role}: {content}\n"
        prompt += "Assistant: "
        return prompt

# Create the agent
assistant = CustomAssistantAgent(**assistant_config)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections = {}
        self.conversation_history = {}
    
    async def connect(self, websocket, client_id):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        if client_id not in self.conversation_history:
            self.conversation_history[client_id] = []
    
    def disconnect(self, client_id):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
    
    async def send_message(self, message, client_id):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)
    
    def add_to_history(self, client_id, message):
        if client_id not in self.conversation_history:
            self.conversation_history[client_id] = []
        self.conversation_history[client_id].append(message)

manager = ConnectionManager()

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Add user message to history
            user_message = {
                "role": "user",
                "content": message_data["message"]
            }
            manager.add_to_history(client_id, user_message)
            
            # Process with autogen agent
            logger.info(f"Processing message from client {client_id}")
            reply = await assistant.generate_reply(
                manager.conversation_history[client_id], 
                "user"
            )
            
            # Add assistant response to history
            assistant_message = {
                "role": "assistant",
                "content": reply
            }
            manager.add_to_history(client_id, assistant_message)
            
            # Send response back to the client
            await manager.send_message(
                json.dumps({"message": reply, "sender": "assistant"}),
                client_id
            )
            
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"Error in websocket handler: {str(e)}", exc_info=True)
        await websocket.send_text(json.dumps({
            "message": f"Server error: {str(e)}",
            "sender": "system"
        }))
        manager.disconnect(client_id)

@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "ok"}

@app.on_event("startup")
async def startup_event():
    logger.info("Server starting up")
    # Disable SSL warnings for requests with verify=False
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Server shutting down")
    await external_llm.close()

if __name__ == "__main__":
    print("Starting server on port 8000...")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
