# server.py
import os
import json
import autogen
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
import logging
import uvicorn
from typing import Optional, Dict, List, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Download NLTK sentiment analysis resources
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')

# Initialize FastAPI app
app = FastAPI(title="AutoGen Chat Service")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API configuration
API_URL = "https://example.com/completions"
API_USERNAME = "<set-api-username>"
API_PASSWORD = ""

# Initialize sentiment analyzer
sia = SentimentIntensityAnalyzer()

# Function to analyze sentiment
def analyze_sentiment(text):
    sentiment_score = sia.polarity_scores(text)
    return sentiment_score['compound']  # Returns a score between -1 (negative) and 1 (positive)

# Class for message passing between agents
class Message:
    def __init__(self, sender, content, metadata=None):
        self.sender = sender
        self.content = content
        self.metadata = metadata or {}
    
    def __str__(self):
        return f"{self.sender}: {self.content}"

# Class for conversation context
class ConversationContext:
    def __init__(self):
        self.messages = []
        self.user_sentiment_history = []
        self.agent_sentiment_history = []
        self.metadata = {}
    
    def add_message(self, message):
        self.messages.append(message)
    
    def get_recent_messages(self, n=5):
        return self.messages[-n:] if self.messages else []
    
    def get_formatted_history(self, n=5):
        recent = self.get_recent_messages(n)
        return "\n".join([str(msg) for msg in recent])
    
    def update_sentiment(self, role, score):
        if role == "user":
            self.user_sentiment_history.append(score)
        elif role == "agent":
            self.agent_sentiment_history.append(score)
    
    def get_current_user_sentiment(self):
        return self.user_sentiment_history[-1] if self.user_sentiment_history else 0
    
    def get_current_agent_sentiment(self):
        return self.agent_sentiment_history[-1] if self.agent_sentiment_history else 0

# Function to call the external API
def call_external_api(prompt):
    logger.info(f"Calling external API with prompt: {prompt}")
    try:
        response = requests.post(
            API_URL,
            json={"prompt": prompt},
            auth=(API_USERNAME, API_PASSWORD),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"API response received: {data}")
        return data["choices"][0]["text"]
    except Exception as e:
        logger.error(f"Error calling external API: {str(e)}")
        return f"I apologize, but I'm experiencing technical difficulties accessing our service information. Please try again later. (Error: {str(e)})"

# AutoGen agent implementations
class CustomerServiceAgent(autogen.AssistantAgent):
    def __init__(self, name="CustomerServiceAgent"):
        super().__init__(
            name=name,
            system_message="You are a customer service agent helping users with their subscribed services. "
                          "Your responses will be sent to an external API for processing.",
            llm_config=False  # No LLM config as we'll use the external API
        )
    
    def generate_response(self, context):
        logger.info(f"CustomerServiceAgent generating response with context: {context.get_formatted_history()}")
        
        prompt = f"""
        Conversation history:
        {context.get_formatted_history()}
        
        You are a customer service agent helping with subscribed services. 
        Respond to the user's latest message in a helpful and professional manner.
        """
        
        response_text = call_external_api(prompt)
        return Message(
            sender=self.name,
            content=response_text,
            metadata={"role": "agent"}
        )

class EndUserAgent(autogen.UserProxyAgent):
    def __init__(self, name="EndUserAgent"):
        super().__init__(
            name=name,
            human_input_mode="NEVER",  # This will be controlled programmatically
            system_message="You are simulating an end user asking about subscribed services."
        )
    
    def create_message(self, content):
        return Message(
            sender=self.name,
            content=content,
            metadata={"role": "user"}
        )

class SupervisorAgent(autogen.AssistantAgent):
    def __init__(self, name="SupervisorAgent"):
        super().__init__(
            name=name,
            system_message="You are a supervisor who monitors conversations between users and customer service agents. "
                          "You intervene when the user sentiment becomes negative to help resolve issues. "
                          "Be professional, empathetic, and solution-oriented.",
            llm_config=False  # No LLM config as we'll use custom logic
        )
    
    def should_intervene(self, context):
        user_sentiment = context.get_current_user_sentiment()
        return user_sentiment < -0.3  # Threshold for negative sentiment
    
    def generate_response(self, context):
        logger.info(f"SupervisorAgent analyzing situation with context: {context.get_formatted_history()}")
        
        # Get the latest user and agent messages
        recent_messages = context.get_recent_messages()
        user_message = next((msg for msg in reversed(recent_messages) if msg.sender == "EndUserAgent"), None)
        agent_message = next((msg for msg in reversed(recent_messages) if msg.sender == "CustomerServiceAgent"), None)
        
        if not user_message or not agent_message:
            return None
        
        prompt = f"""
        As a customer service supervisor, I need to intervene in the following conversation where the customer seems dissatisfied:
        
        Customer: {user_message.content}
        Agent: {agent_message.content}
        
        Previous conversation context:
        {context.get_formatted_history(3)}
        
        Generate an empathetic supervisor response that addresses the customer's concerns, acknowledges any issues, and offers additional assistance or solutions.
        Your response should be professional and solution-oriented.
        """
        
        response_text = call_external_api(prompt)
        return Message(
            sender=self.name,
            content=response_text,
            metadata={"role": "supervisor"}
        )

# Create agent instances
customer_service_agent = CustomerServiceAgent()
end_user_agent = EndUserAgent()
supervisor_agent = SupervisorAgent()

# In-memory storage for conversation contexts
conversation_contexts = {}

# Data models for API
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"

class ChatResponse(BaseModel):
    agent_response: str
    user_sentiment: float
    agent_sentiment: float
    supervisor_intervention: bool
    supervisor_response: Optional[str] = None

# Route for the chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    user_message = request.message
    session_id = request.session_id
    
    # Initialize context if it doesn't exist
    if session_id not in conversation_contexts:
        conversation_contexts[session_id] = ConversationContext()
    
    context = conversation_contexts[session_id]
    
    # Create and add user message to context
    user_msg = end_user_agent.create_message(user_message)
    context.add_message(user_msg)
    
    # Analyze user sentiment
    user_sentiment = analyze_sentiment(user_message)
    context.update_sentiment("user", user_sentiment)
    logger.info(f"User sentiment: {user_sentiment}")
    
    # Get response from customer service agent
    agent_msg = customer_service_agent.generate_response(context)
    context.add_message(agent_msg)
    
    # Analyze agent sentiment
    agent_sentiment = analyze_sentiment(agent_msg.content)
    context.update_sentiment("agent", agent_sentiment)
    logger.info(f"Agent sentiment: {agent_sentiment}")
    
    # Check if supervisor should intervene
    supervisor_response = None
    if supervisor_agent.should_intervene(context):
        logger.info("Negative user sentiment detected. Supervisor intervention initiated.")
        supervisor_msg = supervisor_agent.generate_response(context)
        if supervisor_msg:
            context.add_message(supervisor_msg)
            supervisor_response = supervisor_msg.content
    
    # Prepare response
    response = ChatResponse(
        agent_response=agent_msg.content,
        user_sentiment=user_sentiment,
        agent_sentiment=agent_sentiment,
        supervisor_intervention=bool(supervisor_response),
        supervisor_response=supervisor_response
    )
    
    return response

# Route to serve HTML client
@app.get("/", response_class=HTMLResponse)
async def get_client():
    with open('client.html', 'r') as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

# Define the HTML content for the client
HTML_CLIENT = """
<!DOCTYPE html>
<html>
<head>
    <title>Customer Service Chat</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
        .chat-container { max-width: 800px; margin: 0 auto; border: 1px solid #ddd; border-radius: 5px; }
        .chat-messages { height: 400px; padding: 15px; overflow-y: auto; }
        .message { margin-bottom: 10px; padding: 10px; border-radius: 5px; }
        .user-message { background-color: #e1f5fe; margin-left: 20%; }
        .agent-message { background-color: #f5f5f5; margin-right: 20%; }
        .supervisor-message { background-color: #ffe0b2; margin-right: 20%; }
        .input-area { display: flex; padding: 10px; border-top: 1px solid #ddd; }
        input { flex-grow: 1; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        button { padding: 8px 16px; background: #4CAF50; color: white; border: none; border-radius: 4px; margin-left: 10px; cursor: pointer; }
        .sentiment { padding: 10px; text-align: right; font-size: 0.8em; color: #666; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-messages" id="messages">
            <div class="message agent-message">Hello! I'm your customer service agent. How can I help you today?</div>
        </div>
        <div class="sentiment" id="sentiment">User Sentiment: Neutral | Agent Sentiment: Neutral</div>
        <div class="input-area">
            <input type="text" id="user-input" placeholder="Type your message..." />
            <button onclick="sendMessage()">Send</button>
        </div>
    </div>

    <script>
        // Generate a session ID
        const sessionId = 'session_' + Math.random().toString(36).substring(2, 15);
        
        async function sendMessage() {
            const userInput = document.getElementById('user-input');
            const messagesDiv = document.getElementById('messages');
            const sentimentDiv = document.getElementById('sentiment');
            
            const message = userInput.value.trim();
            if (!message) return;
            
            // Display user message
            messagesDiv.innerHTML += `<div class="message user-message">${message}</div>`;
            userInput.value = '';
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
            
            try {
                // Send to server
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: message,
                        session_id: sessionId
                    }),
                });
                
                const data = await response.json();
                
                // Display agent response
                messagesDiv.innerHTML += `<div class="message agent-message">${data.agent_response}</div>`;
                
                // Display supervisor response if any
                if (data.supervisor_intervention) {
                    messagesDiv.innerHTML += `<div class="message supervisor-message"><strong>Supervisor:</strong> ${data.supervisor_response}</div>`;
                }
                
                // Update sentiment display
                const userSentimentText = data.user_sentiment > 0.3 ? 'Positive' : data.user_sentiment < -0.3 ? 'Negative' : 'Neutral';
                const agentSentimentText = data.agent_sentiment > 0.3 ? 'Positive' : data.agent_sentiment < -0.3 ? 'Negative' : 'Neutral';
                sentimentDiv.textContent = `User Sentiment: ${userSentimentText} | Agent Sentiment: ${agentSentimentText}`;
                
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            } catch (error) {
                console.error('Error:', error);
                messagesDiv.innerHTML += `<div class="message agent-message">Sorry, there was an error processing your request.</div>`;
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
        }
        
        // Allow sending messages with Enter key
        document.getElementById('user-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    </script>
</body>
</html>
"""

# Create client.html file if it doesn't exist
def ensure_client_html_exists():
    if not os.path.exists('client.html'):
        with open('client.html', 'w') as f:
            f.write(HTML_CLIENT)

# Call this function when the server starts
ensure_client_html_exists()

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
