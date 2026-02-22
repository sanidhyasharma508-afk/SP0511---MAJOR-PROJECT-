# 🏗️ Gemini Chatbot - System Architecture Diagram

## High-Level System Overview

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│                    CAMPUS AUTOMATION SYSTEM                   │
│                          Phase 5 (2024)                       │
│                                                                │
│   ┌──────────────────────────────────────────────────────┐   │
│   │                                                      │   │
│   │          🌐 FRONTEND (Port 3000)                    │   │
│   │          Node.js / Express                          │   │
│   │                                                      │   │
│   │  ┌────────────────────────────────────────────┐    │   │
│   │  │     Dashboard Pages (HTML)                 │    │   │
│   │  │  ✓ student_performance_dashboard/         │    │   │
│   │  │  ✓ attendance                             │    │   │
│   │  │  ✓ clubs                                  │    │   │
│   │  │  ✓ events                                 │    │   │
│   │  │  ✓ timetable                              │    │   │
│   │  │  ✓ gemini_settings (NEW)                  │    │   │
│   │  └────────────────────────────────────────────┘    │   │
│   │                                                      │   │
│   │  ┌────────────────────────────────────────────┐    │   │
│   │  │  ▶ GeminiChatbot (JS Component)           │    │   │
│   │  │  ▶ gemini-chatbot.js (550 lines)          │    │   │
│   │  │  ▶ gemini-chatbot.css (650 lines)         │    │   │
│   │  │                                             │    │   │
│   │  │  Features:                                 │    │   │
│   │  │  • Floating chat button (💬)              │    │   │
│   │  │  • Message window                         │    │   │
│   │  │  • Settings modal                         │    │   │
│   │  │  • Auto-initialization                    │    │   │
│   │  │  • LocalStorage persistence               │    │   │
│   │  └────────────────────────────────────────────┘    │   │
│   │                                                      │   │
│   └──────────────────────┬───────────────────────────────┘   │
│                          │                                    │
│                          │ HTTP/REST API                     │
│                          │ ↓ ↑                               │
│   ┌──────────────────────┴───────────────────────────────┐   │
│   │                                                      │   │
│   │          🔧 BACKEND API (Port 8000)                 │   │
│   │          FastAPI (Python)                           │   │
│   │                                                      │   │
│   │  ┌────────────────────────────────────────────┐    │   │
│   │  │   Routes: /api/gemini/*                   │    │   │
│   │  │                                             │    │   │
│   │  │   Endpoints:                               │    │   │
│   │  │   ├─ GET /status                          │    │   │
│   │  │   ├─ POST /chat                           │    │   │
│   │  │   ├─ POST /validate-key                   │    │   │
│   │  │   ├─ POST /update-key                     │    │   │
│   │  │   └─ GET /health                          │    │   │
│   │  └────────────────────────────────────────────┘    │   │
│   │                                                      │   │
│   │  ┌────────────────────────────────────────────┐    │   │
│   │  │  GeminiChatbotService (Python)             │    │   │
│   │  │  gemini.py (280 lines)                     │    │   │
│   │  │                                             │    │   │
│   │  │  Methods:                                  │    │   │
│   │  │  ├─ validate_api_key()                    │    │   │
│   │  │  ├─ generate_response()                   │    │   │
│   │  │  ├─ _build_system_prompt()                │    │   │
│   │  │  └─ Error handling                        │    │   │
│   │  └────────────────────────────────────────────┘    │   │
│   │                                                      │   │
│   │  ┌────────────────────────────────────────────┐    │   │
│   │  │  Configuration                             │    │   │
│   │  │  ├─ .env (environment variables)          │    │   │
│   │  │  ├─ config.py (settings)                  │    │   │
│   │  │  └─ main.py (FastAPI app)                 │    │   │
│   │  └────────────────────────────────────────────┘    │   │
│   │                                                      │   │
│   └──────────────────────┬───────────────────────────────┘   │
│                          │                                    │
│                          │ HTTPS (API Key Auth)              │
│                          │ ↓ ↑                               │
│   ┌──────────────────────┴───────────────────────────────┐   │
│   │                                                      │   │
│   │     🤖 GOOGLE GEMINI API (Cloud Platform)           │   │
│   │                                                      │   │
│   │  • Model: gemini-pro                               │   │
│   │  • Authentication: API Key                         │   │
│   │  • Processing: AI conversation                     │   │
│   │  • Response: Natural language answers              │   │
│   │                                                      │   │
│   └──────────────────────────────────────────────────────┘   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Component Interaction Flow

### User Chat Interaction

```
User Types Message
  ↓
Send Click / Enter Key
  ↓
GeminiChatbot.sendMessage()
  ├─ Validate input
  ├─ Add to local messages array
  ├─ Display message in UI
  └─ Show typing indicator
  ↓
HTTP POST /api/gemini/chat
  ├─ Content-Type: application/json
  ├─ Body: { message, context, user_type }
  └─ Headers: { Authorization (if needed) }
  ↓
FastAPI Backend
  ├─ Parse & validate request
  ├─ Input sanitization
  ├─ Get GeminiChatbotService
  └─ Call generate_response()
  ↓
GeminiChatbotService.generate_response()
  ├─ Check API key exists
  ├─ Build system prompt with context
  ├─ Call google.generativeai.GenerativeModel
  └─ Stream response from Gemini
  ↓
Google Generative AI API
  ├─ Receive prompt + system context
  ├─ Process with Gemini Pro model
  ├─ Generate intelligent response
  └─ Return text response
  ↓
Response to Backend
  ├─ Log the interaction
  ├─ Format response
  └─ Return HTTP 200 + JSON
  ↓
Frontend Receives Response
  ├─ Remove typing indicator
  ├─ Add bot message to UI
  ├─ Auto-scroll to latest message
  └─ Save conversation to localStorage
  ↓
User Sees Response ✅
```

---

## Data Flow Diagram

```
┌─────────────────┐
│  USER INPUT     │
│  (Question)     │
└────────┬────────┘
         │
         ↓
┌──────────────────────────────┐
│  FRONTEND (gemini-chatbot.js) │
├──────────────────────────────┤
│ • Validate input             │
│ • Escape HTML                │
│ • Create message object      │
│ • Update UI                  │
└────────┬─────────────────────┘
         │
         │ JSON Payload
         │ ↓
         ↓
┌──────────────────────────────┐
│  BACKEND (gemini.py)         │
├──────────────────────────────┤
│ • Parse request              │
│ • Validate with Pydantic     │
│ • Sanitize input             │
│ • Check rate limit           │
└────────┬─────────────────────┘
         │
         │ Context + Prompt
         │ ↓
         ↓
┌──────────────────────────────┐
│  GEMINI SERVICE              │
├──────────────────────────────┤
│ • Build system prompt        │
│ • Add campus context         │
│ • Set user type              │
│ • Call Gemini API            │
└────────┬─────────────────────┘
         │
         │ API Request
         │ ↓
         ↓
┌──────────────────────────────┐
│  GOOGLE GENERATIVE AI        │
├──────────────────────────────┤
│ • Process with gemini-pro    │
│ • Generate response          │
│ • Apply safety filters       │
│ • Return text                │
└────────┬─────────────────────┘
         │
         │ Response Text
         │ ↓
         ↓
┌──────────────────────────────┐
│  BACKEND RESPONSE HANDLER    │
├──────────────────────────────┤
│ • Format response            │
│ • Log interaction            │
│ • Add timestamp              │
│ • Return JSON                │
└────────┬─────────────────────┘
         │
         │ JSON Response
         │ ↓
         ↓
┌──────────────────────────────┐
│  FRONTEND UI UPDATE          │
├──────────────────────────────┤
│ • Parse response             │
│ • Add bot message            │
│ • Show timestamp             │
│ • Auto-scroll                │
│ • Save to localStorage       │
└────────┬─────────────────────┘
         │
         ↓
   ✅ USER SEES RESPONSE
```

---

## Authentication & Security Flow

```
┌──────────────────────────────────────────────────────┐
│         API KEY MANAGEMENT FLOW                      │
└──────────────────────────────────────────────────────┘

Admin visits: /gemini-settings
      ↓
┌──────────────────────────────────────────────────────┐
│   Settings Page (HTML/JS)                           │
│  • API Key input field                              │
│  • Admin password field                             │
│  • Validate & Save button                           │
└──────────┬───────────────────────────────────────────┘
           │
    User enters:
    • Gemini API Key
    • Admin Password
           │
           ↓
┌──────────────────────────────────────────────────────┐
│  POST /gemini/validate-key {api_key, password}      │
└──────────┬───────────────────────────────────────────┘
           │
           ↓
┌──────────────────────────────────────────────────────┐
│  Backend Validation                                 │
│  ├─ Check admin password                           │
│  ├─ Create temp Gemini client with key             │
│  ├─ Send test prompt                               │
│  └─ Verify response                                │
└──────────┬───────────────────────────────────────────┘
           │
     ┌─────┴─────┐
     │           │
   Valid      Invalid
     │           │
     ↓           ↓
Return      Return
Success     Error
     │           │
     │           └──→ Show Error Message
     │
     ↓
POST /gemini/update-key
{api_key, password}
     │
     ↓
Save to environment
(or database)
     │
     ↓
Return Success ✅
     │
     ↓
Frontend shows:
"✅ API Key Connected!"
```

---

## Message Persistence Flow

```
┌──────────────────────┐
│   NEW MESSAGE        │
└──────────┬───────────┘
           │
           ↓
┌──────────────────────────────────┐
│  GeminiChatbot.addMessage()      │
├──────────────────────────────────┤
│ • Add to messages[] array        │
│ • Create DOM element             │
│ • Display in chat window         │
│ • Auto-scroll                    │
└──────────┬──────────────────────┘
           │
           ↓
┌──────────────────────────────────┐
│  GeminiChatbot.saveMessages()    │
├──────────────────────────────────┤
│ • Serialize messages array       │
│ • Get session ID                 │
│ • Save to localStorage           │
│   Key: gemini-messages-{id}      │
│   Value: JSON array              │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│  PERSISTENCE BENEFITS            │
├──────────────────────────────────┤
│ ✓ Chat history survives refresh  │
│ ✓ Per-session storage            │
│ ✓ No server load                 │
│ ✓ Instant message retrieval      │
│ ✓ Works offline                  │
└──────────────────────────────────┘
```

---

## Error Handling Architecture

```
┌────────────────────────────────────────────┐
│         ERROR HANDLING LAYERS              │
└────────────────────────────────────────────┘

Layer 1: FRONTEND (JavaScript)
├─ Try-catch blocks
├─ User input validation
├─ Network error handling
├─ Timeout detection
└─ User-friendly messages

     ↓

Layer 2: BACKEND (FastAPI)
├─ Pydantic validation errors
├─ HTTPException handling
├─ SQLAlchemy errors
├─ Timeout handling
└─ Logging of errors

     ↓

Layer 3: EXTERNAL API (Gemini)
├─ API key validation
├─ Request timeout
├─ Rate limit checking
├─ Response parsing
└─ Fallback responses

     ↓

Layer 4: USER EXPERIENCE
├─ No crash to user
├─ Clear error message
├─ Suggestions for fix
├─ Retry capability
└─ Graceful degradation
```

---

## Deployment Architecture

```
┌─────────────────────────────────────────────┐
│                                             │
│         DEVELOPMENT ENVIRONMENT             │
│         (Localhost)                         │
│                                             │
│  Backend:  http://localhost:8000  ← FastAPI
│  Frontend: http://localhost:3000  ← Express
│  Browser:  Chrome, Firefox, Safari, Edge
│                                             │
│  Databases:                                 │
│  ├─ SQLite (test.db)  ← Local              │
│  └─ Redis (optional)  ← Caching            │
│                                             │
└─────────────────────────────────────────────┘
                    ↕
              Deploy to:
                    ↕
┌─────────────────────────────────────────────┐
│                                             │
│       PRODUCTION ENVIRONMENT                │
│       (Cloud Platform)                      │
│                                             │
│  Backend:  https://api.example.com         │
│  Frontend: https://app.example.com         │
│  CDN:      Global edge locations           │
│                                             │
│  Databases:                                 │
│  ├─ PostgreSQL ← Production DB             │
│  ├─ Redis     ← Distributed cache          │
│  └─ S3        ← File storage               │
│                                             │
│  API Keys:                                  │
│  ├─ Stored in: AWS Secrets Manager         │
│  ├─ Rotated: Every 90 days                 │
│  └─ Logged: Audit trail maintained         │
│                                             │
└─────────────────────────────────────────────┘
```

---

## Technology Stack Diagram

```
┌────────────────────────────────────────────────────┐
│                  Frontend Stack                    │
├────────────────────────────────────────────────────┤
│                                                    │
│  HTML5 / CSS3 / Vanilla JavaScript                │
│  • No framework dependencies                      │
│  • Pure ES6+ code                                 │
│  • ~1,200 lines total                             │
│                                                    │
│  Styling:                                         │
│  • CSS3 Features: Grid, Flex, Animation          │
│  • Tailwind CSS (for dashboard)                   │
│  • Custom animations & transitions                │
│                                                    │
│  Server:                                          │
│  • Express.js (lightweight routing)               │
│  • Node.js runtime                                │
│  • Static file serving                            │
│                                                    │
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│                  Backend Stack                     │
├────────────────────────────────────────────────────┤
│                                                    │
│  FastAPI (Modern Python Framework)                │
│  • Async/await support                            │
│  • Built-in validation (Pydantic)                 │
│  • Automatic API docs (Swagger/OpenAPI)           │
│                                                    │
│  Core Libraries:                                  │
│  • SQLAlchemy (ORM)                               │
│  • Pydantic (validation)                          │
│  • google-generativeai (Gemini SDK)               │
│  • python-dotenv (config management)              │
│                                                    │
│  Additional:                                      │
│  • Uvicorn (ASGI server)                          │
│  • CORS middleware                                │
│  • Custom logging                                 │
│                                                    │
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│              External Services                     │
├────────────────────────────────────────────────────┤
│                                                    │
│  Google Generative AI API                        │
│  • Model: gemini-pro                              │
│  • Authentication: API Key                        │
│  • Endpoint: https://generativelanguage.googleapis.com │
│  • Rate Limiting: Configurable                    │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## Request/Response Cycle

```
1. USER INTERACTION
   └─ Clicks chat button or types message
   
2. FRONTEND PROCESSING
   ├─ Validate input
   ├─ Sanitize HTML
   ├─ Create payload
   └─ Show loading indicator
   
3. HTTP REQUEST
   └─ POST /api/gemini/chat
   
4. BACKEND PROCESSING
   ├─ Parse request
   ├─ Validate with Pydantic
   ├─ Check authentication
   └─ Call service
   
5. SERVICE LAYER
   ├─ Build prompt
   ├─ Add context
   └─ Call Gemini API
   
6. EXTERNAL API
   ├─ Process request
   ├─ Generate response
   └─ Return JSON
   
7. BACKEND RESPONSE
   ├─ Parse response
   ├─ Log interaction
   └─ Format JSON
   
8. HTTP RESPONSE
   └─ Return 200 OK + body
   
9. FRONTEND HANDLING
   ├─ Remove loading indicator
   ├─ Display response
   ├─ Save to localStorage
   └─ Update UI
   
10. USER SEES RESULT ✅
```

---

## Security Layers

```
┌──────────────────────────────────────────┐
│     SECURITY IMPLEMENTATION              │
└──────────────────────────────────────────┘

Layer 1: Input Security
├─ Length validation (max 1000 chars)
├─ HTML escaping (XSS prevention)
├─ Type checking (Pydantic)
└─ Sanitization

Layer 2: API Security
├─ HTTPS/TLS encryption
├─ API Key in environment
├─ Rate limiting
└─ Error message filtering

Layer 3: Authentication
├─ Admin password verification
├─ Session handling
└─ Authorization checks

Layer 4: Data Security
├─ No sensitive data in logs
├─ LocalStorage encryption (optional)
├─ Secure session handling
└─ CORS configuration

Layer 5: Monitoring
├─ Request logging
├─ Error tracking
├─ API quota monitoring
└─ Anomaly detection
```

---

## File Organization Architecture

```
Backend Structure:
├── routes/
│   ├── gemini.py          ← NEW: Chatbot routes
│   ├── ai.py
│   ├── auth.py
│   └── ... (other routes)
├── core/
│   ├── config.py          ← UPDATED: Gemini settings
│   ├── logging.py
│   └── ... (other config)
├── models/
├── schemas/
├── main.py                ← UPDATED: Router registration
├── .env                   ← UPDATED: API key
└── requirements.txt       ← UPDATED: Dependencies

Frontend Structure:
├── js/
│   ├── gemini-chatbot.js  ← NEW: Component
│   └── ... (other scripts)
├── styles/
│   ├── gemini-chatbot.css ← NEW: Styling
│   └── ... (other styles)
├── stitch_student_attendance/
│   ├── gemini_settings/   ← NEW: Settings page
│   │   └── index.html
│   ├── student_performance_dashboard/
│   │   └── code.html      ← UPDATED: Integration
│   └── ... (other pages)
├── server.js              ← UPDATED: Routing
└── ... (other files)
```

---

**Architecture Version:** 1.0.0  
**Last Updated:** 2024-02-22  
**Status:** ✅ Complete & Verified
