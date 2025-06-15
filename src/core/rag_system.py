import os
import json
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import sqlite3
from config.config import Config

class RAGSystem:
    def __init__(self):
        self.embedding_model = SentenceTransformer(Config.EMBEDDING_MODEL)
        self.knowledge_base = self._load_knowledge_base()
        self.embeddings = self._create_embeddings()
    
    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        """Load knowledge base with common grievance scenarios and responses"""
        knowledge_base = [
            {
                "id": "kb_001",
                "category": "Hardware",
                "scenario": "laptop not working, computer issues, hardware problems",
                "response": "I understand you're experiencing hardware issues. This is quite common and we'll help resolve it quickly.",
                "follow_up_questions": ["What specific hardware component is causing issues?", "When did the problem start?"],
                "typical_resolution_time": "2-3 business days"
            },
            {
                "id": "kb_002", 
                "category": "Software",
                "scenario": "software not working, application crashes, program errors",
                "response": "Software issues can be frustrating. Let me help you get this resolved.",
                "follow_up_questions": ["Which software/application is having issues?", "What error message do you see?"],
                "typical_resolution_time": "1-2 business days"
            },
            {
                "id": "kb_003",
                "category": "Network",
                "scenario": "internet slow, network problems, connectivity issues, wifi not working",
                "response": "Network connectivity issues can impact your productivity. We'll prioritize getting this fixed.",
                "follow_up_questions": ["Is this affecting all devices or just one?", "When did you first notice the issue?"],
                "typical_resolution_time": "4-6 hours"
            },
            {
                "id": "kb_004",
                "category": "Account",
                "scenario": "login problems, password issues, account access, authentication",
                "response": "Account access issues need immediate attention for security reasons.",
                "follow_up_questions": ["What happens when you try to login?", "Have you recently changed your password?"],
                "typical_resolution_time": "2-4 hours"
            },
            {
                "id": "kb_005",
                "category": "Billing",
                "scenario": "billing issues, payment problems, invoice questions, charges",
                "response": "I'll help you resolve this billing concern. Let me look into the details.",
                "follow_up_questions": ["Which specific charge are you questioning?", "Do you have the invoice number?"],
                "typical_resolution_time": "3-5 business days"
            },
            {
                "id": "kb_006",
                "category": "Service",
                "scenario": "poor service, support issues, customer service problems",
                "response": "I apologize for any service issues you've experienced. We take this seriously.",
                "follow_up_questions": ["Can you describe the specific service issue?", "When did this occur?"],
                "typical_resolution_time": "1-2 business days"
            }
        ]
        return knowledge_base
    
    def _create_embeddings(self) -> np.ndarray:
        """Create embeddings for knowledge base scenarios"""
        scenarios = [item["scenario"] for item in self.knowledge_base]
        embeddings = self.embedding_model.encode(scenarios)
        return embeddings
    
    def find_relevant_context(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Find most relevant knowledge base entries for a query"""
        query_embedding = self.embedding_model.encode([query])
        
        # Calculate cosine similarity
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        
        # Get top-k most similar entries
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        relevant_entries = []
        for idx in top_indices:
            if similarities[idx] > 0.3:  # Minimum similarity threshold
                entry = self.knowledge_base[idx].copy()
                entry["similarity_score"] = float(similarities[idx])
                relevant_entries.append(entry)
        
        return relevant_entries
    
    def get_contextual_response(self, complaint_details: str) -> Dict[str, Any]:
        """Get contextual response based on complaint details"""
        relevant_context = self.find_relevant_context(complaint_details)
        
        if not relevant_context:
            return {
                "response": "Thank you for your complaint. We'll review it and get back to you soon.",
                "category": "Other",
                "estimated_resolution": "3-5 business days",
                "follow_up_questions": ["Could you provide more specific details about the issue?"]
            }
        
        best_match = relevant_context[0]
        return {
            "response": best_match["response"],
            "category": best_match["category"],
            "estimated_resolution": best_match["typical_resolution_time"],
            "follow_up_questions": best_match["follow_up_questions"],
            "similarity_score": best_match["similarity_score"]
        }
    
    def get_similar_complaints(self, complaint_details: str, db_manager) -> List[Dict[str, Any]]:
        """Find similar complaints from database using RAG"""
        try:
            # Get all complaints from database
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT complaint_id, complaint_details, status, category FROM complaints")
                complaints = cursor.fetchall()
            
            if not complaints:
                return []
            
            # Create embeddings for existing complaints
            complaint_texts = [complaint['complaint_details'] for complaint in complaints]
            complaint_embeddings = self.embedding_model.encode(complaint_texts)
            
            # Find similar complaints
            query_embedding = self.embedding_model.encode([complaint_details])
            similarities = cosine_similarity(query_embedding, complaint_embeddings)[0]
            
            # Get top similar complaints
            similar_complaints = []
            for i, similarity in enumerate(similarities):
                if similarity > 0.4:  # Similarity threshold
                    similar_complaints.append({
                        "complaint_id": complaints[i]['complaint_id'],
                        "complaint_details": complaints[i]['complaint_details'],
                        "status": complaints[i]['status'],
                        "category": complaints[i]['category'],
                        "similarity_score": float(similarity)
                    })
            
            # Sort by similarity score
            similar_complaints.sort(key=lambda x: x['similarity_score'], reverse=True)
            return similar_complaints[:5]  # Return top 5
            
        except Exception as e:
            print(f"Error finding similar complaints: {e}")
            return []
    
    def generate_status_update_message(self, complaint_id: str, status: str, db_manager) -> str:
        """Generate contextual status update message"""
        try:
            complaint = db_manager.get_complaint_by_id(complaint_id)
            if not complaint:
                return f"Complaint {complaint_id} not found."
            
            # Get contextual information
            context = self.get_contextual_response(complaint.complaint_details)
            
            status_messages = {
                "Registered": f"Your complaint {complaint_id} has been registered successfully. Expected resolution time: {context.get('estimated_resolution', '3-5 business days')}.",
                "In Progress": f"Good news! Your complaint {complaint_id} is now being actively worked on by our technical team.",
                "Under Review": f"Your complaint {complaint_id} is under review by our specialists. We're analyzing the issue thoroughly.",
                "Resolved": f"Great news! Your complaint {complaint_id} has been resolved. Please verify if the issue is fixed.",
                "Closed": f"Your complaint {complaint_id} has been closed. Thank you for your patience.",
                "Rejected": f"Unfortunately, your complaint {complaint_id} could not be processed. Please contact support for more details."
            }
            
            return status_messages.get(status, f"Your complaint {complaint_id} status has been updated to: {status}")
            
        except Exception as e:
            print(f"Error generating status message: {e}")
            return f"Your complaint {complaint_id} status is: {status}"
