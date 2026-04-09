import autogen as ag
import os
import json
import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Union
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
import base64

# Download NLTK resources for sentiment analysis
nltk.download('vader_lexicon')

# Initialize FastAPI app
app = FastAPI(title="AG2 Customer Service Chat Application")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Configure Autogen
config_list = [
    {
        "model": "external-api",
        "api_key": "not-needed"
    }
]

# External API configuration
EXTERNAL_API_URL = "https://example.com/completions"
EXTERNAL_API_USERNAME = "<set-api-username>"
EXTERNAL_API_PASSWORD = ""

# Initialize Sentiment Analyzer
sentiment_analyzer = SentimentIntensityAnalyzer()

# Conversation context and history
conversation_history = []
agent_sentiment = 0
user_sentiment = 0

class MessageRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class MessageResponse(BaseModel):
    response: str
    responder_type: str  # "agent" or "supervisor"
    user_sentiment: float
    agent_sentiment: float

# Custom LLM that calls the external API
class ExternalApiLLM:
    def __init__(self):
        self.url = EXTERNAL_API_URL
        self.username = EXTERNAL_API_USERNAME
        self.password = EXTERNAL_API_PASSWORD
    
    def generate(self, prompt, config=None):
        # Include conversation history for context
        full_prompt = f"Conversation history: {conversation_history}\n\nCurrent message: {prompt}"
        
        # Prepare the request payload
        payload = {
            "prompt": full_prompt
        }
        
        # Make the API call with basic authentication
        response = requests.post(
            self.url, 
            json=payload,
            auth=(self.username, self.password)
        )
        
        if response.status_code != 200:
            raise Exception(f"External API returned error: {response.status_code}, {response.text}")
        
        response_data = response.json()
        generated_text = response_data["choices"][0]["text"]
        
        return {"content": generated_text}

# Configure the external API client
external_api_llm = ExternalApiLLM()

# Create AG2 agents
customer_service_agent = ag.AssistantAgent(
    name="CustomerServiceAgent",
    llm_config={"config_list": config_list},
    system_message="""You are a helpful customer service agent for a subscription service. 
    Be polite, informative, and try to address customer questions directly."""
)

end_user_agent = ag.UserProxyAgent(
    name="EndUserAgent",
    human_input_mode="NEVER",
    code_execution_config=False,
    llm_config={"config_list": config_list},
    system_message="""You are simulating an end user asking questions about services.
    You will ask typical customer questions about subscriptions, billing, features, and support."""
)

supervisor_agent = ag.AssistantAgent(
    name="SupervisorAgent",
    llm_config={"config_list": config_list},
    system_message="""You are a supervisor who takes over when customer satisfaction is low.
    Your goal is to de-escalate the situation and improve customer sentiment. 
    Be extremely empathetic, proactive in offering solutions, and prioritize customer satisfaction."""
)

def analyze_sentiment(text):
    """Analyze sentiment of a text and return score between -1 and 1"""
    sentiment_scores = sentiment_analyzer.polarity_scores(text)
    return sentiment_scores['compound']  # Compound score ranges from -1 (negative) to 1 (positive)

def custom_generate_response(user_message):
    global conversation_history, agent_sentiment, user_sentiment
    
    # Add user message to conversation history
    conversation_history.append(f"User: {user_message}")
    
    # Analyze user sentiment
    user_sentiment = analyze_sentiment(user_message)
    
    # Determine which agent should respond
    responding_agent = supervisor_agent if user_sentiment < 0 else customer_service_agent
    responder_type = "supervisor" if user_sentiment < 0 else "agent"
    
    # Get response from the appropriate agent using the external API
    prompt = f"You are a {responding_agent.name}. Based on the conversation history and the latest user message, provide a response.\n\nUser message: {user_message}"
    response_data = external_api_llm.generate(prompt)
    response_text = response_data["content"]
    
    # Analyze agent sentiment
    agent_sentiment = analyze_sentiment(response_text)
    
    # Add agent response to conversation history
    conversation_history.append(f"{responding_agent.name}: {response_text}")
    
    # If conversation history gets too long, retain only the latest exchanges
    if len(conversation_history) > 20:
        conversation_history = conversation_history[-10:]
    
    return {
        "response": response_text,
        "responder_type": responder_type,
        "user_sentiment": user_sentiment,
        "agent_sentiment": agent_sentiment
    }

# Function to authenticate using the Authorization header
def get_auth_user(authorization: Optional[str] = Header(None)):
    """Parse the Authorization header and authenticate the user"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    try:
        scheme, credentials = authorization.split()
        if scheme.lower() != "basic":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Basic"},
            )
        
        decoded = base64.b64decode(credentials).decode("utf-8")
        username, password = decoded.split(":", 1)
        
        # Hardcoded credentials for simplicity
        correct_username = "<set-api-username>"
        correct_password = "<set-api-password>"
        
        if username != correct_username or password != correct_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Basic"},
            )
        
        return username
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}",
            headers={"WWW-Authenticate": "Basic"},
        )

# Debug endpoint to help diagnose request issues
@app.post("/debug")
async def debug_request(request: Request, username: str = Depends(get_auth_user)):
    body = await request.body()
    headers = dict(request.headers)
    return {
        "headers": headers,
        "body": body.decode() if body else None,
        "method": request.method,
        "url": str(request.url)
    }

# API Routes
@app.post("/chat", response_model=MessageResponse)
async def chat(message_request: MessageRequest, username: str = Depends(get_auth_user)):
    try:
        # Process the message
        result = custom_generate_response(message_request.message)
        
        return MessageResponse(
            response=result["response"],
            responder_type=result["responder_type"],
            user_sentiment=result["user_sentiment"],
            agent_sentiment=result["agent_sentiment"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/reset")
async def reset_conversation(username: str = Depends(get_auth_user)):
    global conversation_history, agent_sentiment, user_sentiment
    conversation_history = []
    agent_sentiment = 0
    user_sentiment = 0
    return {"status": "Conversation reset successfully"}

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
