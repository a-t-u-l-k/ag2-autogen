# server.py
import json
import asyncio
import uvicorn
import requests
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from autogen import Agent, AssistantAgent
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# Download NLTK data for sentiment analysis
try:
    nltk.data.find('vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon')

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# API endpoint for external LLM service
EXTERNAL_API_URL = "https://example.com/completions"
API_USERNAME = "<set-api-username>"
API_PASSWORD = ""

# Track active connections
active_connections: List[WebSocket] = []

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()

# Class to make external API calls
class ExternalAPIService:
    def __init__(self):
        self.auth_header = "Basic " + base64.b64encode(f"{API_USERNAME}:{API_PASSWORD}".encode()).decode()
        
    async def call_external_api(self, prompt):
        # Prepare request data
        headers = {
            "Authorization": self.auth_header,
            "Content-Type": "application/json"
        }
        data = {"prompt": prompt}
        
        # Make the API call
        try:
            response = requests.post(EXTERNAL_API_URL, headers=headers, json=data)
            response.raise_for_status()
            response_data = response.json()
            
            # Extract text from the response format
            response_text = response_data["choices"][0]["text"]
            return response_text
        except requests.exceptions.RequestException as e:
            return f"Error calling external API: {str(e)}"

# Custom agent implementation to work with external API
class CustomServiceAgent(AssistantAgent):
    def __init__(self, name, system_message):
        super().__init__(name=name, system_message=system_message)
        self.api_service = ExternalAPIService()
    
    async def generate_response(self, messages):
        last_message = messages[-1]["content"] if messages else ""
        return await self.api_service.call_external_api(last_message)

# Initialize agents
class ChatSystem:
    def __init__(self):
        # Initialize the service agent with the external API capability
        self.service_agent = CustomServiceAgent(
            name="service_agent",
            system_message="You are a helpful service agent that assists customers with their subscribed services. Be polite and professional."
        )
        
        # Initialize the supervisor agent
        self.supervisor_agent = AssistantAgent(
            name="supervisor_agent",
            system_message="You are a supervisor that takes over when the customer sentiment is negative. Your goal is to improve the customer experience and turn negative sentiment into positive."
        )
        
        # Current active agent (service_agent or supervisor_agent)
        self.current_agent = self.service_agent
        self.conversation_history = []
        self.customer_sentiment = 0.0
        self.api_service = ExternalAPIService()
    
    def analyze_sentiment(self, message):
        sentiment_scores = sia.polarity_scores(message)
        return sentiment_scores['compound']  # Returns a score between -1 (negative) and 1 (positive)
    
    async def process_message(self, user_message):
        # Add user message to conversation history
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # Analyze user sentiment
        self.customer_sentiment = self.analyze_sentiment(user_message)
        
        # Decide which agent should respond
        if self.customer_sentiment < 0 and self.current_agent == self.service_agent:
            # Sentiment is negative, supervisor takes over
            self.current_agent = self.supervisor_agent
            agent_intro = "Supervisor has taken over the conversation."
        elif self.customer_sentiment >= 0 and self.current_agent == self.supervisor_agent:
            # Sentiment is positive again, service agent takes back
            self.current_agent = self.service_agent
            agent_intro = "Service agent has resumed the conversation."
        else:
            agent_intro = None
        
        # Create context with conversation history
        context = "\n".join([f"{item['role']}: {item['content']}" for item in self.conversation_history])
        
        # Get response
        if self.current_agent == self.service_agent:
            # Service agent uses external API
            prompt = f"Context of the conversation:\n{context}\n\nPlease respond to the latest message: {user_message}"
            response = await self.api_service.call_external_api(prompt)
        else:
            # Supervisor agent handles responses directly
            prompt = f"Context of the conversation:\n{context}\n\nThe customer seems unhappy. Please respond to their message in a way that improves their experience."
            response = await self.api_service.call_external_api(prompt)
        
        # Add agent response to conversation history
        self.conversation_history.append({"role": "assistant", "content": response})
        
        # Return response with sentiment info and agent intro if applicable
        result = {
            "response": response,
            "sentiment": self.customer_sentiment,
            "agent": self.current_agent.name
        }
        
        if agent_intro:
            result["agent_intro"] = agent_intro
        
        return result

# Initialize chat system
chat_system = ChatSystem()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
                user_message = message_data.get("message", "")
                
                # Process the message through our agents
                result = await chat_system.process_message(user_message)
                
                # Send response back to client
                await websocket.send_json(result)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON format"})
    except WebSocketDisconnect:
        active_connections.remove(websocket)

class Message(BaseModel):
    message: str

@app.post("/chat")
async def chat_endpoint(message: Message):
    try:
        # Process the message through our agents
        result = await chat_system.process_message(message.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
