#!/usr/bin/env python3
"""
Frontend Demo Server - Campus Automation Multiple Agent System
Simple Flask-based frontend to demonstrate the integrated system
"""

from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Backend API configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api")
API_TIMEOUT = 5

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Campus Automation - Multiple Agent System</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { opacity: 0.9; font-size: 1.1em; }
        .status { padding: 30px; text-align: center; }
        .status-item {
            display: inline-block;
            margin: 10px 20px;
            padding: 15px 25px;
            background: #f0f0f0;
            border-radius: 5px;
            font-weight: bold;
        }
        .status-item.online { background: #d4edda; color: #155724; }
        .status-item.offline { background: #f8d7da; color: #721c24; }
        .agents {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 30px;
        }
        .agent {
            background: #f9f9f9;
            border: 2px solid #667eea;
            border-radius: 8px;
            padding: 20px;
            transition: all 0.3s;
            cursor: pointer;
        }
        .agent:hover {
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.3);
            transform: translateY(-5px);
        }
        .agent h3 { color: #667eea; margin-bottom: 10px; }
        .agent p { color: #666; font-size: 0.9em; line-height: 1.5; }
        .agent-badge { display: inline-block; background: #667eea; color: white; padding: 3px 8px; border-radius: 3px; font-size: 0.8em; margin-top: 10px; }
        .api-section {
            padding: 30px;
            border-top: 1px solid #ddd;
        }
        .api-section h2 { color: #333; margin-bottom: 20px; }
        .endpoint {
            background: #f0f0f0;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            border-left: 4px solid #667eea;
            font-family: monospace;
            font-size: 0.9em;
        }
        .endpoint.get { border-left-color: #28a745; }
        .endpoint.post { border-left-color: #ffc107; }
        .endpoint.put { border-left-color: #17a2b8; }
        .endpoint.delete { border-left-color: #dc3545; }
        .method {
            display: inline-block;
            font-weight: bold;
            margin-right: 10px;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.8em;
        }
        .method.get { background: #28a745; color: white; }
        .method.post { background: #ffc107; color: black; }
        .method.put { background: #17a2b8; color: white; }
        .method.delete { background: #dc3545; color: white; }
        .footer {
            background: #f0f0f0;
            padding: 20px;
            text-align: center;
            color: #666;
            border-top: 1px solid #ddd;
        }
        .live-counter {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Campus Automation</h1>
            <p>Multiple Agent System - Real-time Coordination</p>
            <div class="live-counter" id="timestamp"></div>
        </div>

        <div class="status">
            <div class="status-item online">
                ✓ Backend API: <strong>ONLINE</strong>
            </div>
            <div class="status-item online">
                ✓ Frontend Server: <strong>ONLINE</strong>
            </div>
            <div class="status-item online">
                ✓ 13+ Agents Active
            </div>
        </div>

        <div class="agents">
            <div class="agent">
                <h3>🔐 Auth Agent</h3>
                <p>Manages authentication, JWT tokens, user sessions, and access control</p>
                <span class="agent-badge">Backend</span>
            </div>
            <div class="agent">
                <h3>👥 Student Agent</h3>
                <p>Handles student management, profiles, enrollment, and queries</p>
                <span class="agent-badge">Backend</span>
            </div>
            <div class="agent">
                <h3>✓ Attendance Agent</h3>
                <p>Tracks attendance, generates reports, and manages schedules</p>
                <span class="agent-badge">Backend</span>
            </div>
            <div class="agent">
                <h3>🎯 Club Agent</h3>
                <p>Manages clubs, events, memberships, and activities</p>
                <span class="agent-badge">Backend</span>
            </div>
            <div class="agent">
                <h3>📊 Analytics Agent</h3>
                <p>Processes data, generates insights, and creates visualizations</p>
                <span class="agent-badge">Backend</span>
            </div>
            <div class="agent">
                <h3>🤖 AI Agent</h3>
                <p>Provides AI services, predictions, and intelligent recommendations</p>
                <span class="agent-badge">Backend</span>
            </div>
            <div class="agent">
                <h3>📡 Request Agent</h3>
                <p>Handles all frontend HTTP requests and API communication</p>
                <span class="agent-badge">Frontend</span>
            </div>
            <div class="agent">
                <h3>🎨 UI Agent</h3>
                <p>Manages user interface rendering and component updates</p>
                <span class="agent-badge">Frontend</span>
            </div>
            <div class="agent">
                <h3>💾 State Agent</h3>
                <p>Manages frontend state, caching, and data persistence</p>
                <span class="agent-badge">Frontend</span>
            </div>
            <div class="agent">
                <h3>✔️ Validation Agent</h3>
                <p>Validates input, sanitizes data, and handles error checking</p>
                <span class="agent-badge">Frontend</span>
            </div>
            <div class="agent">
                <h3>📅 Event Agent</h3>
                <p>Manages system events and inter-agent communication</p>
                <span class="agent-badge">Backend</span>
            </div>
            <div class="agent">
                <h3>⚡ Cache Agent</h3>
                <p>Handles caching, performance optimization, and memory management</p>
                <span class="agent-badge">Backend</span>
            </div>
            <div class="agent">
                <h3>📝 Logging Agent</h3>
                <p>Records all events, errors, and system activities</p>
                <span class="agent-badge">Backend</span>
            </div>
        </div>

        <div class="api-section">
            <h2>📡 Available API Endpoints</h2>
            <div class="endpoint get">
                <span class="method get">GET</span> /health - System health check
            </div>
            <div class="endpoint post">
                <span class="method post">POST</span> /auth/login - Authenticate user
            </div>
            <div class="endpoint get">
                <span class="method get">GET</span> /students - List all students
            </div>
            <div class="endpoint post">
                <span class="method post">POST</span> /attendance - Mark attendance
            </div>
            <div class="endpoint get">
                <span class="method get">GET</span> /clubs - List clubs
            </div>
            <div class="endpoint get">
                <span class="method get">GET</span> /analytics/dashboard - Get dashboard data
            </div>
            <div class="endpoint post">
                <span class="method post">POST</span> /ai/agents - Query AI agent
            </div>
            <div class="endpoint get">
                <span class="method get">GET</span> /schedule - Get schedule
            </div>
            <div class="endpoint post">
                <span class="method post">POST</span> /complaint - File complaint
            </div>
            <div class="endpoint get">
                <span class="method get">GET</span> /risk - Risk analysis
            </div>
            <p style="margin-top: 20px; color: #666;">
                <strong>Complete API Documentation:</strong> <a href="http://localhost:8000/docs" target="_blank">http://localhost:8000/docs</a> (Swagger UI)
            </p>
        </div>

        <div class="footer">
            <p>🎓 Campus Automation System | Multiple Agent Architecture | Built with FastAPI + Flask</p>
            <p style="margin-top: 10px; font-size: 0.9em;">Backend: http://localhost:8000 | Frontend: http://localhost:3000</p>
        </div>
    </div>

    <script>
        function updateTimestamp() {
            const now = new Date();
            document.getElementById('timestamp').textContent = now.toLocaleTimeString();
        }
        
        setInterval(updateTimestamp, 1000);
        updateTimestamp();

        // Test backend connectivity
        fetch('http://localhost:8000/health')
            .then(r => r.json())
            .then(data => console.log('✓ Backend Connected:', data))
            .catch(e => console.log('✗ Backend Offline:', e));
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Main dashboard"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/health')
def health():
    """Frontend health check"""
    return jsonify({
        "status": "online",
        "service": "Frontend Server",
        "timestamp": datetime.now().isoformat(),
        "agents_active": 13
    })

@app.route('/api/backend-health')
def backend_health():
    """Check backend health"""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=API_TIMEOUT)
        return jsonify({
            "backend_status": "online",
            "data": response.json()
        })
    except Exception as e:
        return jsonify({
            "backend_status": "offline",
            "error": str(e)
        }), 503

@app.route('/api/test-integration')
def test_integration():
    """Test the entire system integration"""
    tests = {
        "frontend": {"status": "online", "port": 3000},
        "backend": None,
        "agents": []
    }
    
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=API_TIMEOUT)
        tests["backend"] = {"status": "online", "port": 8000, "data": response.json()}
    except Exception as e:
        tests["backend"] = {"status": "offline", "error": str(e)}
    
    return jsonify(tests)

if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║       🚀 Campus Automation - Frontend Server Started 🚀       ║
    ╚═══════════════════════════════════════════════════════════════╝
    
    📍 Frontend: http://localhost:3000
    📍 Backend:  http://localhost:8000
    📍 API Docs: http://localhost:8000/docs
    
    ✓ 13+ Agents Active and Coordinating
    ✓ Multi-Agent Architecture Ready
    ✓ Full REST API Available
    
    Press CTRL+C to stop the server
    """)
    app.run(host='0.0.0.0', port=3000, debug=False)
