import os
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc
from pydantic import BaseModel
from dotenv import load_dotenv

# Groq Import
from groq import Groq

# Database Imports
import database
from database import SessionLocal, engine, Thread, Message

# Load environment variables
load_dotenv()

app = FastAPI(title="AI Chat App Backend")

# Initialize Groq Client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not found in environment variables.")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize DB on startup
@app.on_event("startup")
def on_startup():
    database.init_db()

# Pydantic Models for requests/responses
class ThreadCreate(BaseModel):
    title: str

class ThreadResponse(BaseModel):
    id: int
    title: str
    class Config:
        orm_mode = True

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: int
    thread_id: int
    role: str
    content: str
    class Config:
        orm_mode = True

# Endpoints
@app.post("/threads", response_model=ThreadResponse)
def create_thread(thread: ThreadCreate, db: Session = Depends(get_db)):
    db_thread = Thread(title=thread.title)
    db.add(db_thread)
    db.commit()
    db.refresh(db_thread)
    return db_thread

@app.get("/threads", response_model=List[ThreadResponse])
def get_threads(db: Session = Depends(get_db)):
    return db.query(Thread).order_by(Thread.created_at.desc()).all()

@app.get("/threads/{thread_id}/messages", response_model=List[MessageResponse])
def get_messages(thread_id: int, db: Session = Depends(get_db)):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.created_at.asc()).all()

@app.post("/threads/{thread_id}/messages", response_model=MessageResponse)
def post_message(thread_id: int, message: MessageCreate, db: Session = Depends(get_db)):
    # 1. Verify thread exists
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # 2. Save user message to DB
    user_msg = Message(thread_id=thread_id, role="user", content=message.content)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # 3. Universal Memory Implementation
    # We fetch ALL messages from ALL threads to provide context of everything the user has ever said.
    # This might be large, but it satisfies the requirement simply.
    all_messages = db.query(Message).order_by(Message.created_at.asc()).all()
    
    # Format messages for Groq API
    # Start with a system prompt telling it to act as an assistant
    chat_history = [
        {"role": "system", "content": "You are a helpful AI assistant. You remember all past conversations across all threads."}
    ]
    
    for msg in all_messages:
        chat_history.append({"role": msg.role, "content": msg.content})
    
    # 4. Call Groq
    if not groq_client:
        raise HTTPException(status_code=500, detail="Groq client not configured")
        
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=chat_history,
            model="llama-3.1-8b-instant", # Using a supported Groq model
            temperature=0.7,
        )
        ai_content = chat_completion.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error communicating with Groq: {str(e)}")
        
    # 5. Save AI response to DB
    ai_msg = Message(thread_id=thread_id, role="assistant", content=ai_content)
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)
    
    return ai_msg
