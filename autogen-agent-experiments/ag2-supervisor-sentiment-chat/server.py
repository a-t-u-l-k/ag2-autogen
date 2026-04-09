import os
import json
import base64
import asyncio
import httpx
import uvicorn
import autogen as ag
from fastapi import FastAPI, WebSocket, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from textblob import TextBlob

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTP Basic Auth
security = HTTPBasic()

# Config
API_URL = "https://example.com/completions"
API_USERNAME = "<set-api-username>"
API_PASSWORD = ""

# Model for chat requests
class ChatMessage(BaseModel):
    message: str
    sender: str

# Model for chat responses
class ChatResponse(BaseModel):
    message: str
    sender: str
    sentiment: float = 0.0

# Store conversation context
conversation_contexts = {}

# Sentiment analysis function
def analyze_sentiment(text: str) -> float:
    analysis = TextBlob(text)
    # Return polarity score between -1 (negative) and 1 (positive)
    return analysis.sentiment.polarity

# Function to call external API
async def call_external_api(prompt: str) -> str:
    auth_str = f"{API_USERNAME}:{API_PASSWORD}"
    auth_bytes = auth_str.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/json"
    }
    
    payload = {"prompt": prompt}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(API_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["text"]
        except httpx.HTTPError as e:
            print(f"Error calling external API: {e}")
            return f"Sorry, I encountered an error: {str(e)}"

# Initialize AutoGen agents
def create_agents(session_id: str):
    # Service agent that calls the external API
    service_agent = ag.ConversableAgent(
        name="ServiceAgent",
        system_message="You are a service agent that helps customers with their subscribed services. You respond professionally and helpfully.",
        llm_config=False,  # We'll handle the LLM calls manually
    )
    
    # User agent that simulates customer queries
    user_agent = ag.ConversableAgent(
        name="CustomerAgent",
        system_message="You are simulating a customer who has questions about their subscribed services.",
        llm_config=False,  # We're simulating this agent
    )
    
    # Supervisor agent that intervenes when customer sentiment is negative
    supervisor_agent = ag.ConversableAgent(
        name="SupervisorAgent",
        system_message="You are a supervisor who steps in when a customer is dissatisfied. Your goal is to de-escalate the situation and ensure customer satisfaction.",
        llm_config=False,  # We'll handle the LLM calls manually
    )
    
    # Register functions for the service agent to call the external API
    async def get_response_from_api(message: str, sender: str, context: Dict[str, Any] = None) -> str:
        if context is None:
            context = {}
        
        # Prepare the input for the external API with context
        context_str = json.dumps(context) if context else ""
        full_prompt = f"Context: {context_str}\nUser message: {message}"
        
        # Call the external API
        response = await call_external_api(full_prompt)
        return response
    
    service_agent.register_function(
        function_map={"get_response_from_api": get_response_from_api}
    )
    
    # Define how the service agent responds to messages
    @service_agent.register_reply
    async def service_agent_reply(self, messages: List[Dict], sender: ag.Agent, context: Dict[str, Any] = None):
        if not messages:
            return None
            
        last_message = messages[-1]
        if last_message.get("content") and last_message.get("role") == "user":
            response = await get_response_from_api(last_message["content"], sender.name, context)
            return response
        return None
    
    # Define how the supervisor agent responds to messages
    @supervisor_agent.register_reply
    async def supervisor_reply(self, messages: List[Dict], sender: ag.Agent, context: Dict[str, Any] = None):
        if not messages:
            return None
            
        last_message = messages[-1]
        if last_message.get("content") and last_message.get("role") == "user":
            # Create a specialized prompt for the supervisor
            supervisor_context = context.copy() if context else {}
            supervisor_context["intervention"] = True
            supervisor_prompt = f"Customer seems dissatisfied. Address their concerns with empathy and find a solution: {last_message['content']}"
            response = await get_response_from_api(supervisor_prompt, "SupervisorAgent", supervisor_context)
            return response
        return None
    
    return {
        "service_agent": service_agent,
        "user_agent": user_agent,
        "supervisor_agent": supervisor_agent,
        "active_agent": "service_agent",  # Track which agent is currently active
        "context": {},  # Store conversation context
    }

@app.on_event("startup")
async def startup_event():
    # Initialize session storage
    conversation_contexts.clear()

@app.get("/")
async def root():
    return {"status": "AG2 Model Context Protocol Server is running"}

@app.post("/chat/{session_id}")
async def chat(session_id: str, chat_message: ChatMessage):
    # Initialize or get session context
    if session_id not in conversation_contexts:
        conversation_contexts[session_id] = create_agents(session_id)
    
    session = conversation_contexts[session_id]
    context = session["context"]
    
    # Update context with the latest message
    if "messages" not in context:
        context["messages"] = []
    
    context["messages"].append({
        "role": chat_message.sender,
        "content": chat_message.message
    })
    
    # Determine which agent to use based on sentiment
    if chat_message.sender == "user":
        sentiment = analyze_sentiment(chat_message.message)
        
        # Switch to supervisor if sentiment is negative
        if sentiment < -0.2 and session["active_agent"] != "supervisor_agent":
            session["active_agent"] = "supervisor_agent"
            print(f"Switching to supervisor due to negative sentiment: {sentiment}")
        # Switch back to service agent if sentiment improves
        elif sentiment >= 0.0 and session["active_agent"] == "supervisor_agent":
            session["active_agent"] = "service_agent"
            print(f"Switching back to service agent due to improved sentiment: {sentiment}")
    
    # Get the active agent
    active_agent_name = session["active_agent"]
    active_agent = session[active_agent_name]
    
    # Process the message with the active agent
    if active_agent_name == "service_agent":
        response = await session["service_agent"].register_reply.functions["service_agent_reply"](
            session["service_agent"], 
            context["messages"], 
            session["user_agent"],
            context
        )
    else:  # supervisor_agent
        response = await session["supervisor_agent"].register_reply.functions["supervisor_reply"](
            session["supervisor_agent"], 
            context["messages"], 
            session["user_agent"],
            context
        )
    
    # Update context with the response
    context["messages"].append({
        "role": active_agent_name.replace("_agent", ""),
        "content": response
    })
    
    # Analyze sentiment of the response
    response_sentiment = analyze_sentiment(response)
    
    return ChatResponse(
        message=response,
        sender=active_agent_name.replace("_agent", ""),
        sentiment=response_sentiment
    )

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    if session_id in conversation_contexts:
        del conversation_contexts[session_id]
        return {"status": "Session deleted"}
    raise HTTPException(status_code=404, detail="Session not found")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
