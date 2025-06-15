import os
from groq import Groq
from typing import Dict, List, Optional, Any
import json
import re
from config.config import Config
from models.models import UserContext, ComplaintCategory

class LLMHandler:
    def __init__(self):
        try:
            # Initialize Groq client with just the API key
            if Config.GROQ_API_KEY:
                self.client = Groq(api_key=Config.GROQ_API_KEY)
            else:
                print("Warning: No Groq API key provided")
                self.client = None
            self.model = Config.GROQ_MODEL
        except Exception as e:
            print(f"Warning: Could not initialize Groq client: {e}")
            self.client = None
            self.model = Config.GROQ_MODEL
        
    def extract_intent(self, user_message: str, context: UserContext) -> Dict[str, Any]:
        """Extract user intent from message"""
        
        system_prompt = """You are an AI assistant for a grievance management system. 
        Analyze the user's message and determine their intent. 
        
        Possible intents:
        1. "register_complaint" - User wants to register a new complaint
        2. "check_status" - User wants to check complaint status
        3. "provide_info" - User is providing requested information (name, mobile, details)
        4. "general" - General conversation or unclear intent
        
        Also extract any relevant information like:
        - name (if mentioned)
        - mobile number (if mentioned) 
        - complaint details (if mentioned)
        - complaint category (Hardware, Software, Network, Account, Billing, Service, Other)
        
        Return response as JSON with keys: intent, extracted_info, confidence
        """
        
        user_prompt = f"""
        Current conversation context: {context.dict()}
        User message: "{user_message}"
        
        Analyze this message and return the intent and extracted information.
        """
        
        if not self.client:
            return self._fallback_intent_detection(user_message, context)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )

            result = response.choices[0].message.content
            # Try to parse JSON response
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                # Fallback to simple intent detection
                return self._fallback_intent_detection(user_message, context)

        except Exception as e:
            print(f"Error in intent extraction: {e}")
            return self._fallback_intent_detection(user_message, context)
    
    def _fallback_intent_detection(self, user_message: str, context: UserContext) -> Dict[str, Any]:
        """Fallback intent detection using simple rules"""
        message_lower = user_message.lower()
        
        # Check for complaint registration keywords
        register_keywords = ["complaint", "complain", "issue", "problem", "register", "file", "report"]
        status_keywords = ["status", "check", "update", "progress", "what's", "how's"]
        
        extracted_info = {}
        
        # Extract mobile number
        mobile_pattern = r'(\+?\d{10,15})'
        mobile_match = re.search(mobile_pattern, user_message)
        if mobile_match:
            extracted_info['mobile'] = mobile_match.group(1)
        
        # Extract name (simple heuristic)
        if context.current_step == "collecting_name":
            # Assume the entire message is the name if we're collecting name
            extracted_info['name'] = user_message.strip()
        
        # Determine intent
        if context.current_step in ["collecting_name", "collecting_mobile", "collecting_details"]:
            intent = "provide_info"
        elif any(keyword in message_lower for keyword in register_keywords):
            intent = "register_complaint"
        elif any(keyword in message_lower for keyword in status_keywords):
            intent = "check_status"
        else:
            intent = "general"
        
        return {
            "intent": intent,
            "extracted_info": extracted_info,
            "confidence": 0.7
        }
    
    def generate_response(self, user_message: str, context: UserContext, intent_data: Dict[str, Any]) -> str:
        """Generate appropriate response based on intent and context"""
        
        system_prompt = f"""You are a helpful customer service assistant for a grievance management system.
        
        Current user context:
        - Name: {context.name or 'Not provided'}
        - Mobile: {context.mobile or 'Not provided'}  
        - Current step: {context.current_step}
        - Complaint details: {context.complaint_details or 'Not provided'}
        
        User intent: {intent_data.get('intent', 'general')}
        Extracted info: {intent_data.get('extracted_info', {})}
        
        Guidelines:
        1. Be polite and professional
        2. If registering complaint, collect name, mobile, and complaint details step by step
        3. If checking status, ask for complaint ID or mobile number
        4. Keep responses concise and clear
        5. Guide the user through the process
        """
        
        user_prompt = f"User message: '{user_message}'\nGenerate an appropriate response."
        
        if not self.client:
            return self._fallback_response(intent_data.get('intent', 'general'), context)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error generating response: {e}")
            return self._fallback_response(intent_data.get('intent', 'general'), context)
    
    def _fallback_response(self, intent: str, context: UserContext) -> str:
        """Fallback responses when LLM fails"""
        
        if intent == "register_complaint":
            if not context.name:
                return "I'd be happy to help you register a complaint. Could you please provide your full name?"
            elif not context.mobile:
                return "Thank you! Now, could you please provide your mobile number?"
            elif not context.complaint_details:
                return "Great! Now please describe your complaint in detail."
            else:
                return "Thank you for providing all the details. I'm registering your complaint now."
        
        elif intent == "check_status":
            return "I can help you check your complaint status. Could you please provide your complaint ID or mobile number?"
        
        elif intent == "provide_info":
            if context.current_step == "collecting_name":
                return "Thank you for providing your name. Could you please share your mobile number?"
            elif context.current_step == "collecting_mobile":
                return "Perfect! Now please describe your complaint in detail."
            elif context.current_step == "collecting_details":
                return "Thank you for the details. I'm processing your complaint registration."
        
        return "Hello! I'm here to help you with complaint registration and status checking. How can I assist you today?"
    
    def categorize_complaint(self, complaint_details: str) -> ComplaintCategory:
        """Categorize complaint based on details"""
        details_lower = complaint_details.lower()
        
        # Simple keyword-based categorization
        if any(word in details_lower for word in ['laptop', 'computer', 'hardware', 'mouse', 'keyboard', 'screen']):
            return ComplaintCategory.HARDWARE
        elif any(word in details_lower for word in ['software', 'application', 'app', 'program', 'bug']):
            return ComplaintCategory.SOFTWARE
        elif any(word in details_lower for word in ['internet', 'network', 'wifi', 'connection', 'slow']):
            return ComplaintCategory.NETWORK
        elif any(word in details_lower for word in ['account', 'login', 'password', 'access']):
            return ComplaintCategory.ACCOUNT
        elif any(word in details_lower for word in ['bill', 'payment', 'charge', 'refund']):
            return ComplaintCategory.BILLING
        elif any(word in details_lower for word in ['service', 'support', 'help', 'assistance']):
            return ComplaintCategory.SERVICE
        else:
            return ComplaintCategory.OTHER
