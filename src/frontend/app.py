import streamlit as st
import requests
import json
from datetime import datetime
from typing import Dict, Any, Optional
import time
import re

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from models.models import UserContext, ComplaintRequest, ComplaintCategory
from core.llm_handler import LLMHandler
from config.config import Config

# Page configuration
st.set_page_config(
    page_title="Grievance Management Chatbot",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_context" not in st.session_state:
    st.session_state.user_context = UserContext()
if "llm_handler" not in st.session_state:
    try:
        st.session_state.llm_handler = LLMHandler()
    except Exception as e:
        st.error(f"Could not initialize LLM handler: {e}")
        st.session_state.llm_handler = None

def check_api_server():
    """Check if API server is running"""
    try:
        response = requests.get(f"{Config.API_BASE_URL}/", timeout=5)
        return response.status_code == 200
    except:
        return False

def validate_mobile(mobile: str) -> bool:
    """Validate mobile number format"""
    pattern = r"^\+?[1-9]\d{9,14}$"
    return bool(re.match(pattern, mobile.strip()))

def validate_name(name: str) -> bool:
    """Validate name format - very permissive"""
    name = name.strip()

    # Basic length check
    if len(name) < 2 or len(name) > 50:
        return False

    # Must contain at least one letter
    if not any(c.isalpha() for c in name):
        return False

    # Reject only obvious non-names (very short list)
    non_names = {'help', 'what', 'yes', 'no', 'ok'}
    if name.lower() in non_names:
        return False

    # Accept almost everything else
    return True

def register_complaint_api(name: str, mobile: str, complaint_details: str, category: str = "Other") -> Dict[str, Any]:
    """Call API to register complaint"""
    try:
        complaint_data = {
            "name": name,
            "mobile": mobile,
            "complaint_details": complaint_details,
            "category": category
        }
        
        response = requests.post(
            f"{Config.API_BASE_URL}/register-complaint",
            json=complaint_data,
            timeout=10
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"API Error: {response.status_code}"}
            
    except Exception as e:
        return {"success": False, "error": f"Connection error: {str(e)}"}

def get_complaint_status_api(complaint_id: str) -> Dict[str, Any]:
    """Get complaint status from API"""
    try:
        response = requests.get(
            f"{Config.API_BASE_URL}/complaint-status/{complaint_id}",
            timeout=10
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        elif response.status_code == 404:
            return {"success": False, "error": "Complaint not found"}
        else:
            return {"success": False, "error": f"API Error: {response.status_code}"}
            
    except Exception as e:
        return {"success": False, "error": f"Connection error: {str(e)}"}

def get_user_complaints_api(mobile: str) -> Dict[str, Any]:
    """Get user complaints from API"""
    try:
        response = requests.get(
            f"{Config.API_BASE_URL}/user-complaints/{mobile}",
            timeout=10
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": f"API Error: {response.status_code}"}
            
    except Exception as e:
        return {"success": False, "error": f"Connection error: {str(e)}"}

def extract_user_details(message: str) -> Dict[str, Any]:
    """Smart extraction of user details from message"""
    extracted = {}

    # Extract mobile number (various formats)
    mobile_patterns = [
        r'\+\d{1,3}[-.\s]?\d{10,14}',  # +91-9876543210, +1 234 567 8900
        r'\b\d{10,15}\b',              # 9876543210, 1234567890
        r'\(\d{3}\)\s?\d{3}[-.\s]?\d{4}'  # (123) 456-7890
    ]

    for pattern in mobile_patterns:
        match = re.search(pattern, message)
        if match:
            mobile = re.sub(r'[-.\s()]', '', match.group())
            if len(mobile) >= 10:
                extracted['mobile'] = mobile if mobile.startswith('+') else mobile
                break

    # Extract name (look for "my name is", "I am", etc.)
    name_patterns = [
        r'(?:my name is|i am|i\'m|name is|call me)\s+([a-zA-Z\s]{2,30})',
        r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',  # Proper case names at start
    ]

    for pattern in name_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if len(name) >= 2 and name.replace(' ', '').isalpha():
                extracted['name'] = name
                break

    # Extract complaint ID
    complaint_id_match = re.search(r'CMP[A-Z0-9]{8}', message.upper())
    if complaint_id_match:
        extracted['complaint_id'] = complaint_id_match.group()

    return extracted

def smart_intent_detection(message: str, context: UserContext) -> Dict[str, Any]:
    """Advanced intent detection with context awareness"""
    message_lower = message.lower()
    extracted_details = extract_user_details(message)

    # If user is in middle of registration, continue that flow
    if context.current_step != "initial":
        return {
            "intent": "continue_registration",
            "extracted_info": extracted_details,
            "confidence": 0.9
        }

    # Check for complaint ID in message - high priority for status check
    if extracted_details.get('complaint_id'):
        return {
            "intent": "check_status_by_id",
            "extracted_info": extracted_details,
            "confidence": 0.95
        }

    # Check for mobile number with status keywords
    if extracted_details.get('mobile') and any(word in message_lower for word in ["status", "check", "my complaints"]):
        return {
            "intent": "check_status_by_mobile",
            "extracted_info": extracted_details,
            "confidence": 0.9
        }

    # Registration intent with various keywords
    registration_keywords = [
        "complaint", "complain", "issue", "problem", "register", "file", "report",
        "submit", "lodge", "raise", "create", "new complaint", "have a problem",
        "facing issue", "not working", "broken", "error", "bug", "fault"
    ]

    if any(keyword in message_lower for keyword in registration_keywords):
        return {
            "intent": "register_complaint",
            "extracted_info": extracted_details,
            "confidence": 0.85
        }

    # Status check intent
    status_keywords = [
        "status", "check", "update", "progress", "what's", "how's", "where is",
        "track", "follow up", "any update", "current status"
    ]

    if any(keyword in message_lower for keyword in status_keywords):
        return {
            "intent": "check_status",
            "extracted_info": extracted_details,
            "confidence": 0.8
        }

    # Help and greeting intents
    if any(word in message_lower for word in ["help", "how", "what", "guide", "instructions"]):
        return {
            "intent": "help",
            "extracted_info": extracted_details,
            "confidence": 0.7
        }

    if any(word in message_lower for word in ["hello", "hi", "hey", "good morning", "good afternoon"]):
        return {
            "intent": "greeting",
            "extracted_info": extracted_details,
            "confidence": 0.7
        }

    return {
        "intent": "general",
        "extracted_info": extracted_details,
        "confidence": 0.5
    }

class IntentBasedResponseSystem:
    """Advanced intent-based response system with memory integration"""

    def __init__(self):
        self.memory_system = ConversationMemory()

    def extract_information(self, user_message: str) -> Dict[str, Any]:
        """Enhanced extraction of structured information from user message"""
        import re

        extracted = {}
        message_lower = user_message.lower()
        original_message = user_message.strip()

        # Enhanced mobile number extraction with better patterns
        mobile_patterns = [
            r'(\+\d{1,4}[-.\s]?\d{10,14})',  # International with country code
            r'(\+\d{1,4}\s?\d{10,14})',      # International compact
            r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})',  # US format: 123-456-7890
            r'(\d{10,15})',                   # Simple digits 10-15 chars
            r'(\(\d{3}\)\s?\d{3}[-.\s]?\d{4})',  # (123) 456-7890
        ]

        for pattern in mobile_patterns:
            mobile_matches = re.findall(pattern, user_message)
            for mobile_match in mobile_matches:
                mobile = mobile_match.strip()
                # Clean up mobile number
                mobile_clean = re.sub(r'[-.\s\(\)]', '', mobile)
                # Validate mobile number length and format
                if 10 <= len(mobile_clean) <= 15 and mobile_clean.isdigit():
                    extracted['mobile'] = mobile_clean
                    break
            if 'mobile' in extracted:
                break

        # Extract complaint ID with better validation
        complaint_id_patterns = [
            r'\b(CMP[A-Z0-9]{8,10})\b',  # Standard format
            r'\b(cmp[a-z0-9]{8,10})\b',  # Lowercase
            r'complaint\s+(?:id|number)?\s*:?\s*([A-Z0-9]{10,12})',  # With prefix
        ]

        for pattern in complaint_id_patterns:
            complaint_match = re.search(pattern, user_message, re.IGNORECASE)
            if complaint_match:
                extracted['complaint_id'] = complaint_match.group(1).upper()
                break

        # Enhanced name extraction with better patterns and validation
        name_patterns = [
            r"(?:i'm|i am|my name is|name is|call me)\s+([a-zA-Z][a-zA-Z\s]{1,40})",
            r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})$",  # Proper case names
            r"name:\s*([a-zA-Z][a-zA-Z\s]{1,40})",
            r"hi,?\s+(?:i'm|i am)\s+([a-zA-Z][a-zA-Z\s]{1,40})",
        ]

        # Check if the entire message could be a name (during name collection)
        if len(original_message.split()) <= 4 and re.match(r'^[a-zA-Z\s]{2,40}$', original_message):
            # Additional validation for names
            words = original_message.split()
            if all(len(word) >= 2 for word in words) and all(word.isalpha() for word in words):
                # Check if it's not a common non-name phrase
                non_name_phrases = ['yes', 'no', 'ok', 'okay', 'sure', 'hello', 'hi', 'help', 'what', 'how']
                if original_message.lower() not in non_name_phrases:
                    extracted['name'] = ' '.join(word.capitalize() for word in words)

        # Try pattern-based extraction
        for pattern in name_patterns:
            name_match = re.search(pattern, user_message, re.IGNORECASE)
            if name_match:
                name = name_match.group(1).strip()
                # Clean and validate name
                name_words = name.split()
                if 1 <= len(name_words) <= 4:  # 1-4 words
                    # Check each word is valid (letters only, reasonable length)
                    if all(2 <= len(word) <= 20 and word.isalpha() for word in name_words):
                        # Exclude common non-name words
                        non_names = {'help', 'what', 'how', 'when', 'where', 'why', 'yes', 'no', 'ok', 'okay'}
                        if not any(word.lower() in non_names for word in name_words):
                            extracted['name'] = ' '.join(word.capitalize() for word in name_words)
                            break

        # Enhanced email extraction
        email_patterns = [
            r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b',
            r'email:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
        ]

        for pattern in email_patterns:
            email_match = re.search(pattern, user_message)
            if email_match:
                extracted['email'] = email_match.group(1).lower()
                break

        # Extract additional context information
        if 'urgent' in message_lower or 'emergency' in message_lower:
            extracted['urgency'] = 'high'
        elif 'asap' in message_lower or 'immediately' in message_lower:
            extracted['urgency'] = 'high'

        return extracted

    def process_user_message(self, user_message: str) -> str:
        """Process user message with advanced intent recognition and memory"""
        context = st.session_state.user_context

        # Extract information from user message
        extracted_info = self.extract_information(user_message)

        # Get conversation insights
        insights = self.memory_system.get_contextual_insights()

        # Determine intent with context awareness
        intent = self.determine_advanced_intent(user_message, extracted_info, insights, context)

        # Generate contextual response
        response = self.generate_contextual_response(user_message, intent, extracted_info, insights, context)

        # Update memory with this interaction
        self.memory_system.update_memory(user_message, response, extracted_info)

        return response

    def determine_advanced_intent(self, message: str, extracted_info: Dict, insights: Dict, context: UserContext) -> str:
        """Advanced intent determination with context awareness"""
        message_lower = message.lower()

        # Check for explicit complaint registration
        if any(phrase in message_lower for phrase in [
            "register complaint", "file complaint", "submit complaint",
            "i have a complaint", "i want to complain", "register a complaint for me",
            "i have some issues", "i have a problem"
        ]):
            return "register_complaint"

        # Check for status inquiries
        if any(phrase in message_lower for phrase in [
            "status", "check my complaint", "what's the update", "any progress",
            "what happened to my complaint", "status of my complaint"
        ]) or extracted_info.get("complaint_id"):
            return "check_status"

        # Context-aware intent detection for registration continuation
        if insights["current_intent"] == "register_complaint" and context.current_step in ["collecting_name", "collecting_mobile", "collecting_details"]:
            return "continue_registration"

        # Check for greetings
        if any(phrase in message_lower for phrase in [
            "hello", "hi", "hey", "good morning", "good afternoon", "good evening"
        ]):
            return "greeting"

        # Check for help requests
        if any(phrase in message_lower for phrase in [
            "help", "how does this work", "guide", "instructions", "what can you do"
        ]):
            return "get_help"

        # Check for thanks/goodbye
        if any(phrase in message_lower for phrase in [
            "thank", "thanks", "bye", "goodbye", "that's all"
        ]):
            return "closing"

        return "general_inquiry"

    def generate_contextual_response(self, message: str, intent: str, extracted_info: Dict, insights: Dict, context: UserContext) -> str:
        """Generate contextual response based on intent and conversation history"""

        # Get user's name for personalization
        user_name = insights["user_profile"]["name"]

        # Adjust tone based on sentiment
        sentiment = insights["dominant_sentiment"]

        # Route to specific handlers based on intent
        if intent == "register_complaint":
            return self.handle_complaint_registration_with_context(message, context, extracted_info, insights)
        elif intent == "check_status":
            return self.handle_status_inquiry_with_context(message, context, extracted_info, insights)
        elif intent == "continue_registration":
            return handle_smart_registration(message, context, extracted_info)
        elif intent == "greeting":
            return self.handle_greeting_with_context(message, context, extracted_info, insights)
        elif intent == "get_help":
            return self.handle_help_with_context(message, context, extracted_info, insights)
        elif intent == "closing":
            return self.handle_closing_with_context(message, context, extracted_info, insights)
        else:
            return self.handle_general_inquiry_with_context(message, context, extracted_info, insights)

    def handle_complaint_registration_with_context(self, message: str, context: UserContext, extracted_info: Dict, insights: Dict) -> str:
        """Handle complaint registration with context awareness"""
        user_name = insights["user_profile"]["name"]
        sentiment = insights["dominant_sentiment"]

        # Personalized greeting
        if user_name:
            greeting = f"Hello {user_name}! "
        else:
            greeting = "Hello! "

        # Adjust response based on sentiment
        if sentiment == "negative" or sentiment == "urgent":
            tone = "I understand this is frustrating, and I'm here to help resolve this quickly. "
        else:
            tone = "I'm here to help you with your complaint. "

        # Check if user provided comprehensive information
        if extracted_info.get("name") and extracted_info.get("mobile") and len(message) > 50:
            return greeting + tone + "I can see you've provided comprehensive information. Let me process your complaint registration right away.\n\n" + handle_smart_registration(message, context, extracted_info)
        else:
            return greeting + tone + handle_smart_registration(message, context, extracted_info)

    def handle_status_inquiry_with_context(self, message: str, context: UserContext, extracted_info: Dict, insights: Dict) -> str:
        """Handle status inquiries with context awareness"""
        user_name = insights["user_profile"]["name"]

        if user_name:
            greeting = f"{user_name}, "
        else:
            greeting = ""

        if extracted_info.get("complaint_id"):
            return greeting + "I'll check the status of your complaint right away.\n\n" + handle_smart_status_check(message, context, extracted_info, "check_status")
        elif insights["user_profile"]["mobile"]:
            return greeting + "Let me check all complaints associated with your registered mobile number.\n\n" + handle_smart_status_check(message, context, {"mobile": insights["user_profile"]["mobile"]}, "check_status")
        else:
            return greeting + "I'd be happy to check your complaint status. " + handle_smart_status_check(message, context, extracted_info, "check_status")

    def handle_greeting_with_context(self, message: str, context: UserContext, extracted_info: Dict, insights: Dict) -> str:
        """Handle greetings with context awareness"""
        return get_contextual_response(message, context)

    def handle_help_with_context(self, message: str, context: UserContext, extracted_info: Dict, insights: Dict) -> str:
        """Handle help requests with context awareness"""
        conversation_length = insights["conversation_length"]

        if conversation_length > 3:
            return get_contextual_response(message, context)
        else:
            return get_general_response(message, context)

    def handle_closing_with_context(self, message: str, context: UserContext, extracted_info: Dict, insights: Dict) -> str:
        """Handle closing/thanks with context awareness"""
        return get_contextual_response(message, context)

    def handle_general_inquiry_with_context(self, message: str, context: UserContext, extracted_info: Dict, insights: Dict) -> str:
        """Handle general inquiries with context awareness"""
        return get_contextual_response(message, context)

# Initialize the enhanced intent-based response system (moved to main function)
enhanced_intent_system = None

def extract_basic_info(user_message: str) -> Dict[str, Any]:
    """Extract basic information from user message"""
    import re
    extracted = {}

    # Extract mobile number
    mobile_patterns = [
        r'(\+?\d{10,15})',  # Simple pattern for 10-15 digits
        r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})',  # US format
    ]

    for pattern in mobile_patterns:
        mobile_matches = re.findall(pattern, user_message)
        for mobile_match in mobile_matches:
            mobile = re.sub(r'[-.\s]', '', mobile_match)
            if 10 <= len(mobile) <= 15 and mobile.isdigit():
                extracted['mobile'] = mobile
                break
        if 'mobile' in extracted:
            break

    # Extract complaint ID
    complaint_id_match = re.search(r'\b(CMP[A-Z0-9]{8,10})\b', user_message, re.IGNORECASE)
    if complaint_id_match:
        extracted['complaint_id'] = complaint_id_match.group(1).upper()

    # Extract name (simple pattern)
    if len(user_message.split()) <= 3 and re.match(r'^[a-zA-Z\s]{2,40}$', user_message.strip()):
        words = user_message.strip().split()
        if all(len(word) >= 2 and word.isalpha() for word in words):
            non_names = {'yes', 'no', 'ok', 'okay', 'help', 'hi', 'hello', 'what', 'how'}
            if user_message.lower().strip() not in non_names:
                extracted['name'] = ' '.join(word.capitalize() for word in words)

    return extracted

def detect_simple_intent(user_message: str, context: UserContext) -> str:
    """Simple intent detection"""
    message_lower = user_message.lower()

    # If we're in the middle of registration, continue it
    if context.current_step in ["collecting_name", "collecting_mobile", "collecting_details"]:
        return "continue_registration"

    # Check for complaint registration
    if any(phrase in message_lower for phrase in [
        "register complaint", "file complaint", "new complaint", "i have a complaint",
        "i want to complain", "complaint", "issue", "problem"
    ]):
        return "register_complaint"

    # Check for status check
    if any(phrase in message_lower for phrase in [
        "status", "check", "update", "cmp"
    ]):
        return "check_status"

    return "general"

def handle_simple_registration(user_message: str, context: UserContext, extracted_info: Dict) -> str:
    """Simple registration handler"""

    # Update context with extracted info
    if extracted_info.get('name') and not context.name:
        context.name = extracted_info['name']
    if extracted_info.get('mobile') and not context.mobile:
        context.mobile = extracted_info['mobile']

    # Step 1: Get name
    if not context.name:
        if context.current_step == "initial":
            context.current_step = "collecting_name"
            return """📝 **Complaint Registration**

I'll help you register your complaint. Let's start with your details.

**Please provide your full name:**"""
        elif context.current_step == "collecting_name":
            name = user_message.strip()
            print(f"DEBUG: Validating name: '{name}'")  # Debug line
            if validate_name(name):
                context.name = name
                context.current_step = "collecting_mobile"
                print(f"DEBUG: Name accepted: '{name}', step: {context.current_step}")  # Debug line
                return f"""✅ Thank you, **{name}**!

**Please provide your mobile number:**"""
            else:
                print(f"DEBUG: Name rejected: '{name}'")  # Debug line
                return f"""❌ Please provide a valid name.

**Examples of valid names:**
• John Doe
• Sarah Smith
• Mary Johnson

**Please enter your full name:**"""

    # Step 2: Get mobile
    elif not context.mobile:
        if context.current_step == "collecting_mobile":
            mobile = user_message.strip()
            if validate_mobile(mobile):
                context.mobile = mobile
                context.current_step = "collecting_details"
                return f"""✅ Mobile number **{mobile}** recorded!

**Please describe your complaint in detail:**"""
            else:
                return """❌ Please provide a valid mobile number (10-15 digits).

**Please enter your mobile number:**"""

    # Step 3: Get complaint details
    elif not context.complaint_details:
        if context.current_step == "collecting_details":
            if len(user_message.strip()) < 10:
                return """❌ Please provide more detailed information (minimum 10 characters).

**Please describe your complaint in detail:**"""

            context.complaint_details = user_message.strip()
            return process_final_registration(context)

    # If we have all info, process registration
    if context.name and context.mobile and context.complaint_details:
        return process_final_registration(context)

    # Start registration process
    context.current_step = "collecting_name"
    return """📝 **Complaint Registration**

I'll help you register your complaint. Let's start with your details.

**Please provide your full name:**"""

def process_final_registration(context: UserContext) -> str:
    """Process the final registration"""
    result = register_complaint_api(
        context.name,
        context.mobile,
        context.complaint_details,
        "Other"  # Default category
    )

    if result["success"]:
        complaint_data = result["data"]
        complaint_id = complaint_data["complaint_id"]

        # Reset context
        st.session_state.user_context = UserContext()

        return f"""🎉 **Complaint Registered Successfully!**

**🆔 Complaint ID:** `{complaint_id}`
**👤 Name:** {context.name}
**📱 Mobile:** {context.mobile}
**📊 Status:** {complaint_data['status']}

**📝 Complaint Details:**
{context.complaint_details}

**📌 Important:** Save your Complaint ID `{complaint_id}` for future reference.

**🔍 To check status:** Say "Check status {complaint_id}" or provide your mobile number.

Is there anything else I can help you with?"""
    else:
        st.session_state.user_context = UserContext()
        return f"""❌ **Registration Failed**

Error: {result['error']}

Please try again by saying "I want to register a complaint"."""

def handle_simple_status_check(user_message: str, context: UserContext, extracted_info: Dict) -> str:
    """Simple status check handler"""

    # Check by complaint ID
    if extracted_info.get('complaint_id'):
        complaint_id = extracted_info['complaint_id']
        result = get_complaint_status_api(complaint_id)

        if result["success"]:
            complaint_data = result["data"]
            return f"""📋 **Complaint Status**

**🆔 Complaint ID:** `{complaint_data['complaint_id']}`
**📊 Status:** **{complaint_data['status']}**
**👤 Name:** {complaint_data['name']}
**📱 Mobile:** {complaint_data['mobile']}
**📅 Registered:** {complaint_data['created_at'][:10]}

**📝 Complaint Details:**
{complaint_data['complaint_details']}

Is there anything else I can help you with?"""
        else:
            return f"""❌ **Complaint Not Found**

Complaint ID `{complaint_id}` was not found in our system.

Please check the ID and try again, or provide your mobile number to see all your complaints."""

    # Check by mobile number
    elif extracted_info.get('mobile'):
        mobile = extracted_info['mobile']
        result = get_user_complaints_api(mobile)

        if result["success"]:
            complaints = result["data"]
            if complaints:
                if len(complaints) == 1:
                    complaint_data = complaints[0]
                    return f"""📋 **Your Complaint**

**🆔 Complaint ID:** `{complaint_data['complaint_id']}`
**📊 Status:** **{complaint_data['status']}**
**📅 Registered:** {complaint_data['created_at'][:10]}

**📝 Complaint Details:**
{complaint_data['complaint_details']}

Is there anything else I can help you with?"""
                else:
                    response = f"""📱 **Your Complaints ({len(complaints)} found)**

"""
                    for i, complaint in enumerate(complaints[:5], 1):
                        response += f"""**{i}. {complaint['complaint_id']}**
   Status: {complaint['status']}
   Date: {complaint['created_at'][:10]}

"""
                    response += "Say 'Check status [ID]' for detailed information about any complaint."
                    return response
            else:
                return f"""📱 **No Complaints Found**

No complaints found for mobile number {mobile}.

Would you like to register a new complaint?"""
        else:
            return f"""❌ **Search Failed**

Could not search for complaints with mobile number {mobile}.

Please try again or contact support."""

    # Ask for mobile number or complaint ID
    return """🔍 **Status Check**

To check your complaint status, please provide:
• Your **Complaint ID** (e.g., CMP12345678), or
• Your **mobile number** to see all your complaints

**Please provide your mobile number:**"""

def handle_general_response(user_message: str, context: UserContext, extracted_info: Dict) -> str:
    """Handle general responses"""
    message_lower = user_message.lower()

    # Greetings
    if any(word in message_lower for word in ["hello", "hi", "hey", "good morning", "good afternoon"]):
        return """👋 **Hello! Welcome to the Grievance Management System**

I'm here to help you with:
• **Register new complaints** - Say "I have a complaint"
• **Check complaint status** - Provide your Complaint ID or mobile number
• **Get help and support** - Ask me anything

How can I assist you today?"""

    # Help requests
    if any(word in message_lower for word in ["help", "how", "what", "guide"]):
        return """💡 **How to Use This System**

**To Register a Complaint:**
1. Say "I have a complaint" or "Register complaint"
2. Provide your name when asked
3. Provide your mobile number
4. Describe your issue in detail

**To Check Status:**
1. Say "Check status" and provide your Complaint ID
2. Or provide your mobile number to see all complaints

**Sample Commands:**
• "I want to register a complaint"
• "Check status CMP12345678"
• "What's my complaint status?"

What would you like to do?"""

    # Thanks/goodbye
    if any(word in message_lower for word in ["thank", "thanks", "bye", "goodbye"]):
        return """🙏 **Thank you for using our Grievance Management System!**

We're committed to resolving your issues promptly. If you need any further assistance, feel free to ask.

Have a great day! 😊"""

    # Default response
    return """🤔 I'm not sure I understood that.

**I can help you with:**
• **Register a complaint** - Say "I have a complaint"
• **Check complaint status** - Provide your Complaint ID or mobile number
• **Get help** - Say "help" for guidance

What would you like to do?"""

def process_user_message(user_message: str) -> str:
    """Process user message with intelligent natural language understanding"""
    context = st.session_state.user_context
    message = user_message.strip()

    # Debug info
    print(f"DEBUG: Processing message: '{message}'")
    print(f"DEBUG: Current step: {context.current_step}")
    print(f"DEBUG: Has name: {bool(context.name)}")
    print(f"DEBUG: Has mobile: {bool(context.mobile)}")

    # If we're in registration flow, handle step by step
    if context.current_step in ["collecting_name", "collecting_mobile", "collecting_details"]:
        return handle_registration_step(message, context)

    # Use intelligent question handler for all other cases
    return handle_intelligent_question(message, context)

def extract_user_info(message: str) -> Dict[str, Any]:
    """Extract user information from natural language"""
    import re
    info = {}
    message_lower = message.lower()

    # Extract names with various patterns
    name_patterns = [
        r"(?:my\s+name\s+is|i\s+am|i'm|myself)\s+([a-zA-Z][a-zA-Z\s]{1,40})",
        r"(?:my\s+self|myself)\s+([a-zA-Z][a-zA-Z\s]{1,40})",
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s+(?:give|show|get)",
        r"name\s*[:=]\s*([a-zA-Z][a-zA-Z\s]{1,40})",
    ]

    for pattern in name_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if len(name) >= 2:
                info['name'] = name
                break

    # Extract mobile numbers
    mobile_patterns = [
        r'(\+?\d{10,15})',
        r'mobile\s*[:=]\s*(\+?\d{10,15})',
        r'phone\s*[:=]\s*(\+?\d{10,15})',
        r'number\s*[:=]\s*(\+?\d{10,15})',
    ]

    for pattern in mobile_patterns:
        matches = re.findall(pattern, message)
        for match in matches:
            mobile = re.sub(r'[^\d]', '', match)
            if 10 <= len(mobile) <= 15:
                info['mobile'] = mobile
                break
        if 'mobile' in info:
            break

    # Extract complaint IDs
    complaint_id_match = re.search(r'\b(CMP[A-Z0-9]{8,10})\b', message, re.IGNORECASE)
    if complaint_id_match:
        info['complaint_id'] = complaint_id_match.group(1).upper()

    return info

def detect_user_intent(message: str, extracted_info: Dict) -> str:
    """Detect user intent from natural language"""
    message_lower = message.lower()

    # Registration intents
    registration_keywords = [
        "register", "file", "submit", "new complaint", "have a complaint",
        "want to complain", "issue", "problem", "facing", "trouble"
    ]
    if any(keyword in message_lower for keyword in registration_keywords):
        return "register_complaint"

    # Status check intents
    status_keywords = [
        "status", "check", "update", "progress", "what happened",
        "any news", "follow up", "track", "see my", "show my",
        "give all record", "all complaint", "my complaints"
    ]
    if any(keyword in message_lower for keyword in status_keywords):
        return "check_status"

    # Record retrieval intents
    record_keywords = [
        "all record", "all complaint", "show all", "give all",
        "my complaints", "my records", "list all", "see all"
    ]
    if any(keyword in message_lower for keyword in record_keywords):
        return "get_all_records"

    # Help intents
    help_keywords = ["help", "how", "what can", "guide", "instructions"]
    if any(keyword in message_lower for keyword in help_keywords):
        return "get_help"

    # Greeting intents
    greeting_keywords = ["hello", "hi", "hey", "good morning", "good afternoon"]
    if any(keyword in message_lower for keyword in greeting_keywords):
        return "greeting"

    # If mobile number or complaint ID provided, assume status check
    if extracted_info.get('mobile') or extracted_info.get('complaint_id'):
        return "check_status"

    return "general"

def handle_intelligent_question(message: str, context: UserContext) -> str:
    """Handle user questions with intelligent understanding"""

    # Extract information from the message
    extracted_info = extract_user_info(message)

    # Detect user intent
    intent = detect_user_intent(message, extracted_info)

    print(f"DEBUG: Intent detected: {intent}")
    print(f"DEBUG: Extracted info: {extracted_info}")

    # Route to appropriate handler based on intent
    if intent == "register_complaint":
        return handle_complaint_registration_intent(message, context, extracted_info)
    elif intent == "check_status":
        return handle_status_check_intent(message, context, extracted_info)
    elif intent == "get_all_records":
        return handle_get_all_records_intent(message, context, extracted_info)
    elif intent == "get_help":
        return handle_help_intent(message, context, extracted_info)
    elif intent == "greeting":
        return handle_greeting_intent(message, context, extracted_info)
    else:
        return handle_general_intent(message, context, extracted_info)

def handle_complaint_registration_intent(message: str, context: UserContext, extracted_info: Dict) -> str:
    """Handle complaint registration with extracted information"""

    # If user provided name and wants to register, start with that info
    if extracted_info.get('name'):
        context.name = extracted_info['name']
        context.current_step = "collecting_mobile"
        return f"""📝 **Complaint Registration**

Hello **{context.name}**! I'll help you register your complaint.

**Please provide your mobile number:**"""
    else:
        context.current_step = "collecting_name"
        return """📝 **Complaint Registration**

I'll help you register your complaint. Let's start with your details.

**Please provide your full name:**"""

def handle_status_check_intent(message: str, context: UserContext, extracted_info: Dict) -> str:
    """Handle status check with intelligent understanding"""

    # If complaint ID provided, check directly
    if extracted_info.get('complaint_id'):
        return get_complaint_by_id(extracted_info['complaint_id'])

    # If mobile number provided, show all complaints
    elif extracted_info.get('mobile'):
        return get_complaints_by_mobile(extracted_info['mobile'])

    # If name provided, ask for mobile or ID
    elif extracted_info.get('name'):
        return f"""🔍 **Status Check for {extracted_info['name']}**

To retrieve your complaint records, I need either:
• Your **mobile number**, or
• Your **complaint ID** (e.g., CMP12345678)

**Please provide your mobile number or complaint ID:**"""

    # Ask for identification
    else:
        return """🔍 **Status Check**

To check your complaint status, please provide:
• Your **mobile number**, or
• Your **complaint ID** (e.g., CMP12345678)

**Please provide your mobile number or complaint ID:**"""

def handle_get_all_records_intent(message: str, context: UserContext, extracted_info: Dict) -> str:
    """Handle requests for all complaint records"""

    # If mobile provided, get all records for that mobile
    if extracted_info.get('mobile'):
        return get_all_complaints_by_mobile(extracted_info['mobile'])

    # If name provided, ask for mobile
    elif extracted_info.get('name'):
        return f"""📋 **All Records for {extracted_info['name']}**

To retrieve all your complaint records, I need your mobile number.

**Please provide your mobile number:**"""

    # Ask for mobile number
    else:
        return """📋 **All Complaint Records**

To show all your complaint records, I need your mobile number.

**Please provide your mobile number:**"""

def handle_help_intent(message: str, context: UserContext, extracted_info: Dict) -> str:
    """Handle help requests"""
    return """💡 **Grievance Management System - Help Guide**

**🔹 Register a New Complaint:**
• Say: "I have a complaint" or "Register complaint"
• Provide: Name → Mobile → Complaint details
• Example: "My name is John, register a complaint"

**🔹 Check Complaint Status:**
• Say: "Check status CMP12345678" (with your complaint ID)
• Say: "Check status" and provide mobile number
• Example: "What's the status of my complaint?"

**🔹 Get All Your Records:**
• Say: "Show all my complaints"
• Say: "Give all records on my name"
• Example: "My self John, give all complaint records"

**🔹 Natural Language Examples:**
• "My name is Sarah, I have a laptop issue"
• "Check status for mobile 9876543210"
• "John here, show all my complaints"
• "What's the update on CMP12345678?"

**🔹 Quick Actions:**
• Just type your mobile number to see all complaints
• Type complaint ID to check specific status
• Say "help" anytime for guidance

How can I assist you today?"""

def handle_greeting_intent(message: str, context: UserContext, extracted_info: Dict) -> str:
    """Handle greetings with personalization"""

    name_part = ""
    if extracted_info.get('name'):
        name_part = f" {extracted_info['name']}!"

    return f"""👋 **Hello{name_part} Welcome to Grievance Management System**

I'm your AI assistant for complaint management. I can understand natural language!

**🔹 What I can help you with:**
• **Register complaints** - "I have an issue with my laptop"
• **Check status** - "What's the status of my complaint?"
• **Get all records** - "Show all my complaints"
• **Natural conversation** - Just tell me what you need!

**🔹 Smart Examples:**
• "My name is John, register a complaint"
• "Check status for mobile 9876543210"
• "Give all records on my name"

How can I assist you today?"""

def handle_general_intent(message: str, context: UserContext, extracted_info: Dict) -> str:
    """Handle general queries with intelligence"""

    # Check if it's a mobile number
    if message.isdigit() and len(message) >= 10:
        return handle_mobile_input(message, context)

    # Check if it contains a complaint ID
    if extracted_info.get('complaint_id'):
        return get_complaint_by_id(extracted_info['complaint_id'])

    # If name provided but unclear intent
    if extracted_info.get('name'):
        return f"""👋 **Hello {extracted_info['name']}!**

I understand you mentioned your name. How can I help you today?

**🔹 I can help you:**
• **Register a new complaint** - Say "I have a complaint"
• **Check complaint status** - Provide your mobile number or complaint ID
• **Get all your records** - Say "show all my complaints"

What would you like to do?"""

    # Default intelligent response
    return """🤔 **I'm here to help!**

I can understand natural language. Try saying:

**🔹 For new complaints:**
• "I have a complaint about my laptop"
• "My name is John, register a complaint"

**🔹 For status checks:**
• "Check my complaint status"
• "What's the update on CMP12345678?"
• Just type your mobile number

**🔹 For all records:**
• "Show all my complaints"
• "Give all records on my name"

What would you like to do?"""

def get_complaint_by_id(complaint_id: str) -> str:
    """Get complaint details by ID"""
    result = get_complaint_status_api(complaint_id)

    if result["success"]:
        complaint_data = result["data"]
        return f"""📋 **Complaint Details**

**🆔 Complaint ID:** `{complaint_data['complaint_id']}`
**📊 Status:** **{complaint_data['status']}**
**👤 Name:** {complaint_data['name']}
**📱 Mobile:** {complaint_data['mobile']}
**🏷️ Category:** {complaint_data['category']}
**📅 Registered:** {complaint_data['created_at'][:10]}
**🔄 Last Updated:** {complaint_data['updated_at'][:10]}

**📝 Complaint Details:**
{complaint_data['complaint_details']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**💡 Quick Actions:**
• Say "Update me on this complaint" for latest status
• Say "Register new complaint" for additional issues
• Type your mobile number to see all complaints

Is there anything else I can help you with?"""
    else:
        return f"""❌ **Complaint Not Found**

**Complaint ID:** `{complaint_id}`
**Error:** {result['error']}

**🔍 Please verify:**
• Complaint ID format: CMP12345678
• Check for typos in the ID
• Ensure the complaint was registered in this system

**💡 Alternative options:**
• Provide your mobile number to see all complaints
• Say "Register new complaint" to file a new issue
• Say "help" for more assistance"""

def get_complaints_by_mobile(mobile: str) -> str:
    """Get all complaints by mobile number"""
    result = get_user_complaints_api(mobile)

    if result["success"]:
        complaints = result["data"]
        if complaints:
            if len(complaints) == 1:
                complaint = complaints[0]
                return f"""📱 **Your Complaint Record**

**📞 Mobile:** {mobile}
**📊 Total Complaints:** 1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**🆔 Complaint ID:** `{complaint['complaint_id']}`
**📊 Status:** **{complaint['status']}**
**🏷️ Category:** {complaint['category']}
**📅 Registered:** {complaint['created_at'][:10]}

**📝 Details:** {complaint['complaint_details']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**💡 Quick Actions:**
• Say "Check status {complaint['complaint_id']}" for detailed info
• Say "Register new complaint" for additional issues

Is there anything else I can help you with?"""
            else:
                return get_all_complaints_by_mobile(mobile)
        else:
            return f"""📱 **No Complaints Found**

**📞 Mobile Number:** {mobile}
**📊 Total Complaints:** 0

No complaints found for this mobile number.

**💡 Would you like to:**
• **Register a new complaint** - Say "I have a complaint"
• **Try different mobile number** - Provide another number
• **Get help** - Say "help" for assistance

How can I help you today?"""
    else:
        return f"""❌ **Search Failed**

**📞 Mobile Number:** {mobile}
**Error:** {result['error']}

Could not search for complaints. Please try again or contact support.

**💡 You can also:**
• Try again with the same mobile number
• Provide a complaint ID instead
• Say "help" for assistance"""

def get_all_complaints_by_mobile(mobile: str) -> str:
    """Get formatted list of all complaints by mobile"""
    result = get_user_complaints_api(mobile)

    if result["success"]:
        complaints = result["data"]
        if complaints:
            response = f"""📱 **All Your Complaint Records**

**📞 Mobile Number:** {mobile}
**📊 Total Complaints:** {len(complaints)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📋 COMPLAINT SUMMARY**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""

            status_emojis = {
                "Registered": "📝",
                "In Progress": "⚙️",
                "Under Review": "🔍",
                "Resolved": "✅",
                "Closed": "📁",
                "Rejected": "❌"
            }

            for i, complaint in enumerate(complaints[:10], 1):  # Show up to 10
                status_emoji = status_emojis.get(complaint['status'], "📊")
                response += f"""**{i}. {complaint['complaint_id']}** {status_emoji}
   **Status:** {complaint['status']}
   **Category:** {complaint['category']}
   **Date:** {complaint['created_at'][:10]}
   **Details:** {complaint['complaint_details'][:80]}{'...' if len(complaint['complaint_details']) > 80 else ''}

"""

            if len(complaints) > 10:
                response += f"... and {len(complaints) - 10} more complaints\n\n"

            response += """━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**💡 Quick Actions:**
• Say "Check status [ID]" for detailed information
• Say "Register new complaint" for additional issues
• Say "Show only pending complaints" to filter

Is there anything else I can help you with?"""

            return response
        else:
            return f"""📱 **No Complaints Found**

**📞 Mobile Number:** {mobile}

No complaints found for this mobile number.

**💡 Would you like to register a new complaint?**"""
    else:
        return f"""❌ **Search Failed**

Could not retrieve complaints for mobile number {mobile}.
Please try again or contact support."""

def handle_registration_step(message: str, context: UserContext) -> str:
    """Handle each step of registration"""

    if context.current_step == "collecting_name":
        # Accept almost any input as name
        if len(message) >= 2:
            context.name = message
            context.current_step = "collecting_mobile"
            return f"""✅ Thank you, **{message}**!

**Please provide your mobile number:**"""
        else:
            return """❌ Please provide a name (at least 2 characters).

**Please enter your full name:**"""

    elif context.current_step == "collecting_mobile":
        # Clean and validate mobile number
        mobile = ''.join(filter(str.isdigit, message))
        if len(mobile) >= 10:
            context.mobile = mobile
            context.current_step = "collecting_details"
            return f"""✅ Mobile number **{mobile}** recorded!

**Please describe your complaint in detail:**"""
        else:
            return """❌ Please provide a valid mobile number (at least 10 digits).

**Please enter your mobile number:**"""

    elif context.current_step == "collecting_details":
        if len(message) >= 10:
            context.complaint_details = message
            return register_final_complaint(context)
        else:
            return """❌ Please provide more detailed information (at least 10 characters).

**Please describe your complaint in detail:**"""

    return "Please provide the requested information."

def handle_mobile_input(message: str, context: UserContext) -> str:
    """Handle when user provides a mobile number"""
    mobile = ''.join(filter(str.isdigit, message))

    # Search for complaints by mobile number
    result = get_user_complaints_api(mobile)

    if result["success"]:
        complaints = result["data"]
        if complaints:
            if len(complaints) == 1:
                complaint = complaints[0]
                return f"""📋 **Your Complaint**

**🆔 Complaint ID:** `{complaint['complaint_id']}`
**📊 Status:** **{complaint['status']}**
**📅 Registered:** {complaint['created_at'][:10]}

**📝 Details:** {complaint['complaint_details']}

Is there anything else I can help you with?"""
            else:
                response = f"""📱 **Your Complaints ({len(complaints)} found)**

"""
                for i, complaint in enumerate(complaints[:5], 1):
                    response += f"""**{i}. {complaint['complaint_id']}**
   Status: {complaint['status']}
   Date: {complaint['created_at'][:10]}

"""
                return response + "Say 'Check status [ID]' for detailed information."
        else:
            return f"""📱 **No Complaints Found**

No complaints found for mobile number {mobile}.

Would you like to register a new complaint? Say "I have a complaint"."""
    else:
        return f"""❌ **Search Failed**

Could not search for complaints. Please try again or contact support."""

def register_final_complaint(context: UserContext) -> str:
    """Register the complaint with all collected information"""
    result = register_complaint_api(
        context.name,
        context.mobile,
        context.complaint_details,
        "Other"
    )

    if result["success"]:
        complaint_data = result["data"]
        complaint_id = complaint_data["complaint_id"]

        # Reset context
        st.session_state.user_context = UserContext()

        return f"""🎉 **Complaint Registered Successfully!**

**🆔 Complaint ID:** `{complaint_id}`
**👤 Name:** {context.name}
**📱 Mobile:** {context.mobile}
**📊 Status:** {complaint_data['status']}

**📝 Complaint Details:**
{context.complaint_details}

**📌 Important:** Save your Complaint ID `{complaint_id}` for future reference.

Is there anything else I can help you with?"""
    else:
        # Reset context on error
        st.session_state.user_context = UserContext()
        return f"""❌ **Registration Failed**

Error: {result['error']}

Please try again by saying "I want to register a complaint"."""

def handle_status_check_simple(message: str, context: UserContext) -> str:
    """Handle status check requests"""

    # Look for complaint ID in message
    import re
    complaint_id_match = re.search(r'\b(CMP[A-Z0-9]{8,10})\b', message, re.IGNORECASE)

    if complaint_id_match:
        complaint_id = complaint_id_match.group(1).upper()
        result = get_complaint_status_api(complaint_id)

        if result["success"]:
            complaint_data = result["data"]
            return f"""📋 **Complaint Status**

**🆔 Complaint ID:** `{complaint_data['complaint_id']}`
**📊 Status:** **{complaint_data['status']}**
**👤 Name:** {complaint_data['name']}
**📱 Mobile:** {complaint_data['mobile']}
**📅 Registered:** {complaint_data['created_at'][:10]}

**📝 Details:** {complaint_data['complaint_details']}

Is there anything else I can help you with?"""
        else:
            return f"""❌ **Complaint Not Found**

Complaint ID `{complaint_id}` was not found.

Please check the ID or provide your mobile number."""

    # Ask for mobile number or complaint ID
    return """🔍 **Status Check**

To check your complaint status, please provide:
• Your **Complaint ID** (e.g., CMP12345678), or
• Your **mobile number**

**Please provide your mobile number or Complaint ID:**"""

def handle_smart_registration(user_message: str, context: UserContext, extracted_info: Dict) -> str:
    """Smart complaint registration that can handle multiple details at once"""

    # Update context with any extracted information
    if extracted_info.get('name') and not context.name:
        context.name = extracted_info['name']
    if extracted_info.get('mobile') and not context.mobile:
        context.mobile = extracted_info['mobile']

    # Check if user provided complaint details in the message
    if not context.complaint_details and context.current_step in ["initial", "collecting_details"]:
        # Look for complaint details in the message
        complaint_indicators = [
            "issue with", "problem with", "not working", "broken", "error", "bug",
            "complaint about", "issue is", "problem is", "facing", "having trouble"
        ]

        message_lower = user_message.lower()
        for indicator in complaint_indicators:
            if indicator in message_lower:
                # Extract the part after the indicator as complaint details
                parts = message_lower.split(indicator, 1)
                if len(parts) > 1 and len(parts[1].strip()) > 10:
                    context.complaint_details = user_message.strip()
                    break

        # If message is long enough and seems like a complaint description
        if not context.complaint_details and len(user_message.strip()) > 20:
            # Check if it contains technical terms or complaint-like content
            complaint_words = [
                "laptop", "computer", "screen", "keyboard", "mouse", "software", "application",
                "internet", "network", "wifi", "slow", "crash", "freeze", "hang",
                "login", "password", "account", "access", "bill", "charge", "payment"
            ]
            if any(word in message_lower for word in complaint_words):
                context.complaint_details = user_message.strip()

    # Smart flow based on what information we have
    missing_info = []
    if not context.name:
        missing_info.append("name")
    if not context.mobile:
        missing_info.append("mobile number")
    if not context.complaint_details:
        missing_info.append("complaint details")

    # If we have all information, proceed with registration
    if not missing_info:
        return process_complaint_registration(context)

    # If this is the initial request, show what we detected and ask for missing info
    if context.current_step == "initial":
        context.current_step = "collecting_info"

        detected_info = []
        if context.name:
            detected_info.append(f"**Name:** {context.name}")
        if context.mobile:
            detected_info.append(f"**Mobile:** {context.mobile}")
        if context.complaint_details:
            detected_info.append(f"**Issue:** {context.complaint_details[:100]}...")

        response = "📝 **Smart Complaint Registration**\n\n"

        if detected_info:
            response += "✅ **Information Detected:**\n"
            response += "\n".join(detected_info)
            response += "\n\n"

        if missing_info:
            response += "📋 **Missing Information:**\n"
            for i, info in enumerate(missing_info, 1):
                response += f"{i}. {info.title()}\n"
            response += f"\n**Please provide your {missing_info[0]}:**"

            # Set the current step to collect the first missing item
            if "name" in missing_info:
                context.current_step = "collecting_name"
            elif "mobile number" in missing_info:
                context.current_step = "collecting_mobile"
            else:
                context.current_step = "collecting_details"

        return response

    # Handle step-by-step collection
    return handle_step_by_step_collection(user_message, context, extracted_info)

def handle_step_by_step_collection(user_message: str, context: UserContext, extracted_info: Dict) -> str:
    """Handle step-by-step information collection"""

    if context.current_step == "collecting_name":
        name = extracted_info.get('name') or user_message.strip()
        if validate_name(name):
            context.name = name
            # Check what's still missing
            if not context.mobile:
                context.current_step = "collecting_mobile"
                return f"✅ Thank you, **{name}**!\n\n**Please provide your mobile number:**"
            elif not context.complaint_details:
                context.current_step = "collecting_details"
                return f"✅ Thank you, **{name}**!\n\n**Please describe your complaint in detail:**"
            else:
                return process_complaint_registration(context)
        else:
            return """❌ **Invalid Name Format**

Please provide a valid name:
• At least 2 characters
• Letters and spaces only
• Example: "John Doe" or "Sarah Smith"

**Please enter your full name:**"""

    elif context.current_step == "collecting_mobile":
        mobile = extracted_info.get('mobile') or user_message.strip()
        if validate_mobile(mobile):
            context.mobile = mobile
            if not context.complaint_details:
                context.current_step = "collecting_details"
                return f"✅ Mobile number **{mobile}** recorded!\n\n**Please describe your complaint in detail:**"
            else:
                return process_complaint_registration(context)
        else:
            return """❌ **Invalid Mobile Number Format**

Please provide a valid mobile number:
• 10-15 digits
• Can include country code (+1, +91, etc.)
• Examples: "+1234567890" or "9876543210"

**Please enter your mobile number:**"""

    elif context.current_step == "collecting_details":
        if len(user_message.strip()) < 10:
            return """❌ **Insufficient Details**

Please provide more detailed information about your complaint:
• Minimum 10 characters required
• Be specific about the issue
• Include relevant details like error messages, when it started, etc.

**Please describe your complaint in detail:**"""

        context.complaint_details = user_message.strip()
        return process_complaint_registration(context)

    return "Please provide the requested information."

def process_complaint_registration(context: UserContext) -> str:
    """Process the actual complaint registration"""
    context.current_step = "processing"

    # Use default category if LLM handler is not available
    if st.session_state.llm_handler:
        try:
            category = st.session_state.llm_handler.categorize_complaint(context.complaint_details)
            category_value = category.value
        except:
            category_value = "Other"
    else:
        category_value = "Other"

    result = register_complaint_api(
        context.name,
        context.mobile,
        context.complaint_details,
        category_value
    )

    if result["success"]:
        complaint_data = result["data"]
        complaint_id = complaint_data["complaint_id"]

        # Reset context for next interaction
        st.session_state.user_context = UserContext()

        return f"""🎉 **Complaint Registered Successfully!**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📋 COMPLAINT DETAILS**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**🆔 Complaint ID:** `{complaint_id}`
**👤 Name:** {context.name}
**📱 Mobile:** {context.mobile}
**📊 Status:** {complaint_data['status']}
**🏷️ Category:** {complaint_data['category']}
**📅 Registered:** {complaint_data['created_at'][:10]}

**📝 Complaint Details:**
{context.complaint_details}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**📌 IMPORTANT NOTES:**
• **Save your Complaint ID:** `{complaint_id}`
• **Expected Resolution:** 2-5 business days
• **Status Updates:** Check anytime with your Complaint ID
• **Reference Number:** Keep this for all future communications

**🔍 To Check Status:** Simply say "Check status {complaint_id}" or provide your mobile number

Thank you for using our Grievance Management System. We'll resolve your issue promptly!

Is there anything else I can help you with?"""
    else:
        # Reset context on error too
        st.session_state.user_context = UserContext()
        return f"""❌ **Registration Failed**

We encountered an error while registering your complaint:
**Error:** {result['error']}

**Please try again by saying:** "I want to register a complaint"

If the problem persists, please contact our support team."""

def handle_complaint_registration(user_message: str, context: UserContext, intent: str, extracted_info: Dict) -> str:
    """Handle complaint registration flow"""

    # Step 1: Collect name
    if not context.name:
        if context.current_step == "initial":
            context.current_step = "collecting_name"
            return """📝 **Complaint Registration Process**

I'll help you register your complaint. This process involves 3 simple steps:
1. Your full name
2. Your mobile number
3. Complaint details

Let's start - **Please provide your full name:**"""
        elif context.current_step == "collecting_name":
            name = user_message.strip()
            if validate_name(name):
                context.name = name
                context.current_step = "collecting_mobile"
                return f"""✅ Thank you, **{name}**!

**Step 2 of 3:** Please provide your mobile number (with country code if international):"""
            else:
                return """❌ **Invalid Name Format**

Please provide a valid name:
• At least 2 characters
• Letters and spaces only
• Example: "John Doe" or "Sarah Smith"

**Please enter your full name:**"""
    
    # Step 2: Collect mobile
    elif not context.mobile:
        if context.current_step == "collecting_mobile":
            mobile = user_message.strip()
            if validate_mobile(mobile):
                context.mobile = mobile
                context.current_step = "collecting_details"
                return f"""✅ Mobile number **{mobile}** recorded successfully!

**Step 3 of 3:** Please describe your complaint in detail:

• What is the issue you're facing?
• When did it start?
• Any error messages or specific problems?

**Please provide your complaint details:**"""
            else:
                return """❌ **Invalid Mobile Number Format**

Please provide a valid mobile number:
• 10-15 digits
• Can include country code (+1, +91, etc.)
• Examples: "+1234567890" or "9876543210"

**Please enter your mobile number:**"""
    
    # Step 3: Collect complaint details
    elif not context.complaint_details:
        if context.current_step == "collecting_details":
            if len(user_message.strip()) < 10:
                return """❌ **Insufficient Details**

Please provide more detailed information about your complaint:
• Minimum 10 characters required
• Be specific about the issue
• Include relevant details like error messages, when it started, etc.

**Please describe your complaint in detail:**"""

            context.complaint_details = user_message.strip()
            context.current_step = "processing"
            
            # Register complaint via API
            # Use default category if LLM handler is not available
            if st.session_state.llm_handler:
                try:
                    category = st.session_state.llm_handler.categorize_complaint(context.complaint_details)
                    category_value = category.value
                except:
                    category_value = "Other"
            else:
                category_value = "Other"

            result = register_complaint_api(
                context.name,
                context.mobile,
                context.complaint_details,
                category_value
            )
            
            if result["success"]:
                complaint_data = result["data"]
                complaint_id = complaint_data["complaint_id"]

                # Reset context for next interaction
                st.session_state.user_context = UserContext()

                return f"""🎉 **Complaint Registered Successfully!**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📋 COMPLAINT DETAILS**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**🆔 Complaint ID:** `{complaint_id}`
**👤 Name:** {context.name}
**📱 Mobile:** {context.mobile}
**📊 Status:** {complaint_data['status']}
**🏷️ Category:** {complaint_data['category']}
**📅 Registered:** {complaint_data['created_at'][:10]}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**📌 IMPORTANT NOTES:**
• **Save your Complaint ID:** `{complaint_id}`
• **Expected Resolution:** 2-5 business days
• **Status Updates:** Check anytime with your Complaint ID
• **Reference Number:** Keep this for all future communications

**🔍 To Check Status:** Simply say "Check status" and provide your Complaint ID

Thank you for using our Grievance Management System. We'll resolve your issue promptly!

Is there anything else I can help you with?"""
            else:
                # Reset context on error too
                st.session_state.user_context = UserContext()
                return f"""❌ **Registration Failed**

We encountered an error while registering your complaint:
**Error:** {result['error']}

**Please try again by saying:** "I want to register a complaint"

If the problem persists, please contact our support team."""
    
    return "I'm processing your request. Please wait..."

def get_detailed_complaint_info(complaint_data: Dict) -> str:
    """Generate detailed complaint information"""

    # Status-specific messages and emojis
    status_info = {
        "Registered": {
            "emoji": "📝",
            "message": "Your complaint has been received and is in our system",
            "next_step": "Our team will review it within 24 hours"
        },
        "In Progress": {
            "emoji": "⚙️",
            "message": "Our technical team is actively working on your complaint",
            "next_step": "You'll receive updates as we make progress"
        },
        "Under Review": {
            "emoji": "🔍",
            "message": "Your complaint is being reviewed by our specialists",
            "next_step": "We're analyzing the issue thoroughly"
        },
        "Resolved": {
            "emoji": "✅",
            "message": "Your complaint has been resolved successfully",
            "next_step": "Please verify if the issue is fixed"
        },
        "Closed": {
            "emoji": "📁",
            "message": "Your complaint has been closed",
            "next_step": "Contact us if you need further assistance"
        },
        "Rejected": {
            "emoji": "❌",
            "message": "Your complaint could not be processed",
            "next_step": "Please contact support for more details"
        }
    }

    status = complaint_data['status']
    status_detail = status_info.get(status, {
        "emoji": "📊",
        "message": "Status updated",
        "next_step": "Check back for updates"
    })

    # Calculate days since registration
    from datetime import datetime
    try:
        created_date = datetime.fromisoformat(complaint_data['created_at'][:19])
        days_ago = (datetime.now() - created_date).days
        time_info = f"{days_ago} day{'s' if days_ago != 1 else ''} ago"
    except:
        time_info = complaint_data['created_at'][:10]

    return f"""📋 **DETAILED COMPLAINT REPORT**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**🆔 Complaint ID:** `{complaint_data['complaint_id']}`
**📊 Current Status:** **{status}** {status_detail['emoji']}
**🏷️ Category:** {complaint_data['category']}
**👤 Name:** {complaint_data['name']}
**📱 Mobile:** {complaint_data['mobile']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**📅 Timeline:**
• **Registered:** {complaint_data['created_at'][:10]} ({time_info})
• **Last Updated:** {complaint_data['updated_at'][:10]}

**📝 Complaint Details:**
{complaint_data['complaint_details']}

**ℹ️ Status Information:**
{status_detail['message']}

**🔄 Next Steps:**
{status_detail['next_step']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**💡 Quick Actions:**
• Say "Update me on {complaint_data['complaint_id']}" for latest status
• Say "Register new complaint" for additional issues
• Say "Help" for more assistance options"""

def handle_smart_status_check(user_message: str, context: UserContext, extracted_info: Dict, intent: str) -> str:
    """Smart status checking with automatic detail extraction"""

    # Direct complaint ID check
    if extracted_info.get('complaint_id'):
        complaint_id = extracted_info['complaint_id']
        result = get_complaint_status_api(complaint_id)

        if result["success"]:
            complaint_data = result["data"]
            return get_detailed_complaint_info(complaint_data)
        else:
            return f"""❌ **Complaint Not Found**

**Complaint ID:** {complaint_id}
**Error:** {result['error']}

**Please verify:**
• Complaint ID format: CMP12345678
• Check for typos in the ID
• Ensure the complaint was registered in this system

**Need help?** Say "help" for assistance or try registering a new complaint."""

    # Mobile number check
    elif extracted_info.get('mobile'):
        mobile = extracted_info['mobile']
        result = get_user_complaints_api(mobile)

        if result["success"]:
            complaints = result["data"]
            if complaints:
                if len(complaints) == 1:
                    # If only one complaint, show detailed info
                    return get_detailed_complaint_info(complaints[0])
                else:
                    # Multiple complaints - show summary with option to get details
                    response = f"""📱 **COMPLAINTS SUMMARY**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📞 Mobile Number:** {mobile}
**📊 Total Complaints:** {len(complaints)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**📋 Your Complaints:**
"""
                    for i, complaint in enumerate(complaints[:10], 1):  # Show up to 10
                        status_emoji = {
                            "Registered": "📝", "In Progress": "⚙️", "Under Review": "🔍",
                            "Resolved": "✅", "Closed": "📁", "Rejected": "❌"
                        }.get(complaint['status'], "📊")

                        response += f"""
**{i}.** `{complaint['complaint_id']}` {status_emoji}
   **Status:** {complaint['status']}
   **Date:** {complaint['created_at'][:10]}
   **Category:** {complaint['category']}
   **Issue:** {complaint['complaint_details'][:60]}..."""

                    response += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**🔍 For detailed information:**
Say "Details of [Complaint ID]" (e.g., "Details of {complaints[0]['complaint_id']}")

**📝 To register new complaint:** Say "I have a complaint"

Which complaint would you like to know more about?"""
                    return response
            else:
                return f"""📱 **No Complaints Found**

**Mobile Number:** {mobile}

**This could mean:**
• No complaints registered with this number
• Different mobile number was used during registration
• Typo in the mobile number

**Would you like to:**
• Register a new complaint?
• Try a different mobile number?
• Check with a Complaint ID instead?

**Example:** Say "I have an issue with my laptop" to register a new complaint."""
        else:
            return f"""❌ **Error Fetching Complaints**

**Error:** {result['error']}

**Please try:**
• Check your mobile number format
• Ensure you're using the registered number
• Contact support if the issue persists"""

    # Look for complaint ID or mobile in the message text
    else:
        # Try to find complaint ID in the message
        complaint_id_match = re.search(r'CMP[A-Z0-9]{8}', user_message.upper())
        if complaint_id_match:
            complaint_id = complaint_id_match.group()
            result = get_complaint_status_api(complaint_id)

            if result["success"]:
                return get_detailed_complaint_info(result["data"])
            else:
                return f"""❌ **Complaint Not Found**

**Complaint ID:** {complaint_id}
**Error:** {result['error']}

Please verify the Complaint ID and try again."""

        # Try to find mobile number in the message
        mobile_match = re.search(r'\+?\d{10,15}', user_message)
        if mobile_match:
            mobile = mobile_match.group()
            result = get_user_complaints_api(mobile)

            if result["success"] and result["data"]:
                complaints = result["data"]
                if len(complaints) == 1:
                    return get_detailed_complaint_info(complaints[0])
                else:
                    return handle_smart_status_check(user_message, context, {"mobile": mobile}, intent)

        # No specific ID or mobile found - ask for clarification
        return """🔍 **Status Check - Need More Information**

I'd be happy to check your complaint status! Please provide:

**Option 1: Complaint ID**
• Format: `CMP12345678`
• Example: "Check status CMP9B41CA0F"
• **Most accurate method**

**Option 2: Mobile Number**
• Use the number you registered with
• Example: "Status for +1234567890"
• Shows all your complaints

**Option 3: Natural Language**
• "What's the status of my laptop complaint?"
• "Check my complaint from yesterday"
• "Any updates on my network issue?"

**Sample Commands:**
• "Status of CMP9B41CA0F"
• "Check complaints for +1234567890"
• "Details of my complaint CMP12345678"

Please provide your Complaint ID or mobile number to proceed."""

def handle_status_check(user_message: str, context: UserContext, extracted_info: Dict) -> str:
    """Handle status check requests"""
    
    # Look for complaint ID in the message
    complaint_id_pattern = r"CMP[A-Z0-9]{8}"
    complaint_id_match = re.search(complaint_id_pattern, user_message.upper())
    
    if complaint_id_match:
        complaint_id = complaint_id_match.group()
        result = get_complaint_status_api(complaint_id)
        
        if result["success"]:
            complaint = result["data"]

            # Status-specific messages
            status_messages = {
                "Registered": "📝 Your complaint has been received and is in our system",
                "In Progress": "⚙️ Our team is actively working on your complaint",
                "Under Review": "🔍 Your complaint is being reviewed by our specialists",
                "Resolved": "✅ Your complaint has been resolved successfully",
                "Closed": "📁 Your complaint has been closed",
                "Rejected": "❌ Your complaint could not be processed"
            }

            status_msg = status_messages.get(complaint['status'], "📊 Status updated")

            return f"""📋 **COMPLAINT STATUS REPORT**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**🆔 Complaint ID:** `{complaint['complaint_id']}`
**📊 Current Status:** **{complaint['status']}**
**🏷️ Category:** {complaint['category']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**📅 Timeline:**
• **Registered:** {complaint['created_at'][:10]}
• **Last Updated:** {complaint['updated_at'][:10]}

**📝 Complaint Details:**
{complaint['complaint_details'][:150]}{"..." if len(complaint['complaint_details']) > 150 else ""}

**ℹ️ Status Information:**
{status_msg}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Need help with anything else? You can:
• Register a new complaint
• Check another complaint status"""
        else:
            return f"""❌ **Complaint Not Found**

**Error:** {result['error']}

**Please verify:**
• Complaint ID format: CMP12345678
• Check for typos in the ID
• Ensure the complaint was registered in this system

**Need help?** Say "help" for assistance or try registering a new complaint."""
    
    # Look for mobile number
    elif "mobile" in extracted_info or validate_mobile(user_message.strip()):
        mobile = extracted_info.get("mobile", user_message.strip())
        result = get_user_complaints_api(mobile)
        
        if result["success"]:
            complaints = result["data"]
            if complaints:
                response = f"""📱 **COMPLAINTS SUMMARY**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**📞 Mobile Number:** {mobile}
**📊 Total Complaints:** {len(complaints)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**📋 Recent Complaints:**
"""
                for i, complaint in enumerate(complaints[:5], 1):  # Show latest 5
                    status_emoji = {
                        "Registered": "📝",
                        "In Progress": "⚙️",
                        "Under Review": "🔍",
                        "Resolved": "✅",
                        "Closed": "📁",
                        "Rejected": "❌"
                    }.get(complaint['status'], "📊")

                    response += f"""
**{i}.** `{complaint['complaint_id']}` {status_emoji}
   **Status:** {complaint['status']}
   **Date:** {complaint['created_at'][:10]}
   **Category:** {complaint['category']}"""

                response += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**🔍 For detailed status:** Provide a specific Complaint ID
**📝 To register new complaint:** Say "I have a complaint"

Which complaint would you like to check in detail?"""
                return response
            else:
                return f"""📱 **No Complaints Found**

**Mobile Number:** {mobile}

**This could mean:**
• No complaints registered with this number
• Different mobile number was used during registration
• Typo in the mobile number

**Would you like to:**
• Register a new complaint?
• Try a different mobile number?
• Check with a Complaint ID instead?"""
        else:
            return f"""❌ **Error Fetching Complaints**

**Error:** {result['error']}

**Please try:**
• Check your mobile number format
• Ensure you're using the registered number
• Contact support if the issue persists"""
    
    else:
        return """🔍 **Status Check Required**

To check your complaint status, please provide **one of the following:**

**Option 1: Complaint ID**
• Format: `CMP12345678`
• Example: "Check status CMP9B41CA0F"
• Most accurate method

**Option 2: Mobile Number**
• Use the number you registered with
• Example: "+1234567890" or "9876543210"
• Shows all your complaints

**Sample Commands:**
• "Status of CMP9B41CA0F"
• "Check my complaints for +1234567890"
• "What's the status of my complaint CMP12345678"

Please provide your Complaint ID or mobile number to proceed."""

class ConversationMemory:
    """Advanced conversation memory system"""

    def __init__(self):
        if "conversation_memory" not in st.session_state:
            st.session_state.conversation_memory = {
                "user_profile": {
                    "name": None,
                    "mobile": None,
                    "preferred_language": "english",
                    "interaction_style": "formal",
                    "complaint_history": []
                },
                "conversation_flow": {
                    "current_intent": None,
                    "previous_intents": [],
                    "context_stack": [],
                    "unresolved_questions": [],
                    "follow_up_needed": False
                },
                "session_data": {
                    "start_time": datetime.now().isoformat(),
                    "total_messages": 0,
                    "topics_discussed": [],
                    "sentiment_history": [],
                    "satisfaction_level": "unknown"
                },
                "smart_context": {
                    "mentioned_entities": [],
                    "technical_terms": [],
                    "complaint_categories": [],
                    "urgency_indicators": [],
                    "resolution_preferences": []
                }
            }

    def update_memory(self, user_message: str, bot_response: str, extracted_info: Dict):
        """Update conversation memory with new interaction"""
        memory = st.session_state.conversation_memory

        # Update session data
        memory["session_data"]["total_messages"] += 1

        # Update user profile
        if extracted_info.get("name") and not memory["user_profile"]["name"]:
            memory["user_profile"]["name"] = extracted_info["name"]
        if extracted_info.get("mobile") and not memory["user_profile"]["mobile"]:
            memory["user_profile"]["mobile"] = extracted_info["mobile"]

        # Analyze and store intent
        current_intent = self.analyze_intent(user_message)
        memory["conversation_flow"]["current_intent"] = current_intent
        memory["conversation_flow"]["previous_intents"].append(current_intent)

        # Update context stack (keep last 5 interactions)
        memory["conversation_flow"]["context_stack"].append({
            "user_message": user_message,
            "bot_response": bot_response,
            "timestamp": datetime.now().isoformat(),
            "intent": current_intent,
            "extracted_info": extracted_info
        })
        if len(memory["conversation_flow"]["context_stack"]) > 5:
            memory["conversation_flow"]["context_stack"].pop(0)

        # Analyze sentiment
        sentiment = self.analyze_sentiment(user_message)
        memory["session_data"]["sentiment_history"].append(sentiment)

        # Update smart context
        self.update_smart_context(user_message, extracted_info)

    def analyze_intent(self, message: str) -> str:
        """Analyze user intent from message"""
        message_lower = message.lower()

        # Intent patterns
        intent_patterns = {
            "register_complaint": ["register", "complaint", "file", "submit", "issue", "problem", "broken"],
            "check_status": ["status", "check", "update", "progress", "what happened", "any news"],
            "modify_complaint": ["change", "update", "modify", "edit", "correct"],
            "cancel_complaint": ["cancel", "withdraw", "remove", "delete"],
            "get_help": ["help", "how", "what", "guide", "explain", "instructions"],
            "express_frustration": ["angry", "frustrated", "terrible", "awful", "disappointed"],
            "express_satisfaction": ["thank", "good", "great", "excellent", "satisfied"],
            "request_escalation": ["manager", "supervisor", "escalate", "higher", "urgent"],
            "ask_timeline": ["when", "how long", "timeline", "eta", "expected"],
            "provide_feedback": ["feedback", "suggestion", "improve", "better"]
        }

        for intent, keywords in intent_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                return intent

        return "general_inquiry"

    def analyze_sentiment(self, message: str) -> str:
        """Analyze sentiment of user message"""
        message_lower = message.lower()

        positive_words = ["thank", "good", "great", "excellent", "satisfied", "happy", "pleased"]
        negative_words = ["angry", "frustrated", "terrible", "awful", "disappointed", "upset", "bad"]
        urgent_words = ["urgent", "emergency", "asap", "immediately", "critical", "serious"]

        if any(word in message_lower for word in urgent_words):
            return "urgent"
        elif any(word in message_lower for word in negative_words):
            return "negative"
        elif any(word in message_lower for word in positive_words):
            return "positive"
        else:
            return "neutral"

    def update_smart_context(self, message: str, extracted_info: Dict):
        """Update smart context with entities and technical terms"""
        memory = st.session_state.conversation_memory

        # Technical categories
        tech_categories = {
            "hardware": ["laptop", "computer", "screen", "keyboard", "mouse", "printer", "monitor"],
            "software": ["application", "program", "software", "app", "system", "windows", "browser"],
            "network": ["internet", "wifi", "connection", "network", "email", "website", "server"],
            "billing": ["bill", "charge", "payment", "invoice", "account", "subscription", "refund"],
            "service": ["support", "service", "help", "assistance", "response", "agent"]
        }

        message_lower = message.lower()
        for category, terms in tech_categories.items():
            if any(term in message_lower for term in terms):
                if category not in memory["smart_context"]["complaint_categories"]:
                    memory["smart_context"]["complaint_categories"].append(category)
                memory["smart_context"]["technical_terms"].extend([term for term in terms if term in message_lower])

        # Extract entities
        if extracted_info.get("complaint_id"):
            memory["smart_context"]["mentioned_entities"].append(f"complaint_id:{extracted_info['complaint_id']}")

        # Remove duplicates
        memory["smart_context"]["technical_terms"] = list(set(memory["smart_context"]["technical_terms"]))
        memory["smart_context"]["mentioned_entities"] = list(set(memory["smart_context"]["mentioned_entities"]))

    def get_contextual_insights(self) -> Dict:
        """Get insights from conversation memory"""
        memory = st.session_state.conversation_memory

        return {
            "user_profile": memory["user_profile"],
            "current_intent": memory["conversation_flow"]["current_intent"],
            "recent_intents": memory["conversation_flow"]["previous_intents"][-3:],
            "conversation_length": len(memory["conversation_flow"]["context_stack"]),
            "dominant_sentiment": max(set(memory["session_data"]["sentiment_history"]),
                                   key=memory["session_data"]["sentiment_history"].count) if memory["session_data"]["sentiment_history"] else "neutral",
            "technical_focus": memory["smart_context"]["complaint_categories"],
            "needs_follow_up": memory["conversation_flow"]["follow_up_needed"]
        }

def analyze_conversation_context() -> Dict[str, Any]:
    """Enhanced conversation analysis with memory integration"""
    if not st.session_state.messages:
        return {"has_history": False}

    # Initialize memory system
    memory_system = ConversationMemory()
    insights = memory_system.get_contextual_insights()

    context_info = {
        "has_history": True,
        "message_count": len(st.session_state.messages),
        "recent_topics": [],
        "user_mentioned_name": insights["user_profile"]["name"],
        "user_mentioned_mobile": insights["user_profile"]["mobile"],
        "complaint_ids_mentioned": [],
        "last_bot_action": None,
        "conversation_stage": "ongoing",
        "user_sentiment": insights["dominant_sentiment"],
        "urgency_level": "high" if insights["dominant_sentiment"] == "urgent" else "normal",
        "technical_terms": [],
        "complaint_categories": insights["technical_focus"],
        "user_intent_history": insights["recent_intents"],
        "follow_up_needed": insights["needs_follow_up"],
        "current_intent": insights["current_intent"],
        "conversation_insights": insights
    }

    # Analyze recent messages (last 15 for better context)
    recent_messages = st.session_state.messages[-15:]

    # Sentiment keywords
    positive_words = ["thank", "thanks", "good", "great", "excellent", "satisfied", "happy"]
    negative_words = ["angry", "frustrated", "terrible", "awful", "disappointed", "upset"]
    urgent_words = ["urgent", "emergency", "asap", "immediately", "critical", "serious"]

    # Technical categories
    tech_categories = {
        "hardware": ["laptop", "computer", "screen", "keyboard", "mouse", "printer"],
        "software": ["application", "program", "software", "app", "system", "windows"],
        "network": ["internet", "wifi", "connection", "network", "email", "website"],
        "billing": ["bill", "charge", "payment", "invoice", "account", "subscription"],
        "service": ["support", "service", "help", "assistance", "response"]
    }

    for msg in recent_messages:
        content = msg["content"].lower()
        original_content = msg["content"]

        # Extract complaint IDs
        complaint_ids = re.findall(r'cmp[a-z0-9]{8}', content)
        context_info["complaint_ids_mentioned"].extend(complaint_ids)

        # Extract mobile numbers
        mobile_match = re.search(r'\+?\d{10,15}', original_content)
        if mobile_match and not context_info["user_mentioned_mobile"]:
            context_info["user_mentioned_mobile"] = mobile_match.group()

        # Extract names with better patterns
        if msg["role"] == "user":
            name_patterns = [
                r'(?:my name is|i am|i\'m|call me|this is)\s+([a-zA-Z\s]{2,40})',
                r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\s|,|\.)',
                r'hi,?\s+i\'?m\s+([a-zA-Z\s]{2,30})',
            ]
            for pattern in name_patterns:
                name_match = re.search(pattern, original_content, re.IGNORECASE)
                if name_match and not context_info["user_mentioned_name"]:
                    potential_name = name_match.group(1).strip()
                    # Validate it's actually a name (not a complaint description)
                    if len(potential_name.split()) <= 4 and not any(word in potential_name.lower() for word in ["issue", "problem", "complaint", "broken"]):
                        context_info["user_mentioned_name"] = potential_name

        # Analyze sentiment
        if any(word in content for word in positive_words):
            context_info["user_sentiment"] = "positive"
        elif any(word in content for word in negative_words):
            context_info["user_sentiment"] = "negative"

        # Check urgency
        if any(word in content for word in urgent_words):
            context_info["urgency_level"] = "high"

        # Categorize technical terms
        for category, terms in tech_categories.items():
            if any(term in content for term in terms):
                if category not in context_info["complaint_categories"]:
                    context_info["complaint_categories"].append(category)
                context_info["technical_terms"].extend([term for term in terms if term in content])

        # Track conversation topics and intents
        if msg["role"] == "user":
            if any(word in content for word in ["complaint", "issue", "problem", "register", "file"]):
                context_info["recent_topics"].append("complaint_registration")
                context_info["user_intent_history"].append("register_complaint")
            elif any(word in content for word in ["status", "check", "update", "progress"]):
                context_info["recent_topics"].append("status_check")
                context_info["user_intent_history"].append("check_status")
            elif any(word in content for word in ["help", "how", "what", "guide"]):
                context_info["user_intent_history"].append("seek_help")
            elif any(word in content for word in ["thank", "thanks", "bye", "goodbye"]):
                context_info["user_intent_history"].append("closing")

        # Track bot actions with more detail
        if msg["role"] == "assistant":
            if "complaint id" in content and "registered successfully" in content:
                context_info["last_bot_action"] = "completed_registration"
            elif "please provide your" in content or "enter your" in content:
                context_info["last_bot_action"] = "collecting_info"
            elif "status" in content and ("complaint id" in content or "mobile" in content):
                context_info["last_bot_action"] = "provided_status"
            elif "help" in content or "guide" in content:
                context_info["last_bot_action"] = "provided_help"
            elif "not sure" in content or "understand" in content:
                context_info["last_bot_action"] = "clarification_needed"

    # Determine if follow-up is needed
    if context_info["last_bot_action"] == "collecting_info":
        context_info["follow_up_needed"] = True
    elif context_info["urgency_level"] == "high":
        context_info["follow_up_needed"] = True

    # Remove duplicates
    context_info["complaint_ids_mentioned"] = list(set(context_info["complaint_ids_mentioned"]))
    context_info["technical_terms"] = list(set(context_info["technical_terms"]))
    context_info["complaint_categories"] = list(set(context_info["complaint_categories"]))

    return context_info

def get_contextual_response(user_message: str, context: UserContext) -> str:
    """Generate contextual responses based on conversation history"""
    message_lower = user_message.lower()
    conv_context = analyze_conversation_context()

    # Greeting responses with context awareness
    if any(word in message_lower for word in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]):
        if conv_context["has_history"]:
            if conv_context["last_bot_action"] == "completed_registration":
                return """👋 **Hello again!**

I see we just completed your complaint registration. Is there anything else I can help you with?

**You can:**
• Check the status of your recent complaint
• Register another complaint if needed
• Ask any questions about the process

What would you like to do next?"""

            elif conv_context["complaint_ids_mentioned"]:
                recent_id = conv_context["complaint_ids_mentioned"][-1].upper()
                return f"""👋 **Welcome back!**

I see we were discussing complaint **{recent_id}**.

**How can I continue helping you?**
• Get an update on {recent_id}
• Register a new complaint
• Check other complaint statuses

What would you like to do?"""

            elif conv_context["message_count"] > 2:
                return """👋 **Hello again!**

I see we've been chatting. How can I continue assisting you today?

**I'm ready to help with:**
• Complaint registration or updates
• Status checking
• Any questions you might have

What can I do for you?"""

        # First-time greeting
        return """👋 **Welcome to the Smart Grievance Management System!**

I'm your AI assistant, ready to help you with complaint management.

**🎯 I can help you:**
• **Register complaints** - Just describe your issue naturally
• **Check status** - Provide your complaint ID or mobile number
• **Track progress** - Get detailed updates on your complaints

**💡 Try saying:**
• "I have an issue with my laptop"
• "Check status CMP12345678"
• "What's my complaint status?"

How can I assist you today?"""

    # Contextual general responses for unclear messages
    else:
        if conv_context["has_history"]:
            if conv_context["last_bot_action"] == "collecting_info":
                return """🤔 **I'm not sure I understood that.**

It looks like I was collecting information from you. Could you please:
• Provide the information I requested, or
• Say "start over" if you want to begin fresh, or
• Ask "help" if you need guidance

What would you like to do?"""

            elif conv_context["complaint_ids_mentioned"]:
                recent_id = conv_context["complaint_ids_mentioned"][-1].upper()
                return f"""🤔 **I'm not sure what you need.**

I see we were discussing complaint **{recent_id}**. Would you like to:
• Get a status update on {recent_id}
• Register a new complaint
• Check other complaints
• Get help with something else

Please let me know how I can assist you!"""

            elif conv_context["message_count"] > 2:
                return """🤔 **I'm not sure I understood that.**

Based on our conversation, I can help you with:
• **Complaint registration** - Describe your issue
• **Status checking** - Provide complaint ID or mobile number
• **General help** - Say "help" for guidance

What would you like to do?"""

        # Default response for new users
        return """🤖 **I'm here to help with your complaints!**

I can assist you with:
• **Register complaints** - Just describe your issue
• **Check status** - Provide your complaint ID or mobile
• **Get help** - Ask me anything about the process

**💡 Try saying:**
• "I have a problem with..."
• "Check status CMP12345678"
• "Help me understand this system"

What can I do for you?"""

def get_general_response(user_message: str, context: UserContext) -> str:
    """Generate general responses with conversation context"""
    message_lower = user_message.lower()

    # Check for greetings first
    if any(word in message_lower for word in ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]):
        return get_contextual_response(user_message, context)

    # Check for help requests
    elif any(word in message_lower for word in ["help", "what can you do", "how does this work", "guide", "instructions"]):
        conv_context = analyze_conversation_context()
        if conv_context["has_history"] and conv_context["message_count"] > 3:
            return """📚 **Help - Based on Our Conversation**

I can see we've been chatting, so let me give you targeted help:

**🔄 Continue What We Started:**
• If you were registering a complaint, I can pick up where we left off
• If you were checking status, I can help with that too

**🆕 Start Something New:**
• Register a new complaint: "I have a problem with..."
• Check different complaint: "Status of CMP12345678"
• Get general info: "Show me my complaints"

**💡 Smart Features I Offer:**
• **Natural conversation** - Just talk normally
• **Auto-detection** - I extract names, numbers, IDs automatically
• **Context memory** - I remember our conversation
• **Flexible input** - All details at once or step-by-step

**Based on our chat, what would you like to do next?**"""

        return """📚 **Complete Help Guide**

**🧠 Smart Features:**
• **Natural Language** - Talk to me normally, no special commands needed
• **Auto-Detection** - I extract names, mobile numbers, complaint IDs automatically
• **Context Awareness** - I remember our conversation and respond accordingly
• **Flexible Input** - Provide all details at once or step-by-step

**🆕 Complaint Registration:**
• "I have an issue with my laptop"
• "Hi, I'm John (+1234567890), my computer is broken"
• "Register complaint: Internet is very slow"

**🔍 Status Checking:**
• "Check status CMP9B41CA0F"
• "What's my complaint status for +1234567890?"
• "Any updates on my laptop issue?"

**💡 I learn from our conversation and provide relevant responses!**

What would you like to do?"""

    # Check for thank you/goodbye
    elif any(word in message_lower for word in ["thank", "thanks", "bye", "goodbye", "exit", "quit"]):
        conv_context = analyze_conversation_context()
        if conv_context["last_bot_action"] == "completed_registration":
            return """🙏 **You're welcome!**

I'm glad I could help you register your complaint successfully.

**📋 Remember:**
• Save your Complaint ID for future reference
• Check back anytime for status updates
• I'm here 24/7 if you need more help

**Have a great day!** 🌟"""

        elif conv_context["complaint_ids_mentioned"]:
            return """🙏 **Thank you for using our service!**

I hope I was able to help with your complaint inquiries.

**🔔 Don't forget:**
• Your complaint IDs are important - keep them safe
• Check back for status updates
• I'm always here to help

**Take care!** 🌟"""

        return """🙏 **Thank you for visiting!**

I hope our conversation was helpful. Feel free to return anytime for:
• New complaint registration
• Status updates
• Any assistance you need

**Have a wonderful day!** 🌟"""

    # For unclear messages, use contextual response
    else:
        return get_contextual_response(user_message, context)



# Main UI
def main():
    # Professional Clean UI Styling
    st.markdown("""
    <style>
    /* Hide Streamlit elements */
    .stDeployButton { display: none; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
    .stActionButton { display: none; }

    /* Clean container */
    .main .block-container {
        padding: 1rem 2rem;
        max-width: 1200px;
        margin: 0 auto;
    }

    /* Professional header */
    .main-header {
        background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }

    /* Clean sidebar */
    .css-1d391kg { padding-top: 1rem; }
    .sidebar-section {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid #3498db;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }

    /* Status indicators */
    .status-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 8px;
        animation: pulse 2s infinite;
    }

    .status-online { background: #27ae60; }
    .status-offline { background: #e74c3c; }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }

    /* Chat styling */
    .stChatMessage {
        margin: 0.5rem 0;
        border-radius: 12px;
    }

    .stChatMessage[data-testid="chat-message-user"] {
        flex-direction: row-reverse;
    }

    .stChatMessage[data-testid="chat-message-user"] .stChatMessageContent {
        background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        color: white;
        border-radius: 18px 18px 5px 18px;
        box-shadow: 0 2px 8px rgba(52, 152, 219, 0.3);
    }

    .stChatMessage[data-testid="chat-message-assistant"] .stChatMessageContent {
        background: #f8f9fa;
        color: #2c3e50;
        border-radius: 18px 18px 18px 5px;
        border-left: 3px solid #3498db;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }

    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(52, 152, 219, 0.3);
    }

    /* Input styling */
    .stChatInput > div > div > input {
        border-radius: 25px;
        border: 2px solid #e9ecef;
        padding: 0.75rem 1rem;
    }

    .stChatInput > div > div > input:focus {
        border-color: #3498db;
        box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
    }
    </style>
    """, unsafe_allow_html=True)

    # Clean Professional Header
    st.markdown("""
    <div class="main-header">
        <h1 style="margin: 0; font-size: 2.5rem; font-weight: 300;">Grievance Management System</h1>
        <p style="font-size: 1.1rem; margin: 0.5rem 0 0 0; opacity: 0.9;">AI-Powered Complaint Management Platform</p>
    </div>
    """, unsafe_allow_html=True)

    # Clean Professional Sidebar
    with st.sidebar:
        st.markdown("### System Status")

        api_status = check_api_server()
        if api_status:
            st.markdown("""
            <div class="sidebar-section">
                <span class="status-indicator status-online"></span>
                <strong>System Online</strong><br>
                <small>All services operational</small>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="sidebar-section">
                <span class="status-indicator status-offline"></span>
                <strong>System Offline</strong><br>
                <small>Please start the server</small>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("### Quick Actions")

        if st.button("🆕 New Complaint", use_container_width=True):
            st.session_state.quick_action = "I want to register a complaint"
            st.rerun()

        if st.button("🔍 Check Status", use_container_width=True):
            st.session_state.quick_action = "Check my complaint status"
            st.rerun()

        if st.button("🔄 Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.user_context = UserContext()
            st.rerun()

        st.markdown("### Sample Data")
        st.markdown("""
        **Test Complaint IDs:**
        • CMP9B41CA0F
        • CMPBD678C56
        • CMP3A066B16
        """)

        st.markdown("### Admin Panel")
        if st.button("🔧 Admin Dashboard", use_container_width=True):
            st.switch_page("pages/admin.py")
    
    # Clean Welcome Message
    if not st.session_state.messages:
        welcome_msg = """👋 **Welcome to the Grievance Management System**

I'm your AI assistant, ready to help you manage complaints efficiently.

**What I can help you with:**
• Register new complaints
• Check complaint status
• Track your issues

**Getting started:**
• Type "I have a complaint" to register
• Type "Check status [ID]" to track
• Ask me anything about your complaints

How can I assist you today?"""

        st.session_state.messages.append({
            "role": "assistant",
            "content": welcome_msg,
            "timestamp": datetime.now().strftime('%H:%M')
        })

    # Clean Chat Interface
    for message in st.session_state.messages:
        timestamp = message.get('timestamp', datetime.now().strftime('%H:%M'))

        if message["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(message["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(message["content"])

    # Input handling section
    st.markdown("---")

    # Handle quick actions
    if hasattr(st.session_state, 'quick_action'):
        prompt = st.session_state.quick_action
        del st.session_state.quick_action
    else:
        prompt = st.chat_input("💬 Type your message here...", key="chat_input")

    if prompt:
        # Add user message to history
        user_message = {
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now().strftime('%H:%M')
        }
        st.session_state.messages.append(user_message)

        # Show typing indicator
        with st.spinner("🤖 AI is processing your request..."):
            # Process the request
            if not api_status:
                response = """❌ **System Temporarily Unavailable**

I apologize, but our backend services are currently offline. This means I cannot process complaint registrations or status checks at the moment.

**🔧 Technical Details:**
• API server connection failed
• Database services unavailable
• Real-time processing disabled

**🚀 Quick Resolution:**
1. Ensure the API server is running: `python api_server.py`
2. Verify server accessibility at http://127.0.0.1:8000
3. Check system logs for error details

**💡 Alternative Actions:**
• Try again in a few moments
• Contact system administrator
• Use offline complaint forms if available

I'll be ready to help once the system is back online!"""
            else:
                response = process_user_message(prompt)

        # Add assistant response to history
        assistant_message = {
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().strftime('%H:%M')
        }
        st.session_state.messages.append(assistant_message)

        # Rerun to update the chat display
        st.rerun()

    # Clean Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #95a5a6; font-size: 0.85rem; padding: 1rem;'>"
        "Grievance Management System © 2024"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
