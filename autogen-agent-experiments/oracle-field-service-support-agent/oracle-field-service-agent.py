import os
import json
import httpx
import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure base app
app = FastAPI(title="Oracle Field Service AI Support Agent")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class ProductType(str, Enum):
    FIELD_SERVICE = "Oracle Field Service"
    INTELLIGENT_ADVISOR = "Oracle Intelligent Advisor"
    OTHER = "Other Oracle Product"

class UserInfo(BaseModel):
    user_id: str
    name: str
    email: str
    subscribed_products: List[ProductType]

class ConversationState(str, Enum):
    GREETING = "greeting"
    PRODUCT_CLARIFICATION = "product_clarification"
    PROBLEM_IDENTIFICATION = "problem_identification"
    KNOWLEDGE_LOOKUP = "knowledge_lookup"
    LIVE_AGENT_CHECK = "live_agent_check"
    WAITING_FOR_LIVE_AGENT = "waiting_for_live_agent"
    SERVICE_REQUEST_CREATION = "service_request_creation"
    RESOLUTION = "resolution"
    FOLLOW_UP = "follow_up"

class KnowledgeArticle(BaseModel):
    id: str
    title: str
    content: str
    url: str
    relevance_score: float

class LiveAgentInfo(BaseModel):
    available: bool
    wait_time_minutes: int
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None

class ServiceRequest(BaseModel):
    sr_id: str
    user_id: str
    product: ProductType
    issue_summary: str
    description: str
    created_at: datetime
    status: str = "Open"

class SentimentAnalysis(BaseModel):
    score: float  # -1.0 to 1.0
    magnitude: float  # 0.0 to +inf
    category: str  # "positive", "negative", "neutral", "mixed"
    detected_emotions: List[str] = []
    
class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str
    sender: str  # "user", "agent", "supervisor"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    sentiment: Optional[SentimentAnalysis] = None

class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    state: ConversationState = ConversationState.GREETING
    messages: List[Message] = []
    current_product: Optional[ProductType] = None
    issue_summary: Optional[str] = None
    knowledge_articles: List[KnowledgeArticle] = []
    sentiment_trend: List[SentimentAnalysis] = []
    assigned_agent_id: Optional[str] = None
    supervisor_present: bool = False
    service_request_id: Optional[str] = None
    resolved: bool = False

# In-memory database for demo purposes
conversation_db: Dict[str, Conversation] = {}
user_db: Dict[str, UserInfo] = {
    "user123": UserInfo(
        user_id="user123",
        name="John Smith",
        email="john.smith@example.com",
        subscribed_products=[ProductType.FIELD_SERVICE, ProductType.INTELLIGENT_ADVISOR]
    )
}
service_requests_db: Dict[str, ServiceRequest] = {}
knowledge_base = [
    {
        "id": "kb001",
        "title": "Changing a Technician's Working Hours",
        "content": """
        To change a technician's working hours:
        1. Navigate to the Resource Management section
        2. Select the technician from the list
        3. Click on 'Edit Schedule'
        4. Modify the working hours as needed
        5. Click 'Save Changes'
        """,
        "url": "https://docs.oracle.com/field-service/changing-technician-hours",
        "keywords": ["technician", "hours", "schedule", "working hours", "change hours"]
    },
    {
        "id": "kb002",
        "title": "Viewing the Schedule Dashboard",
        "content": """
        To access the schedule dashboard:
        1. Log in to Oracle Field Service
        2. Click on 'Dashboard' in the top navigation
        3. Select 'Schedule View' from the dropdown
        4. Filter by date or technician if needed
        """,
        "url": "https://docs.oracle.com/field-service/schedule-dashboard",
        "keywords": ["schedule", "dashboard", "view", "calendar"]
    },
    {
        "id": "kb003",
        "title": "Troubleshooting Common Error Messages",
        "content": """
        When encountering an error while viewing the schedule:
        1. Check your internet connection
        2. Clear your browser cache
        3. Ensure you have the proper permissions
        4. Try accessing from a different browser
        5. If the issue persists, contact support with the error code
        """,
        "url": "https://docs.oracle.com/field-service/troubleshooting",
        "keywords": ["error", "troubleshoot", "schedule", "view", "access denied"]
    }
]
active_agents = {
    "agent001": {"name": "Sarah Johnson", "status": "available", "current_chats": 0},
    "agent002": {"name": "Michael Lee", "status": "available", "current_chats": 1},
    "agent003": {"name": "Jessica Martinez", "status": "busy", "current_chats": 3}
}
active_supervisors = {
    "super001": {"name": "David Wilson", "status": "available"}
}

# Connected WebSocket clients
connected_clients = {}

# Model context protocol server endpoints
SENTIMENT_ANALYZER_URL = os.environ.get("SENTIMENT_ANALYZER_URL", "http://localhost:8001/analyze")
KNOWLEDGE_SEARCH_URL = os.environ.get("KNOWLEDGE_SEARCH_URL", "http://localhost:8002/search")

# Mock functions to simulate external services
async def analyze_sentiment(text: str) -> SentimentAnalysis:
    """Analyze the sentiment of a text message"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SENTIMENT_ANALYZER_URL,
                json={"text": text}
            )
            if response.status_code == 200:
                return SentimentAnalysis(**response.json())
    except Exception as e:
        print(f"Error connecting to sentiment analyzer: {e}")
    
    # Fallback simple sentiment analysis
    score = 0.0
    if "thank" in text.lower() or "great" in text.lower() or "good" in text.lower():
        score = 0.7
    elif "error" in text.lower() or "issue" in text.lower() or "problem" in text.lower():
        score = -0.3
    elif "frustrated" in text.lower() or "angry" in text.lower() or "not working" in text.lower():
        score = -0.7
    
    return SentimentAnalysis(
        score=score,
        magnitude=abs(score),
        category="positive" if score > 0.3 else "negative" if score < -0.3 else "neutral",
        detected_emotions=[]
    )

async def search_knowledge_base(query: str) -> List[KnowledgeArticle]:
    """Search the knowledge base for relevant articles"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                KNOWLEDGE_SEARCH_URL,
                json={"query": query}
            )
            if response.status_code == 200:
                return [KnowledgeArticle(**article) for article in response.json()]
    except Exception as e:
        print(f"Error connecting to knowledge search: {e}")
    
    # Fallback simple keyword matching
    results = []
    query_terms = query.lower().split()
    
    for article in knowledge_base:
        score = 0
        for term in query_terms:
            if term in article["title"].lower():
                score += 0.5
            if term in article["content"].lower():
                score += 0.3
            if term in article["keywords"]:
                score += 0.5
        
        if score > 0.5:  # Only include relevant articles
            results.append(KnowledgeArticle(
                id=article["id"],
                title=article["title"],
                content=article["content"],
                url=article["url"],
                relevance_score=score
            ))
    
    return sorted(results, key=lambda x: x.relevance_score, reverse=True)

async def get_live_agent_wait_time() -> LiveAgentInfo:
    """Get the current wait time for a live agent"""
    available_agents = [a for a, info in active_agents.items() if info["status"] == "available"]
    busy_agents = [a for a, info in active_agents.items() if info["status"] == "busy"]
    
    if available_agents:
        agent_id = available_agents[0]
        return LiveAgentInfo(
            available=True,
            wait_time_minutes=max(0, len(busy_agents) * 2),
            agent_id=agent_id,
            agent_name=active_agents[agent_id]["name"]
        )
    else:
        return LiveAgentInfo(
            available=False,
            wait_time_minutes=max(5, len(busy_agents) * 5)
        )

async def create_service_request(user_id: str, product: ProductType, issue_summary: str, description: str) -> ServiceRequest:
    """Create a new service request"""
    sr_id = f"SR-{str(uuid.uuid4())[:8]}"
    service_request = ServiceRequest(
        sr_id=sr_id,
        user_id=user_id,
        product=product,
        issue_summary=issue_summary,
        description=description,
        created_at=datetime.now()
    )
    service_requests_db[sr_id] = service_request
    return service_request

# Agent state management functions
async def process_agent_response(conversation_id: str, user_input: str) -> str:
    """Process user input and determine the next agent action"""
    if conversation_id not in conversation_db:
        return "I'm sorry, but I can't find your conversation. Let's start a new one."
    
    conversation = conversation_db[conversation_id]
    current_state = conversation.state
    
    # Add the user message to the conversation
    user_message = Message(
        conversation_id=conversation_id,
        sender="user",
        content=user_input
    )
    
    # Analyze sentiment
    sentiment = await analyze_sentiment(user_input)
    user_message.sentiment = sentiment
    conversation.messages.append(user_message)
    conversation.sentiment_trend.append(sentiment)
    
    # Check if supervisor needs to be alerted
    if sentiment.score < -0.7 or (len(conversation.sentiment_trend) > 3 and 
                                all(s.score < -0.5 for s in conversation.sentiment_trend[-3:])):
        # Alert would go here
        pass
    
    # Process based on current state
    if current_state == ConversationState.GREETING:
        # Try to identify the product and issue
        if any(product.value.lower() in user_input.lower() for product in ProductType):
            for product in ProductType:
                if product.value.lower() in user_input.lower():
                    conversation.current_product = product
                    break
            conversation.state = ConversationState.PROBLEM_IDENTIFICATION
            return f"I see you're working with {conversation.current_product.value}. What specific issue are you having today?"
        else:
            conversation.state = ConversationState.PRODUCT_CLARIFICATION
            return "Thanks for reaching out! I see you're subscribed to Oracle Field Service and Oracle Intelligent Advisor. Which product are you having issues with today?"
    
    elif current_state == ConversationState.PRODUCT_CLARIFICATION:
        # Identify which product they're using
        for product in ProductType:
            if product.value.lower() in user_input.lower():
                conversation.current_product = product
                break
        
        if not conversation.current_product:
            conversation.current_product = ProductType.FIELD_SERVICE  # Default to Field Service
        
        conversation.state = ConversationState.PROBLEM_IDENTIFICATION
        return f"Got it. You're working with {conversation.current_product.value}. What specific issue are you having today?"
    
    elif current_state == ConversationState.PROBLEM_IDENTIFICATION:
        conversation.issue_summary = user_input
        conversation.state = ConversationState.KNOWLEDGE_LOOKUP
        
        # Search knowledge base for solutions
        knowledge_articles = await search_knowledge_base(user_input)
        conversation.knowledge_articles = knowledge_articles
        
        if knowledge_articles:
            best_article = knowledge_articles[0]
            response = f"I found some information that might help with your issue: '{best_article.title}'\n\n{best_article.content}\n\nYou can find more details at {best_article.url}\n\nDid this resolve your issue?"
            return response
        else:
            conversation.state = ConversationState.LIVE_AGENT_CHECK
            agent_info = await get_live_agent_wait_time()
            
            if agent_info.available and agent_info.wait_time_minutes < 5:
                return f"I don't have a specific solution for that issue. A live agent can help you right away (wait time: approximately {agent_info.wait_time_minutes} minutes). Would you like me to connect you with {agent_info.agent_name}?"
            else:
                return f"I don't have a specific solution for that issue. The current wait time for a live agent is approximately {agent_info.wait_time_minutes} minutes. Would you prefer to wait for an agent or should I create a service request for follow-up?"
    
    elif current_state == ConversationState.KNOWLEDGE_LOOKUP:
        if "yes" in user_input.lower() or "thank" in user_input.lower() or "help" in user_input.lower():
            conversation.state = ConversationState.RESOLUTION
            conversation.resolved = True
            return "Great! I'm glad I could help. Is there anything else you need assistance with today?"
        else:
            conversation.state = ConversationState.LIVE_AGENT_CHECK
            agent_info = await get_live_agent_wait_time()
            
            if agent_info.available and agent_info.wait_time_minutes < 5:
                return f"I'm sorry the solution didn't resolve your issue. A live agent can help you right away (wait time: approximately {agent_info.wait_time_minutes} minutes). Would you like me to connect you with {agent_info.agent_name}?"
            else:
                return f"I'm sorry the solution didn't resolve your issue. The current wait time for a live agent is approximately {agent_info.wait_time_minutes} minutes. Would you prefer to wait for an agent or should I create a service request for follow-up?"
    
    elif current_state == ConversationState.LIVE_AGENT_CHECK:
        if "agent" in user_input.lower() or "connect" in user_input.lower() or "speak" in user_input.lower() or "talk" in user_input.lower() or "wait" in user_input.lower():
            conversation.state = ConversationState.WAITING_FOR_LIVE_AGENT
            agent_info = await get_live_agent_wait_time()
            
            if agent_info.available:
                conversation.assigned_agent_id = agent_info.agent_id
                return f"I'm connecting you with {agent_info.agent_name} now. Please hold while the agent reviews your case."
            else:
                return f"All our agents are currently busy. The estimated wait time is {agent_info.wait_time_minutes} minutes. I'll place you in the queue and an agent will be with you shortly."
        else:
            conversation.state = ConversationState.SERVICE_REQUEST_CREATION
            service_request = await create_service_request(
                user_id=conversation.user_id,
                product=conversation.current_product,
                issue_summary=conversation.issue_summary or "Support needed",
                description="\n".join([m.content for m in conversation.messages if m.sender == "user"])
            )
            conversation.service_request_id = service_request.sr_id
            
            return f"I've created a service request ({service_request.sr_id}) for you. A support engineer will review and follow up as soon as possible. Is there anything else you'd like to add to the service request?"
    
    elif current_state == ConversationState.SERVICE_REQUEST_CREATION:
        if service_requests_db.get(conversation.service_request_id):
            service_request = service_requests_db[conversation.service_request_id]
            service_request.description += f"\n\nAdditional information: {user_input}"
        
        conversation.state = ConversationState.FOLLOW_UP
        return "Thank you for the additional information. Your service request has been updated. Is there anything else I can help you with today?"
    
    elif current_state == ConversationState.RESOLUTION or current_state == ConversationState.FOLLOW_UP:
        if "yes" in user_input.lower() or "another" in user_input.lower() or "new" in user_input.lower():
            conversation.state = ConversationState.PROBLEM_IDENTIFICATION
            return "I'm happy to help with something else. What issue are you experiencing?"
        else:
            return "Thank you for contacting Oracle Support. If you need assistance in the future, don't hesitate to reach out. Have a great day!"
    
    else:
        return "I'm here to help. What can I assist you with regarding Oracle Field Service?"

# API Endpoints
@app.get("/")
async def get_root():
    """Return the HTML client app"""
    with open("static/index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.post("/api/conversations")
async def create_conversation(user_id: str = "user123"):
    """Create a new conversation"""
    # Check if user exists
    if user_id not in user_db:
        raise HTTPException(status_code=404, detail="User not found")
    
    conversation_id = str(uuid.uuid4())
    conversation = Conversation(
        id=conversation_id,
        user_id=user_id
    )
    
    # Add initial greeting message
    greeting = Message(
        conversation_id=conversation_id,
        sender="agent",
        content="Hi there! I'm your virtual support engineer. What can I help you with today?"
    )
    conversation.messages.append(greeting)
    conversation_db[conversation_id] = conversation
    
    return {"conversation_id": conversation_id, "message": greeting.dict()}

@app.post("/api/conversations/{conversation_id}/messages")
async def add_message(conversation_id: str, content: str = Query(...)):
    """Add a message to an existing conversation"""
    if conversation_id not in conversation_db:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Process user message and get agent response
    agent_response = await process_agent_response(conversation_id, content)
    
    # Add agent response to conversation
    agent_message = Message(
        conversation_id=conversation_id,
        sender="agent",
        content=agent_response
    )
    conversation_db[conversation_id].messages.append(agent_message)
    
    return {"message": agent_message.dict()}

@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation details"""
    if conversation_id not in conversation_db:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return conversation_db[conversation_id].dict()

@app.post("/api/service-requests")
async def create_service_request_endpoint(
    conversation_id: str,
    description: str = Query(...)
):
    """Create a service request from a conversation"""
    if conversation_id not in conversation_db:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conversation = conversation_db[conversation_id]
    
    sr = await create_service_request(
        user_id=conversation.user_id,
        product=conversation.current_product or ProductType.FIELD_SERVICE,
        issue_summary=conversation.issue_summary or "Support needed",
        description=description
    )
    
    conversation.service_request_id = sr.sr_id
    
    return {"service_request": sr.dict()}

@app.get("/api/service-requests/{sr_id}")
async def get_service_request(sr_id: str):
    """Get service request details"""
    if sr_id not in service_requests_db:
        raise HTTPException(status_code=404, detail="Service request not found")
    
    return service_requests_db[sr_id].dict()

@app.get("/api/live-agent/wait-time")
async def get_wait_time():
    """Get the current wait time for a live agent"""
    agent_info = await get_live_agent_wait_time()
    return agent_info.dict()

@app.post("/api/supervisor/join-conversation/{conversation_id}")
async def supervisor_join(conversation_id: str, supervisor_id: str = Query(...)):
    """Allow a supervisor to join a conversation"""
    if conversation_id not in conversation_db:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if supervisor_id not in active_supervisors:
        raise HTTPException(status_code=404, detail="Supervisor not found")
    
    conversation = conversation_db[conversation_id]
    conversation.supervisor_present = True
    
    supervisor_message = Message(
        conversation_id=conversation_id,
        sender="supervisor",
        content=f"Hi, I'm {active_supervisors[supervisor_id]['name']}, a support supervisor. I'll be joining this conversation to help resolve your issue."
    )
    conversation.messages.append(supervisor_message)
    
    return {"message": supervisor_message.dict()}

# WebSocket handling for real-time chat
@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    await websocket.accept()
    
    if conversation_id not in conversation_db:
        await websocket.send_json({"error": "Conversation not found"})
        await websocket.close()
        return
    
    # Add client to connected clients
    if conversation_id not in connected_clients:
        connected_clients[conversation_id] = []
    connected_clients[conversation_id].append(websocket)
    
    try:
        # Send conversation history
        conversation = conversation_db[conversation_id]
        for message in conversation.messages:
            await websocket.send_json({"type": "message", "data": message.dict()})
        
        # Listen for messages
        while True:
            data = await websocket.receive_text()
            data = json.loads(data)
            
            if data["type"] == "message":
                user_input = data["content"]
                
                # Add user message to conversation
                user_message = Message(
                    conversation_id=conversation_id,
                    sender="user",
                    content=user_input
                )
                sentiment = await analyze_sentiment(user_input)
                user_message.sentiment = sentiment
                conversation.messages.append(user_message)
                conversation.sentiment_trend.append(sentiment)
                
                # Broadcast user message to all connected clients
                for client in connected_clients[conversation_id]:
                    await client.send_json({"type": "message", "data": user_message.dict()})
                
                # Process agent response
                agent_response = await process_agent_response(conversation_id, user_input)
                
                # Add agent response to conversation
                agent_message = Message(
                    conversation_id=conversation_id,
                    sender="agent",
                    content=agent_response
                )
                conversation.messages.append(agent_message)
                
                # Broadcast agent message to all connected clients
                for client in connected_clients[conversation_id]:
                    await client.send_json({"type": "message", "data": agent_message.dict()})
    
    except WebSocketDisconnect:
        # Remove client from connected clients
        if conversation_id in connected_clients:
            if websocket in connected_clients[conversation_id]:
                connected_clients[conversation_id].remove(websocket)
            
            if not connected_clients[conversation_id]:
                del connected_clients[conversation_id]

# Model Context Protocol Servers (simplified versions for demo purposes)

# Sentiment Analysis MCP Server
sentiment_app = FastAPI(title="Sentiment Analysis MCP")

class SentimentRequest(BaseModel):
    text: str

@sentiment_app.post("/analyze")
async def analyze_sentiment_endpoint(request: SentimentRequest):
    """Analyze sentiment of text"""
    text = request.text.lower()
    score = 0.0
    emotions = []
    
    # Simple keyword-based sentiment analysis
    positive_words = ["happy", "good", "great", "excellent", "thank", "thanks", "appreciate", "helpful"]
    negative_words = ["bad", "error", "issue", "problem", "frustrated", "angry", "not working", "broken"]
    
    for word in positive_words:
        if word in text:
            score += 0.2
            emotions.append("positive")
    
    for word in negative_words:
        if word in text:
            score -= 0.2
            emotions.append("negative")
    
    # Clamp score between -1 and 1
    score = max(-1.0, min(1.0, score))
    
    category = "positive" if score > 0.3 else "negative" if score < -0.3 else "neutral"
    
    return SentimentAnalysis(
        score=score,
        magnitude=abs(score),
        category=category,
        detected_emotions=list(set(emotions))
    )

# Knowledge Search MCP Server
knowledge_app = FastAPI(title="Knowledge Search MCP")

class SearchRequest(BaseModel):
    query: str

@knowledge_app.post("/search")
async def search_knowledge_endpoint(request: SearchRequest):
    """Search knowledge base for relevant articles"""
    query = request.query.lower()
    results = []
    
    for article in knowledge_base:
        score = 0
        
        # Simple keyword matching
        for keyword in article["keywords"]:
            if keyword in query:
                score += 0.5
        
        if article["title"].lower() in query:
            score += 1.0
        
        for term in query.split():
            if term in article["title"].lower():
                score += 0.3
            if term in article["content"].lower():
                score += 0.2
        
        if score > 0.5:  # Only include relevant articles
            results.append({
                "id": article["id"],
                "title": article["title"],
                "content": article["content"],
                "url": article["url"],
                "relevance_score": score
            })
    
    return sorted(results, key=lambda x: x["relevance_score"], reverse=True)

# Create the static folder and HTML file
import os
if not os.path.exists("static"):
    os.makedirs("static")

with open("static/index.html", "w") as f:
    f.write("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oracle Field Service AI Support</title>
    <style>
        :root {
            --primary-color: #c74634;
            --secondary-color: #3a3a3a;
            --background-color: #f5f5f5;
            --card-color: #ffffff;
            --text-color: #333333;
            --border-color: #e0e0e0;
            --light-gray: #f9f9f9;
            --mid-gray: #d8d8d8;
            --success-color: #4caf50;
            --warning-color: #ff9800;
            --danger-color: #f44336;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        body {
            background-color: var(--background-color);
            color: var(--text-color);
            line-height: 1.6;
        }

        header {
            background-color: #f80000;
            color: white;
            padding: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }

        .logo {
            font-size: 1.5rem;
            font-weight: bold;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 1rem;
            display: grid;
            grid-template-columns: 1fr 300px;
            gap: 1rem;
            height: calc(100vh - 60px);
        }

        .chat-container {
            background-color: var(--card-color);
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .chat-header {
            background-color: var(--light-gray);
            padding: 1rem;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .chat-title {
            font-size: 1.2rem;
            font-weight: 600;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.9rem;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--success-color);
        }

        .chat-messages {
            flex: 1;
            padding: 1rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .message {
            max-width: 80%;
            padding: 0.75rem 1rem;
            border-radius: 1rem;
            position: relative;
            word-wrap: break-word;
        }

        .user-message {
            align-self: flex-end;
            background-color: #e1f5fe;
            border-bottom-right-radius: 0.25rem;
        }
        .agent-message {
            align-self: flex-start;
            background-color: var(--light-gray);
            border-bottom-left-radius: 0.25rem;
        }

        .supervisor-message {
            align-self: flex-start;
            background-color: #fff8e1;
            border-bottom-left-radius: 0.25rem;
        }

        .message-sender {
            font-size: 0.8rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
            color: var(--secondary-color);
        }

        .message-time {
            font-size: 0.7rem;
            color: #888;
            position: absolute;
            bottom: 0.25rem;
            right: 0.75rem;
        }

        .chat-input {
            padding: 1rem;
            border-top: 1px solid var(--border-color);
            display: flex;
            gap: 0.5rem;
        }

        .chat-input input {
            flex: 1;
            padding: 0.75rem 1rem;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            outline: none;
            font-size: 1rem;
        }

        .chat-input input:focus {
            border-color: var(--primary-color);
        }

        .chat-input button {
            padding: 0.75rem 1.5rem;
            background-color: var(--primary-color);
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
            transition: background-color 0.2s;
        }

        .chat-input button:hover {
            background-color: #b13224;
        }

        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .info-card {
            background-color: var(--card-color);
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            padding: 1rem;
        }

        .info-card h3 {
            font-size: 1rem;
            margin-bottom: 0.5rem;
            color: var(--secondary-color);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.5rem;
        }

        .info-card-content {
            font-size: 0.9rem;
        }

        .sentiment-meter {
            margin-top: 0.5rem;
            height: 8px;
            background-color: var(--mid-gray);
            border-radius: 4px;
            overflow: hidden;
        }

        .sentiment-value {
            height: 100%;
            background: linear-gradient(to right, #f44336, #ffeb3b, #4caf50);
            transition: width 0.3s ease;
        }

        .agent-controls {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            margin-top: 0.5rem;
        }

        .control-button {
            padding: 0.5rem;
            background-color: var(--light-gray);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
            text-align: center;
            transition: background-color 0.2s;
        }

        .control-button:hover {
            background-color: var(--mid-gray);
        }

        .typing-indicator {
            align-self: flex-start;
            background-color: var(--light-gray);
            border-radius: 1rem;
            padding: 0.5rem 1rem;
            font-size: 0.9rem;
            display: none;
        }

        .typing-indicator span {
            display: inline-block;
            width: 6px;
            height: 6px;
            background-color: #888;
            border-radius: 50%;
            animation: typing 1s infinite;
            margin: 0 2px;
        }

        .typing-indicator span:nth-child(2) {
            animation-delay: 0.2s;
        }

        .typing-indicator span:nth-child(3) {
            animation-delay: 0.4s;
        }

        @keyframes typing {
            0%, 100% {
                transform: translateY(0);
            }
            50% {
                transform: translateY(-5px);
            }
        }

        .knowledge-article {
            background-color: #e8f5e9;
            border: 1px solid #c8e6c9;
            border-radius: 4px;
            padding: 0.75rem;
            margin-top: 0.5rem;
            font-size: 0.9rem;
        }

        .knowledge-article h4 {
            margin-bottom: 0.5rem;
            font-size: 1rem;
        }

        .knowledge-article p {
            margin-bottom: 0.5rem;
        }

        .knowledge-article a {
            color: var(--primary-color);
            text-decoration: none;
            font-weight: 600;
        }

        .knowledge-article a:hover {
            text-decoration: underline;
        }

        .supervisor-panel {
            display: none;
            position: fixed;
            top: 60px;
            right: 0;
            width: 300px;
            height: calc(100vh - 60px);
            background-color: var(--card-color);
            box-shadow: -2px 0 5px rgba(0, 0, 0, 0.1);
            z-index: 100;
            overflow-y: auto;
            padding: 1rem;
        }

        .supervisor-panel h2 {
            font-size: 1.2rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border-color);
        }

        .conversation-list {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .conversation-item {
            padding: 0.75rem;
            border-radius: 4px;
            background-color: var(--light-gray);
            cursor: pointer;
            transition: background-color 0.2s;
        }

        .conversation-item:hover {
            background-color: var(--mid-gray);
        }

        .conversation-item.negative {
            border-left: 3px solid var(--danger-color);
        }

        .loading {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100%;
        }

        .spinner {
            border: 4px solid rgba(0, 0, 0, 0.1);
            border-left-color: var(--primary-color);
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .sr-created {
            background-color: #e8f5e9;
            border: 1px solid #c8e6c9;
            padding: 0.75rem;
            border-radius: 4px;
            margin-top: 0.5rem;
            font-size: 0.9rem;
        }

        .sr-id {
            font-weight: 600;
            color: var(--primary-color);
        }

        /* Responsive design */
        @media (max-width: 768px) {
            .container {
                grid-template-columns: 1fr;
            }
            
            .sidebar {
                display: none;
            }
        }
    </style>
</head>
<body>
    <header>
        <div class="logo">Oracle Field Service Support</div>
        <div class="user-info">John Smith</div>
    </header>
    
    <div class="container">
        <div class="chat-container">
            <div class="chat-header">
                <div class="chat-title">AI Support Engineer</div>
                <div class="status-indicator">
                    <div class="status-dot"></div>
                    <span>Online</span>
                </div>
            </div>
            
            <div class="chat-messages" id="chatMessages">
                <div class="message agent-message">
                    <div class="message-sender">AI Support Engineer</div>
                    <div>Hi there! I'm your virtual support engineer. What can I help you with today?</div>
                    <div class="message-time">Just now</div>
                </div>
                
                <div class="typing-indicator" id="typingIndicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
            
            <div class="chat-input">
                <input type="text" id="messageInput" placeholder="Type your message here..." />
                <button id="sendButton">Send</button>
            </div>
        </div>
        
        <div class="sidebar">
            <div class="info-card">
                <h3>Active Subscription</h3>
                <div class="info-card-content">
                    <p>Oracle Field Service Cloud</p>
                    <p>Oracle Intelligent Advisor</p>
                </div>
            </div>
            
            <div class="info-card">
                <h3>Current Issue</h3>
                <div class="info-card-content" id="currentIssue">
                    <p>No issue reported yet</p>
                </div>
            </div>
            
            <div class="info-card">
                <h3>Sentiment Analysis</h3>
                <div class="info-card-content">
                    <p>Current mood: <span id="sentimentValue">Neutral</span></p>
                    <div class="sentiment-meter">
                        <div class="sentiment-value" id="sentimentMeter" style="width: 50%;"></div>
                    </div>
                </div>
            </div>
            
            <div class="info-card">
                <h3>Agent Tools</h3>
                <div class="agent-controls">
                    <div class="control-button" id="createSRButton">Create Service Request</div>
                    <div class="control-button" id="liveSupportButton">Request Live Support</div>
                    <div class="control-button" id="supervisorButton">Call Supervisor</div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="supervisor-panel" id="supervisorPanel">
        <h2>Supervisor Dashboard</h2>
        <div class="conversation-list" id="conversationList">
            <!-- Conversation items will be added here -->
        </div>
    </div>

    <script>
        // Global variables
        let conversationId = null;
        let socket = null;
        let currentState = "greeting";
        let user = {
            id: "user123",
            name: "John Smith",
            email: "john.smith@example.com"
        };
        let sentimentHistory = [];
        let isSupervisor = false;
        let supervisorMode = false;

        // DOM Elements
        const chatMessages = document.getElementById('chatMessages');
        const messageInput = document.getElementById('messageInput');
        const sendButton = document.getElementById('sendButton');
        const typingIndicator = document.getElementById('typingIndicator');
        const currentIssue = document.getElementById('currentIssue');
        const sentimentValue = document.getElementById('sentimentValue');
        const sentimentMeter = document.getElementById('sentimentMeter');
        const createSRButton = document.getElementById('createSRButton');
        const liveSupportButton = document.getElementById('liveSupportButton');
        const supervisorButton = document.getElementById('supervisorButton');
        const supervisorPanel = document.getElementById('supervisorPanel');
        const conversationList = document.getElementById('conversationList');

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            initializeConversation();
            
            // Event listeners
            sendButton.addEventListener('click', sendMessage);
            messageInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
            
            createSRButton.addEventListener('click', createServiceRequest);
            liveSupportButton.addEventListener('click', requestLiveSupport);
            supervisorButton.addEventListener('click', toggleSupervisorMode);
        });

        // Initialize a new conversation
        async function initializeConversation() {
            try {
                const response = await fetch('/api/conversations', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ user_id: user.id })
                });
                
                const data = await response.json();
                conversationId = data.conversation_id;
                
                // Initialize WebSocket connection
                initializeWebSocket();
            } catch (error) {
                console.error('Error initializing conversation:', error);
                addSystemMessage('Error connecting to support. Please try again later.');
            }
        }

        // Initialize WebSocket connection
        function initializeWebSocket() {
            if (socket) {
                socket.close();
            }
            
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/${conversationId}`;
            
            socket = new WebSocket(wsUrl);
            
            socket.onopen = () => {
                console.log('WebSocket connection established');
            };
            
            socket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                if (data.type === 'message') {
                    handleIncomingMessage(data.data);
                } else if (data.type === 'error') {
                    addSystemMessage(data.message || 'An error occurred');
                }
            };
            
            socket.onclose = () => {
                console.log('WebSocket connection closed');
                // Attempt to reconnect after a delay
                setTimeout(initializeWebSocket, 3000);
            };
            
            socket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        }

        // Send a message
        function sendMessage() {
            const content = messageInput.value.trim();
            
            if (!content) return;
            
            // Add message to UI
            addMessage('user', content);
            
            // Clear input
            messageInput.value = '';
            
            // Show typing indicator
            typingIndicator.style.display = 'block';
            
            // Send message via WebSocket
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({
                    type: 'message',
                    content: content
                }));
            } else {
                // Fallback to REST API if WebSocket is not available
                sendMessageViaREST(content);
            }
        }

        // Send message via REST API (fallback)
        async function sendMessageViaREST(content) {
            try {
                const response = await fetch(`/api/conversations/${conversationId}/messages?content=${encodeURIComponent(content)}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const data = await response.json();
                
                // Hide typing indicator
                typingIndicator.style.display = 'none';
                
                // Add agent response to UI
                if (data.message) {
                    addMessage(data.message.sender, data.message.content);
                }
            } catch (error) {
                console.error('Error sending message:', error);
                typingIndicator.style.display = 'none';
                addSystemMessage('Error sending message. Please try again.');
            }
        }

        // Handle incoming messages from WebSocket
        function handleIncomingMessage(message) {
            // Hide typing indicator
            typingIndicator.style.display = 'none';
            
            // Add message to UI if it's not from the current user
            if (message.sender !== 'user') {
                addMessage(message.sender, message.content);
            }
            
            // Update sentiment if available
            if (message.sentiment) {
                updateSentiment(message.sentiment);
            }
            
            // Check for knowledge articles in agent message
            if (message.sender === 'agent' && message.content.includes('I found some information')) {
                const title = message.content.match(/'([^']+)'/);
                if (title) {
                    updateCurrentIssue(title[1]);
                }
            }
            
            // Check for service request creation
            if (message.sender === 'agent' && message.content.includes('service request (SR-')) {
                const srId = message.content.match(/\(([^)]+)\)/)[1];
                addServiceRequestNotification(srId);
            }
        }

        // Add a message to the UI
        function addMessage(sender, content) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender}-message`;
            
            const senderDiv = document.createElement('div');
            senderDiv.className = 'message-sender';
            senderDiv.textContent = sender === 'user' ? 'You' : 
                                   sender === 'agent' ? 'AI Support Engineer' : 
                                   'Support Supervisor';
            
            const contentDiv = document.createElement('div');
            contentDiv.textContent = content;
            
            const timeDiv = document.createElement('div');
            timeDiv.className = 'message-time';
            timeDiv.textContent = formatTime(new Date());
            
            messageDiv.appendChild(senderDiv);
            messageDiv.appendChild(contentDiv);
            messageDiv.appendChild(timeDiv);
            
            // Insert before typing indicator
            chatMessages.insertBefore(messageDiv, typingIndicator);
            
            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
            
            // Update current issue if this is a user message
            if (sender === 'user') {
                updateCurrentIssue(content);
            }
        }

        // Add a system message
        function addSystemMessage(content) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message agent-message';
            messageDiv.style.fontStyle = 'italic';
            messageDiv.style.color = '#777';
            
            const contentDiv = document.createElement('div');
            contentDiv.textContent = content;
            
            messageDiv.appendChild(contentDiv);
            
            // Insert before typing indicator
            chatMessages.insertBefore(messageDiv, typingIndicator);
            
            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // Update sentiment display
        function updateSentiment(sentiment) {
            sentimentHistory.push(sentiment);
            
            // Update sentiment display
            sentimentValue.textContent = sentiment.category.charAt(0).toUpperCase() + sentiment.category.slice(1);
            
            // Update sentiment meter (convert -1 to 1 scale to 0 to 100%)
            const meterValue = ((sentiment.score + 1) / 2) * 100;
            sentimentMeter.style.width = `${meterValue}%`;
            
            // Alert supervisor if sentiment is negative
            if (sentiment.score < -0.7 && !supervisorMode) {
                addSystemMessage('The customer appears to be experiencing frustration. A supervisor has been notified.');
            }
        }

        // Update current issue
        function updateCurrentIssue(content) {
            currentIssue.innerHTML = `<p>${content}</p>`;
        }

        // Create a service request
        async function createServiceRequest() {
            try {
                // Collect conversation history
                const messages = Array.from(chatMessages.querySelectorAll('.user-message'))
                    .map(msg => msg.querySelector('div:not(.message-sender):not(.message-time)').textContent);
                
                const response = await fetch('/api/service-requests', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        conversation_id: conversationId,
                        description: messages || 'No description provided'
                    })
                });
                
                const data = await response.json();
                
                if (data.service_request) {
                    addServiceRequestNotification(data.service_request.sr_id);
                    addSystemMessage(`Service request ${data.service_request.sr_id} has been created. A support engineer will follow up soon.`);
                }
            } catch (error) {
                console.error('Error creating service request:', error);
                addSystemMessage('Error creating service request. Please try again.');
            }
        }

        // Add service request notification
        function addServiceRequestNotification(srId) {
            const srDiv = document.createElement('div');
            srDiv.className = 'sr-created';
            srDiv.innerHTML = `Service Request <span class="sr-id">${srId}</span> has been created. A support engineer will follow up with you shortly.`;
            
            chatMessages.insertBefore(srDiv, typingIndicator);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // Request live support
        async function requestLiveSupport() {
            try {
                const response = await fetch('/api/live-agent/wait-time');
                const data = await response.json();
                
                if (data.available) {
                    addSystemMessage(`Connecting you to a live agent. Estimated wait time: ${data.wait_time_minutes} minutes.`);
                    
                    // In a real app, this would initiate the live transfer
                    setTimeout(() => {
                        addMessage('agent', `Hi there! I'm ${data.agent_name}, a live support agent. I've reviewed your conversation and I'm ready to help you. What specific issue are you having with Oracle Field Service?`);
                    }, 3000);
                } else {
                    addSystemMessage(`All agents are currently busy. Estimated wait time: ${data.wait_time_minutes} minutes. Would you like to wait or create a service request instead?`);
                }
            } catch (error) {
                console.error('Error requesting live support:', error);
                addSystemMessage('Error connecting to live support. Please try again later.');
            }
        }

        // Toggle supervisor mode
        function toggleSupervisorMode() {
            supervisorMode = !supervisorMode;
            supervisorPanel.style.display = supervisorMode ? 'block' : 'none';
            
            if (supervisorMode) {
                loadSupervisorData();
            }
        }

        // Load supervisor data
        function loadSupervisorData() {
            // In a real app, this would load active conversations
            conversationList.innerHTML = '';
            
            const conversations = [
                { id: conversationId, user: 'John Smith', issue: currentIssue.textContent, sentiment: -0.8 },
                { id: 'conv-002', user: 'Jane Doe', issue: 'Account access issue', sentiment: -0.5 },
                { id: 'conv-003', user: 'Alex Johnson', issue: 'Schedule not updating', sentiment: 0.2 }
            ];
            
            conversations.forEach(conv => {
                const item = document.createElement('div');
                item.className = `conversation-item ${conv.sentiment < -0.5 ? 'negative' : ''}`;
                item.innerHTML = `
                    <div><strong>${conv.user}</strong></div>
                    <div>${conv.issue}</div>
                    <div>Sentiment: ${conv.sentiment < -0.5 ? 'Negative' : conv.sentiment > 0.5 ? 'Positive' : 'Neutral'}</div>
                `;
                
                item.addEventListener('click', () => {
                    joinConversation(conv.id);
                });
                
                conversationList.appendChild(item);
            });
        }

        // Join a conversation as supervisor
        async function joinConversation(convId) {
            try {
                const response = await fetch(`/api/supervisor/join-conversation/${convId}?supervisor_id=super001`, {
                    method: 'POST'
                });
                
                const data = await response.json();
                
                if (data.message) {
                    addSystemMessage('Supervisor has joined the conversation.');
                    setTimeout(() => {
                        addMessage('supervisor', data.message.content);
                    }, 1000);
                }
            } catch (error) {
                console.error('Error joining conversation:', error);
            }
        }

        // Helper function to format time
        function formatTime(date) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
    </script>
</body>
</html>
""")

# Start servers
def start_server(app, host, port, app_name):
    import uvicorn
    config = uvicorn.Config(app=app, host=host, port=port)
    server = uvicorn.Server(config)
    print(f"Starting {app_name} server on {host}:{port}")
    return server

async def start_all():
    # Start all servers
    sentiment_server = start_server(sentiment_app, "0.0.0.0", 8001, "Sentiment Analysis MCP")
    knowledge_server = start_server(knowledge_app, "0.0.0.0", 8002, "Knowledge Search MCP")
    main_server = start_server(app, "0.0.0.0", 8000, "Main API")
    
    # Run all servers
    await asyncio.gather(
        sentiment_server.serve(),
        knowledge_server.serve(),
        main_server.serve()
    )

if __name__ == "__main__":
    # Start all servers
    import asyncio
    asyncio.run(start_all())
            