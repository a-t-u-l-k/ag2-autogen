from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import json
import random
import asyncio
import time
import uuid
from enum import Enum

app = FastAPI(title="Agentic Support Engineer API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enum for ticket status
class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"

# Data models
class Message(BaseModel):
    message: str
    sender: str

class ConversationRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ServiceRequest(BaseModel):
    user_id: str
    issue: str
    details: str
    status: TicketStatus = TicketStatus.OPEN
    created_at: float = time.time()
    sr_id: str = ""

# In-memory database
active_conversations = {}
knowledge_base = {
    "changing technician hours": "To change a technician's working hours:\n1. Navigate to Resources > Technicians\n2. Select the technician\n3. Click 'Edit Schedule'\n4. Modify the working hours\n5. Click 'Save'",
    "view schedule": "To view the schedule:\n1. Go to Dispatch Console\n2. Select date range\n3. Filter by resource group if needed\n4. The schedule view will display all assignments",
    "reset password": "To reset your password:\n1. Click on your profile icon\n2. Select 'Account Settings'\n3. Choose 'Change Password'\n4. Follow the prompts to create a new password",
    "add new technician": "To add a new technician:\n1. Go to Resources > Technicians\n2. Click 'Add New'\n3. Fill in the required information\n4. Set skills and working hours\n5. Click 'Save'",
    "create service activity": "To create a service activity:\n1. Go to Activities\n2. Click 'Create New'\n3. Fill in customer information\n4. Set activity type and required skills\n5. Set time window\n6. Click 'Save'"
}
service_requests = {}
live_agent_status = {"available": True, "wait_time": 10}  # Default values

# Agent tools
async def search_km(issue_summary: str) -> Dict:
    """Search knowledge base for relevant information"""
    await asyncio.sleep(1)  # Simulate search delay
    
    # Simplistic keyword matching
    results = []
    for key, value in knowledge_base.items():
        if any(word in issue_summary.lower() for word in key.split()):
            results.append({"topic": key, "content": value})
    
    return {
        "success": len(results) > 0,
        "results": results
    }

async def get_live_agent_wait_time() -> Dict:
    """Get estimated wait time for live agent"""
    await asyncio.sleep(0.5)  # Simulate API call
    
    # In real system, this would check actual queue status
    wait_time = live_agent_status["wait_time"]
    available = live_agent_status["available"]
    
    return {
        "available": available,
        "wait_time": wait_time
    }

async def initiate_live_transfer(context: Dict) -> Dict:
    """Transfer to live agent"""
    await asyncio.sleep(1)  # Simulate transfer delay
    
    # In real system, this would place customer in queue
    transfer_id = str(uuid.uuid4())
    
    return {
        "success": True,
        "transfer_id": transfer_id,
        "estimated_wait": live_agent_status["wait_time"]
    }

async def create_service_request(context: Dict) -> Dict:
    """Create a service request ticket"""
    await asyncio.sleep(1)  # Simulate SR creation
    
    sr_id = f"SR-{int(time.time())}"
    
    sr = ServiceRequest(
        user_id=context.get("user_id", "anonymous"),
        issue=context.get("issue", "Unspecified issue"),
        details=context.get("details", "No details provided"),
        sr_id=sr_id
    )
    
    service_requests[sr_id] = sr.dict()
    
    return {
        "success": True,
        "sr_id": sr_id
    }

async def analyze_sentiment(message: str) -> Dict:
    """Analyze message sentiment"""
    await asyncio.sleep(0.5)  # Simulate analysis
    
    # Very simplistic sentiment analysis
    negative_words = ["error", "problem", "issue", "broken", "doesn't work", "frustrated", "angry"]
    urgent_words = ["urgent", "immediately", "asap", "emergency", "critical"]
    
    sentiment_score = 0.5  # Neutral default
    is_urgent = False
    
    # Adjust sentiment based on negative words
    for word in negative_words:
        if word in message.lower():
            sentiment_score -= 0.1
    
    # Check for urgency
    for word in urgent_words:
        if word in message.lower():
            is_urgent = True
    
    sentiment_score = max(0.0, min(1.0, sentiment_score))  # Keep in range 0-1
    
    return {
        "score": sentiment_score,
        "is_urgent": is_urgent,
        "needs_attention": sentiment_score < 0.3 or is_urgent
    }

# Stateful conversation handler
class ConversationHandler:
    def __init__(self):
        self.conversation_id = str(uuid.uuid4())
        self.messages = []
        self.context = {
            "product": None,
            "issue": None,
            "details": {},
            "user_id": f"user-{int(time.time())}",
            "sentiment_history": [],
            "supervisor_notified": False
        }
        self.state = "greeting"
    
    async def process_message(self, message: str) -> str:
        """Process incoming message and generate response"""
        self.messages.append({"sender": "user", "message": message})
        
        # Analyze sentiment
        sentiment = await analyze_sentiment(message)
        self.context["sentiment_history"].append(sentiment)
        
        # Check if supervisor should be notified
        if sentiment["needs_attention"] and not self.context["supervisor_notified"]:
            self.context["supervisor_notified"] = True
            # In a real system, this would trigger a notification
        
        response = await self._generate_response(message)
        self.messages.append({"sender": "agent", "message": response})
        
        return response
    
    async def _generate_response(self, message: str) -> str:
        """Generate response based on current state and message"""
        if self.state == "greeting":
            # Move to product clarification if Oracle Field Service is mentioned
            if "field service" in message.lower():
                self.context["product"] = "Oracle Field Service"
                self.state = "problem_restatement"
                return "Thanks for reaching out about Oracle Field Service. What specific issue can I help you with today?"
            else:
                self.state = "product_clarification"
                return "Thanks for reaching out! I'm your virtual support engineer. To help you better, could you confirm which Oracle product you're inquiring about? Is it Oracle Field Service?"
        
        elif self.state == "product_clarification":
            if "yes" in message.lower() or "field service" in message.lower():
                self.context["product"] = "Oracle Field Service"
                self.state = "problem_restatement"
                return "Great! What specific Oracle Field Service issue can I help you with today?"
            else:
                self.context["product"] = message  # Just use whatever they mentioned
                self.state = "problem_restatement"
                return f"Thanks for clarifying. What specific issue with {message} can I help you with today?"
        
        elif self.state == "problem_restatement":
            self.context["issue"] = message
            issue_summary = f"Got it—you need help with {message}. Let me check our resources for that."
            self.state = "knowledge_lookup"
            
            # Start knowledge lookup
            km_results = await search_km(message)
            
            if km_results["success"] and km_results["results"]:
                # Found relevant info
                result = km_results["results"][0]  # Take first match
                response = f"Here's what I found that should help with {result['topic']}:\n\n{result['content']}\n\nDid that answer your question?"
                self.state = "solution_verification"
                return response
            else:
                # No relevant info found
                self.state = "live_agent_check"
                agent_status = await get_live_agent_wait_time()
                
                if agent_status["available"]:
                    return f"I don't have a specific guide for that issue. A live support agent can be available in about {agent_status['wait_time']} minutes. Would you like to wait and speak to someone, or should I create a Service Request so someone can follow up later?"
                else:
                    # Create SR directly if no agents available
                    sr_result = await create_service_request(self.context)
                    self.state = "farewell"
                    return f"No agents are currently available, so I've created a Service Request for you. Your ticket number is {sr_result['sr_id']}. A support engineer will reach out as soon as possible. Is there anything else I can help with?"
        
        elif self.state == "knowledge_lookup":
            # This is handled in problem_restatement state
            self.state = "solution_verification"
            return "I'm still searching our knowledge base..."
        
        elif self.state == "solution_verification":
            if "yes" in message.lower() or "thank" in message.lower() or "that work" in message.lower() or "helpful" in message.lower():
                self.state = "farewell"
                return "Great! I'm glad that helped. Is there anything else you need assistance with today?"
            else:
                self.state = "live_agent_check"
                agent_status = await get_live_agent_wait_time()
                return f"I'm sorry the information wasn't helpful. A live support agent can be available in about {agent_status['wait_time']} minutes. Would you like to wait and speak to someone, or should I create a Service Request instead?"
        
        elif self.state == "live_agent_check":
            if "wait" in message.lower() or "speak" in message.lower() or "talk" in message.lower() or "agent" in message.lower():
                # User wants to speak to live agent
                transfer_result = await initiate_live_transfer(self.context)
                self.state = "live_transfer"
                return f"Perfect. I'm transferring you now. A support agent will be with you in approximately {transfer_result['estimated_wait']} minutes. Please stay in this chat."
            elif "ticket" in message.lower() or "request" in message.lower() or "sr" in message.lower() or "case" in message.lower():
                # User wants SR created
                self.context["details"] = message  # Add any details they provided
                sr_result = await create_service_request(self.context)
                self.state = "farewell"
                return f"I've created a Service Request for you. Your ticket number is {sr_result['sr_id']}. A support engineer will reach out as soon as possible. Is there anything else I can help with in the meantime?"
            else:
                # Unclear response, ask again
                return "Would you prefer to wait for a live agent now, or should I create a Service Request ticket for follow-up?"
        
        elif self.state == "live_transfer":
            # Simulate supervisor barge-in based on sentiment or direct request
            if "supervisor" in message.lower() or "manager" in message.lower():
                self.state = "supervisor_barge_in"
                return "I'm bringing in a supervisor to assist you. Please hold for a moment."
            else:
                return "A support agent will be with you shortly. Your position in the queue is being maintained."
        
        elif self.state == "supervisor_barge_in":
            self.state = "farewell"
            return "Hi, this is the supervisor. I understand you're having some issues. I'll personally make sure this gets resolved for you. Could you please provide me with a contact number where our senior support team can reach you?"
        
        elif self.state == "farewell":
            if "yes" in message.lower() or "another" in message.lower() or "also" in message.lower():
                self.state = "problem_restatement"
                return "I'd be happy to help with something else. What other issue can I assist you with?"
            elif "no" in message.lower() or "thank" in message.lower() or "bye" in message.lower():
                return "Thank you for contacting Oracle Support. Have a great day!"
            else:
                self.state = "problem_restatement"
                return "Is there something else I can help you with today?"
        
        else:
            # Default response
            return "I'm here to help. Could you please clarify what you need assistance with regarding Oracle Field Service?"

# API Endpoints
@app.post("/conversation")
async def handle_conversation(request: ConversationRequest):
    if request.conversation_id and request.conversation_id in active_conversations:
        # Existing conversation
        conversation = active_conversations[request.conversation_id]
    else:
        # New conversation
        conversation = ConversationHandler()
        active_conversations[conversation.conversation_id] = conversation
    
    response = await conversation.process_message(request.message)
    
    return {
        "conversation_id": conversation.conversation_id,
        "response": response,
        "state": conversation.state
    }

@app.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str):
    if conversation_id not in active_conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conversation = active_conversations[conversation_id]
    
    return {
        "conversation_id": conversation_id,
        "messages": conversation.messages,
        "state": conversation.state
    }

@app.get("/service-requests")
async def get_service_requests():
    return {"service_requests": service_requests}

@app.get("/live-agent-status")
async def get_agent_status():
    return live_agent_status

@app.put("/live-agent-status")
async def update_agent_status(status: Dict):
    global live_agent_status
    if "available" in status:
        live_agent_status["available"] = status["available"]
    if "wait_time" in status:
        live_agent_status["wait_time"] = status["wait_time"]
    return live_agent_status

@app.get("/knowledge")
async def get_knowledge_items():
    return {"knowledge_items": [{"topic": k, "summary": v.split("\n")[0]} for k, v in knowledge_base.items()]}

# WebSocket for real-time supervisor monitoring
active_websockets = []

@app.websocket("/ws/supervisor")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            # Send periodic updates about conversations
            conversation_summaries = []
            for conv_id, conv in active_conversations.items():
                # Only include active conversations from the last hour
                latest_messages = conv.messages[-3:] if conv.messages else []
                sentiment_alert = any(s["needs_attention"] for s in conv.context["sentiment_history"][-3:]) if conv.context["sentiment_history"] else False
                
                conversation_summaries.append({
                    "id": conv_id,
                    "state": conv.state,
                    "latest_messages": latest_messages,
                    "sentiment_alert": sentiment_alert,
                    "product": conv.context["product"],
                    "issue": conv.context["issue"]
                })
            
            await websocket.send_json({"conversations": conversation_summaries})
            await asyncio.sleep(5)  # Update every 5 seconds
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        active_websockets.remove(websocket)

# Main entrypoint
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
