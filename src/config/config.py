import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Groq API Configuration
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = "mixtral-8x7b-32768"  # Default Groq model

    # Database Configuration - Use absolute path to ensure consistency
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATABASE_URL = os.path.join(PROJECT_ROOT, "data", "grievance_system.db")
    
    # API Configuration
    API_HOST = os.getenv("HOST", "127.0.0.1")
    API_PORT = int(os.getenv("PORT", "8000"))
    API_BASE_URL = f"http://{API_HOST}:{API_PORT}"
    
    # RAG Configuration
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    VECTOR_DB_PATH = "vector_db"
    
    # Application Configuration
    APP_TITLE = "Grievance Management Chatbot"
    APP_DESCRIPTION = "RAG-based chatbot for complaint registration and status tracking"
    
    # Complaint Status Options
    COMPLAINT_STATUSES = [
        "Registered",
        "In Progress", 
        "Under Review",
        "Resolved",
        "Closed",
        "Rejected"
    ]
    
    # Session Configuration
    SESSION_TIMEOUT = 3600  # 1 hour in seconds
