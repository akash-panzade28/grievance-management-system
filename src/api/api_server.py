from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
from datetime import datetime
import random

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.models import (
    ComplaintRequest, ComplaintResponse, StatusUpdateRequest,
    ComplaintStatus, UserContext
)
from database.database import DatabaseManager
from core.rag_system import RAGSystem
from config.config import Config

app = FastAPI(
    title=Config.APP_TITLE,
    description=Config.APP_DESCRIPTION,
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
db_manager = DatabaseManager()
rag_system = RAGSystem()

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    db_manager.init_database()
    print("Database initialized successfully")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Grievance Management API", "status": "running"}

@app.post("/register-complaint", response_model=ComplaintResponse)
async def register_complaint(complaint: ComplaintRequest):
    """Register a new complaint"""
    try:
        # Get contextual information using RAG
        context = rag_system.get_contextual_response(complaint.complaint_details)
        
        # Auto-categorize if not provided
        if complaint.category is None:
            from core.llm_handler import LLMHandler
            llm = LLMHandler()
            complaint.category = llm.categorize_complaint(complaint.complaint_details)
        
        # Register complaint in database
        complaint_response = db_manager.register_complaint(complaint)
        
        return complaint_response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error registering complaint: {str(e)}")

@app.get("/complaint-status/{complaint_id}", response_model=ComplaintResponse)
async def get_complaint_status(complaint_id: str):
    """Get complaint status by ID"""
    try:
        complaint = db_manager.get_complaint_by_id(complaint_id)
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")
        
        return complaint
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching complaint: {str(e)}")

@app.get("/user-complaints/{mobile}", response_model=List[ComplaintResponse])
async def get_user_complaints(mobile: str):
    """Get all complaints for a mobile number"""
    try:
        complaints = db_manager.get_complaints_by_mobile(mobile)
        return complaints
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching complaints: {str(e)}")

@app.put("/update-complaint-status/{complaint_id}")
async def update_complaint_status(complaint_id: str, status_update: StatusUpdateRequest):
    """Update complaint status (for admin use)"""
    try:
        success = db_manager.update_complaint_status(
            complaint_id, 
            status_update.status, 
            status_update.notes
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Complaint not found")
        
        return {"message": "Status updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating status: {str(e)}")

@app.get("/complaint-history/{complaint_id}")
async def get_complaint_history(complaint_id: str):
    """Get status change history for a complaint"""
    try:
        # Check if complaint exists
        complaint = db_manager.get_complaint_by_id(complaint_id)
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")
        
        history = db_manager.get_status_history(complaint_id)
        return {"complaint_id": complaint_id, "history": history}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching history: {str(e)}")

@app.get("/similar-complaints")
async def get_similar_complaints(complaint_details: str, limit: int = 5):
    """Get similar complaints using RAG"""
    try:
        similar = rag_system.get_similar_complaints(complaint_details, db_manager)
        return {"similar_complaints": similar[:limit]}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding similar complaints: {str(e)}")

@app.get("/contextual-response")
async def get_contextual_response(complaint_details: str):
    """Get contextual response for complaint details"""
    try:
        context = rag_system.get_contextual_response(complaint_details)
        return context
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

@app.post("/simulate-status-update/{complaint_id}")
async def simulate_status_update(complaint_id: str):
    """Simulate status update for demo purposes"""
    try:
        complaint = db_manager.get_complaint_by_id(complaint_id)
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")
        
        # Simulate status progression
        current_status = complaint.status
        status_progression = {
            ComplaintStatus.REGISTERED: ComplaintStatus.IN_PROGRESS,
            ComplaintStatus.IN_PROGRESS: ComplaintStatus.UNDER_REVIEW,
            ComplaintStatus.UNDER_REVIEW: ComplaintStatus.RESOLVED
        }
        
        new_status = status_progression.get(current_status, current_status)
        
        if new_status != current_status:
            db_manager.update_complaint_status(
                complaint_id, 
                new_status, 
                "Status updated automatically for demo"
            )
            
            # Generate contextual message
            message = rag_system.generate_status_update_message(complaint_id, new_status.value, db_manager)
            
            return {
                "complaint_id": complaint_id,
                "old_status": current_status.value,
                "new_status": new_status.value,
                "message": message
            }
        else:
            return {
                "complaint_id": complaint_id,
                "status": current_status.value,
                "message": "No status change needed"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error simulating update: {str(e)}")

# Admin endpoints
@app.put("/admin/complaint/{complaint_id}/status")
async def update_complaint_status_admin(complaint_id: str, status_data: dict):
    """Update complaint status (Admin endpoint)"""
    try:
        new_status = status_data.get("status")
        if not new_status:
            raise HTTPException(status_code=400, detail="Status is required")

        # Convert string to enum
        try:
            status_enum = ComplaintStatus(new_status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status value")

        complaint = db_manager.get_complaint_by_id(complaint_id)
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        # Update status
        db_manager.update_complaint_status(complaint_id, status_enum, "Updated by admin")

        return {
            "message": "Status updated successfully",
            "complaint_id": complaint_id,
            "new_status": new_status
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")

@app.delete("/admin/complaint/{complaint_id}")
async def delete_complaint_admin(complaint_id: str):
    """Delete a complaint (Admin endpoint)"""
    try:
        complaint = db_manager.get_complaint_by_id(complaint_id)
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        # Delete complaint
        success = db_manager.delete_complaint(complaint_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete complaint")

        return {
            "message": "Complaint deleted successfully",
            "complaint_id": complaint_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete complaint: {str(e)}")

@app.get("/admin/complaints")
async def get_all_complaints_admin():
    """Get all complaints for admin dashboard"""
    try:
        complaints = db_manager.get_all_complaints()
        return [
            {
                "complaint_id": c.complaint_id,
                "name": c.name,
                "mobile": c.mobile,
                "complaint_details": c.complaint_details,
                "category": c.category.value,
                "status": c.status.value,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat()
            }
            for c in complaints
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch complaints: {str(e)}")

@app.get("/admin/stats")
async def get_admin_stats():
    """Get statistics for admin dashboard"""
    try:
        stats = db_manager.get_complaint_statistics()
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch statistics: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=True
    )
