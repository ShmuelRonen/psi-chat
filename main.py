import os
from typing import List, Dict, Optional
import requests
import logging
import traceback
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv
from prompts import SYSTEM_PROMPT, INITIAL_PROMPT, FOLLOW_UP_PROMPT, ANALYSIS_PROMPT
import json
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# DeepSeek API configuration
DEEPSEEK_API_KEY = os.getenv("deepseek_api_key")
logger.info(f"API Key: {DEEPSEEK_API_KEY}")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Initialize FastAPI app
app = FastAPI()

# Mount templates directory
templates = Jinja2Templates(directory="templates")

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory storage for conversations
conversations = {}

class Message(BaseModel):
    role: str
    content: str

class Conversation(BaseModel):
    messages: List[Message]
    analysis: str = ""
    session_id: Optional[str] = None

class StartRequest(BaseModel):
    messages: List[Message]
    session_id: Optional[str] = None

def get_ai_response(messages: List[Dict], prompt: str, session_id: Optional[str] = None) -> str:
    """Get response from DeepSeek API"""
    try:
        # Convert messages to DeepSeek format
        deepseek_messages = []
        
        # Add conversation messages (excluding system messages)
        for msg in messages:
            if msg["role"] in ["user", "assistant"]:
                deepseek_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Always add the specific prompt at the end as a system message
        deepseek_messages.append({
            "role": "system",
            "content": prompt + "\nPlease respond in Hebrew."
        })
        
        # Prepare the request
        headers = {
            "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY')}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": deepseek_messages,
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": False
        }
        
        # Log request for debugging
        logger.info(f"Sending request to DeepSeek API with {len(deepseek_messages)} messages")
        logger.info(f"Last message: {deepseek_messages[-1]['content']}")
        
        # Determine timeout based on whether this is an analysis request
        timeout = 60 if ANALYSIS_PROMPT in prompt else 30
        
        # Make the API call
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=timeout
        )
        
        # Log response for debugging
        logger.info(f"DeepSeek API response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"DeepSeek API error: {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"DeepSeek API error: {response.text}"
            )
        
        # Parse the response
        result = response.json()
        ai_response = result["choices"][0]["message"]["content"]
        
        return ai_response
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request to DeepSeek API failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get response from DeepSeek API: {str(e)}")
    except Exception as e:
        logger.error(f"Error in get_ai_response: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def get_chat_interface(request: Request):
    """Serve the chat interface"""
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        logger.error(f"Error serving template: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error serving template: {str(e)}")

def clean_text(text: str) -> str:
    """Clean text from invalid characters and normalize encoding"""
    # Remove the specific problematic character ()
    text = text.replace('', '')
    # Remove other potential invalid characters
    text = ''.join(char for char in text if ord(char) < 0x10000)
    return text

def start_conversation(message: str, conversation_history: List[Dict] = None) -> Dict:
    """Start a new conversation with the given message"""
    try:
        # Generate a new session ID
        session_id = str(uuid.uuid4())
        
        # Initialize conversation with system message
        conversations[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # If we have conversation history, add it
        if conversation_history:
            conversations[session_id].extend(conversation_history)
        
        # Add user message
        conversations[session_id].append({"role": "user", "content": message})
        
        # Get AI response
        response = get_ai_response(conversations[session_id], FOLLOW_UP_PROMPT)
        
        # Add AI response to conversation
        conversations[session_id].append({"role": "assistant", "content": response})
        
        logger.info(f"Started new conversation with session ID: {session_id}")
        
        return {
            "session_id": session_id,
            "message": response
        }
        
    except Exception as e:
        logger.error(f"Error in start_conversation: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

def continue_conversation(session_id: str, message: str) -> Dict:
    """Continue an existing conversation with the given message"""
    try:
        # Check if session exists
        if session_id not in conversations:
            raise ValueError(f"Session {session_id} not found")
        
        # Add user message to conversation
        conversations[session_id].append({"role": "user", "content": message})
        
        # Get AI response
        response = get_ai_response(conversations[session_id], FOLLOW_UP_PROMPT)
        
        # Add AI response to conversation
        conversations[session_id].append({"role": "assistant", "content": response})
        
        logger.info(f"Continued conversation {session_id}")
        
        return {
            "session_id": session_id,
            "messages": [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response}
            ]
        }
        
    except Exception as e:
        logger.error(f"Error in continue_conversation: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze")
async def analyze_conversation(request: Request):
    """Analyze the conversation and return insights about the user"""
    try:
        logger.info("=== Starting Analysis ===")
        data = await request.json()
        conversation_history = data.get("conversation_history", [])
        
        logger.info(f"Received {len(conversation_history)} messages for analysis")
        
        if not conversation_history:
            logger.warning("No conversation history provided for analysis")
            raise HTTPException(status_code=400, detail="No conversation history provided")
        
        # Clean all messages in the conversation history
        cleaned_history = []
        for msg in conversation_history:
            if "content" in msg:
                cleaned_history.append({
                    "role": msg["role"],
                    "content": clean_text(msg["content"])
                })
        
        logger.info(f"Cleaned {len(cleaned_history)} messages for analysis")
        
        # Create analysis messages - only include conversation history
        analysis_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *cleaned_history
        ]
        
        logger.info(f"Prepared {len(analysis_messages)} messages for analysis")
        
        # Get analysis from DeepSeek using ANALYSIS_PROMPT
        try:
            logger.info("Sending analysis request to DeepSeek API")
            
            # Create a custom analysis prompt that includes the required phrase
            custom_analysis_prompt = ANALYSIS_PROMPT + "\n\nחשוב: התשובה שלך חייבת להתחיל בדיוק במשפט הבא:\n\"בהתבסס על שיחתנו עד כה, אוכל לשתף אותך במספר תובנות על עצמך שעשויות לעניין אותך:\""
            
            analysis = get_ai_response(analysis_messages, custom_analysis_prompt)
            
            # Clean the analysis
            analysis = clean_text(analysis)
            logger.info(f"Received analysis response: {analysis[:100]}...")
            
            # Ensure the analysis starts with the required phrase
            required_phrase = "בהתבסס על שיחתנו עד כה, אוכל לשתף אותך במספר תובנות על עצמך שעשויות לעניין אותך:"
            if not analysis.startswith(required_phrase):
                analysis = required_phrase + "\n\n" + analysis
                logger.info("Added required phrase to the beginning of the analysis")
            
            return JSONResponse({
                "analysis": analysis
            })
            
        except Exception as e:
            logger.error(f"Error getting analysis from DeepSeek: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail="Failed to generate analysis")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in analyze_conversation: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/last-conversation")
async def get_last_chat():
    """Get the most recent conversation"""
    try:
        # Get the most recent session ID
        if not conversations:
            return {"session_id": None, "messages": []}
            
        session_id = list(conversations.keys())[-1]
        return {
            "session_id": session_id,
            "messages": conversations[session_id]
        }
    except Exception as e:
        logger.error(f"Error getting last conversation: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/start")
async def start_chat(request: Request):
    """Start a new conversation"""
    try:
        data = await request.json()
        message = data.get("message", "")
        conversation_history = data.get("conversation_history", [])
        
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        # If we have conversation history, use it
        if conversation_history:
            result = start_conversation(message, conversation_history)
        else:
            result = start_conversation(message)
            
        return result
    except Exception as e:
        logger.error(f"Error starting conversation: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/continue")
async def continue_chat(request: Request):
    """Continue an existing conversation"""
    try:
        data = await request.json()
        session_id = data.get("session_id")
        message = data.get("message", "")
        
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID is required")
        
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        result = continue_conversation(session_id, message)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error continuing conversation: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    try:
        logger.info("Starting server...")
        uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}") 