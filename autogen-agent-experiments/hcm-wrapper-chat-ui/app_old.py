# Server-side code (app.py)
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import autogen
import json
import httpx
import asyncio
import uvicorn

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure autogen agent with Ollama LLama 3.2
class OllamaLLM:
    def __init__(self, model="llama3.2", base_url="http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def generate(self, prompt, **kwargs):
        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": kwargs.get("options", {})
            }
        )
        result = response.json()
        return result["response"]
    
    async def close(self):
        await self.client.aclose()

# Initialize Ollama LLM
ollama_llm = OllamaLLM()

# Create AutoGen assistant agent
assistant_config = {
    "name": "Assistant",
    "system_message": "You are a helpful AI assistant powered by LLama 3.2. Provide clear, concise, and accurate responses."
}

class CustomAssistantAgent(autogen.AssistantAgent):
    async def generate_reply(self, messages, sender):
        prompt = self._construct_prompt(messages)
        response = await ollama_llm.generate(prompt)
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
        manager.disconnect(client_id)
    except Exception as e:
        print(f"Error: {str(e)}")
        manager.disconnect(client_id)

@app.on_event("shutdown")
async def shutdown_event():
    await ollama_llm.close()

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
