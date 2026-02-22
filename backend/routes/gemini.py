# ============================================================================
# Gemini AI Chatbot Route (Phase 5 - Enhancement)
# ============================================================================
# This module handles all Gemini chatbot interactions, API key management,
# and campus-specific context enrichment for intelligent responses.
# ============================================================================

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import logging
import asyncio
import os

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/gemini", tags=["gemini-chatbot"])

# ============================================================================
# SCHEMAS / MODELS
# ============================================================================

class ChatMessage(BaseModel):
    """Single chat message"""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    """Request for chatbot response"""
    message: str = Field(..., min_length=1, max_length=1000, description="User message")
    context: Optional[dict] = Field(default=None, description="Optional campus context")
    user_type: Optional[str] = Field(default="student", description="'student', 'faculty', 'admin'")


class ChatResponse(BaseModel):
    """Response from chatbot"""
    success: bool
    message: str
    response: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class APIKeyRequest(BaseModel):
    """Request to update API key"""
    api_key: str = Field(..., min_length=10, description="Gemini API Key")
    admin_password: str = Field(..., description="Admin password for verification")


class APIKeyValidationResponse(BaseModel):
    """Response for API key validation"""
    valid: bool
    message: str
    status: str  # "connected", "invalid", "error"


class ChatbotStatusResponse(BaseModel):
    """Overall chatbot status"""
    enabled: bool
    api_connected: bool
    model: str
    rate_limit: int
    message: str


# ============================================================================
# GEMINI AI SERVICE
# ============================================================================

class GeminiChatbotService:
    """Service for handling Gemini API interactions with campus context"""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.enabled = settings.ENABLE_GEMINI_CHATBOT
        self.session_context = {}

    async def validate_api_key(self, api_key: str) -> tuple[bool, str]:
        """
        Validate Gemini API key with test request
        Returns: (is_valid, message)
        """
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(self.model)
            
            # Test with simple prompt
            response = model.generate_content("Say 'API Connected' only.")
            
            if response and response.text:
                logger.log_event(
                    "gemini_api_validated",
                    level="INFO",
                    status="success"
                )
                return True, "API Key is valid and connected"
            else:
                return False, "API returned empty response"
                
        except Exception as e:
            logger.log_error("gemini_api_validation_failed", e)
            return False, f"Validation failed: {str(e)}"

    async def generate_response(self, user_message: str, context: dict = None) -> str:
        """
        Generate response from Gemini with campus context
        """
        try:
            if not self.api_key or not self.enabled:
                return "❌ Chatbot is not configured. Please add Gemini API key in settings."

            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)

            # Build context-aware prompt
            system_prompt = self._build_system_prompt(context)
            full_prompt = f"{system_prompt}\n\nUser Query: {user_message}"

            # Generate response with timeout
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    full_prompt
                ),
                timeout=10.0
            )

            if response and response.text:
                logger.log_event(
                    "gemini_response_generated",
                    level="INFO",
                    prompt_length=len(user_message),
                    response_length=len(response.text)
                )
                return response.text
            else:
                return "⚠️ No response from model. Please try again."

        except asyncio.TimeoutError:
            logger.log_error("gemini_timeout", Exception("Request timeout"))
            return "⏱️ Request timeout. The AI model took too long to respond."
        except Exception as e:
            logger.log_error("gemini_response_error", e)
            return f"❌ Error: Unable to process your request. {str(e)[:100]}"

    def _build_system_prompt(self, context: dict = None) -> str:
        """Build system prompt with campus context"""
        base_prompt = """You are a professional Campus Automation Assistant AI chatbot.
You help students, faculty, and administrators with campus-related queries.

GUIDELINES:
- Keep responses SHORT, CLEAR, and FORMAL (max 150 words)
- Focus ONLY on campus-related topics
- Provide accurate information about classes, schedules, attendance, events, and campus resources
- If question is outside campus scope, politely decline and redirect
- Use professional language
- Be helpful and courteous
- Never share sensitive personal data
- Always suggest contacting administration for complex issues"""

        if context:
            if context.get("user_type") == "admin":
                base_prompt += "\n- You're assisting an ADMIN user"
            elif context.get("user_type") == "faculty":
                base_prompt += "\n- You're assisting a FACULTY member"
            elif context.get("user_type") == "student":
                base_prompt += "\n- You're assisting a STUDENT"

            if context.get("current_semester"):
                base_prompt += f"\n- Current semester: {context['current_semester']}"
            
            if context.get("department"):
                base_prompt += f"\n- Department: {context['department']}"

        return base_prompt


# Initialize service
gemini_service = GeminiChatbotService()

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/status", response_model=ChatbotStatusResponse)
async def get_chatbot_status():
    """
    Get current chatbot status and configuration
    Accessible to all authenticated users
    """
    try:
        return ChatbotStatusResponse(
            enabled=gemini_service.enabled,
            api_connected=bool(gemini_service.api_key),
            model=gemini_service.model,
            rate_limit=settings.CHATBOT_RATE_LIMIT,
            message="Chatbot is operational" if gemini_service.enabled else "Chatbot is disabled"
        )
    except Exception as e:
        logger.log_error("get_chatbot_status_error", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send message to Gemini chatbot and receive response
    
    Parameters:
    - message: User's question (required)
    - context: Optional context dict with campus info
    - user_type: Optional user type (student/faculty/admin)
    """
    try:
        if not request.message.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message cannot be empty"
            )

        # Input sanitization
        message = request.message.strip()[:1000]

        # Generate response
        response_text = await gemini_service.generate_response(
            message,
            context=request.context
        )

        return ChatResponse(
            success=True,
            message="Response generated successfully",
            response=response_text
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("chat_error", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing chat request"
        )


@router.post("/validate-key", response_model=APIKeyValidationResponse)
async def validate_api_key(request: APIKeyRequest):
    """
    Validate Gemini API key
    Admin operation - requires password
    
    Parameters:
    - api_key: The Gemini API key to validate
    - admin_password: Admin password for verification
    """
    try:
        # In production, compare with hashed admin password from database
        # For now, use environment variable (should be changed)
        ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
        
        if request.admin_password != ADMIN_PASSWORD:
            logger.log_event(
                "api_key_validation_failed",
                level="WARNING",
                reason="Invalid admin password"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid admin password"
            )

        # Validate the API key
        is_valid, message = await gemini_service.validate_api_key(request.api_key)

        status_msg = "connected" if is_valid else "invalid"
        
        return APIKeyValidationResponse(
            valid=is_valid,
            message=message,
            status=status_msg
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("key_validation_error", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error validating API key"
        )


@router.post("/update-key")
async def update_api_key(request: APIKeyRequest):
    """
    Update Gemini API key
    Admin operation - requires password
    Stores in environment/backend storage
    
    Note: In production, use secure vault (HashiCorp Vault, AWS Secrets Manager)
    """
    try:
        # Verify admin credentials
        ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
        
        if request.admin_password != ADMIN_PASSWORD:
            logger.log_event(
                "api_key_update_attempted",
                level="WARNING",
                reason="Invalid admin password"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid admin password"
            )

        # Validate before saving
        is_valid, validation_msg = await gemini_service.validate_api_key(request.api_key)
        
        if not is_valid:
            return ChatResponse(
                success=False,
                message=f"API key validation failed: {validation_msg}"
            )

        # Update the service
        gemini_service.api_key = request.api_key
        settings.GEMINI_API_KEY = request.api_key
        
        # In production, save to database instead of environment
        logger.log_event(
            "api_key_updated",
            level="INFO",
            status="success"
        )

        return ChatResponse(
            success=True,
            message="API key updated and validated successfully",
            response="Gemini chatbot is now ready to use"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("update_key_error", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating API key"
        )


@router.get("/health")
async def gemini_health_check():
    """
    Health check for Gemini chatbot service
    Used internally for monitoring
    """
    try:
        return {
            "status": "healthy",
            "service": "gemini-chatbot",
            "enabled": gemini_service.enabled,
            "api_configured": bool(gemini_service.api_key),
            "model": gemini_service.model,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.log_error("gemini_health_check_failed", e)
        return {
            "status": "error",
            "service": "gemini-chatbot",
            "error": str(e)
        }


# ============================================================================
# END OF GEMINI CHATBOT ROUTES
# ============================================================================
