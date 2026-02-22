const express = require('express');
const cors = require('cors');
const path = require('path');
const http = require('http');
const axios = require('axios');

const app = express();

// Middleware
app.use(cors({
    origin: ['http://localhost:3000', 'http://localhost:8000', 'http://127.0.0.1:3000', 'https://sp0511-major-project-4.onrender.com'],
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization']
}));

app.use(express.json());

// Serve static files from root directory first (for modern UI)
app.use(express.static(path.join(__dirname)));

// Also serve old interface if needed
app.use(express.static(path.join(__dirname, 'stitch_student_attendance')));

// --- UPDATED FOR LIVE RENDER BACKEND ---
const API_BASE_URL = 'https://sp0511-major-project-4.onrender.com';

// Proxy middleware to forward requests to backend
app.all('/api/*', async (req, res) => {
    try {
        const backendUrl = API_BASE_URL + req.path.replace('/api', '');
        const config = {
            method: req.method,
            url: backendUrl,
            headers: {
                ...req.headers,
                // Host header updated for Render compatibility
                'host': 'sp0511-major-project-4.onrender.com'
            }
        };

        if (req.body && Object.keys(req.body).length > 0) {
            config.data = req.body;
        }

        if (req.query && Object.keys(req.query).length > 0) {
            config.params = req.query;
        }

        const response = await axios(config);
        res.status(response.status).json(response.data);
    } catch (error) {
        console.error('API Error:', error.message);
        res.status(error.response?.status || 500).json({
            status: 'error',
            message: error.response?.data?.message || error.message
        });
    }
});

// --- ALL FRONTEND ROUTES RESTORED ---
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_student_attendance', 'homepage', 'index.html'));
});

app.get('/attendance', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_student_attendance', 'student_attendance', 'index.html'));
});

app.get('/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_student_attendance', 'student_performance_dashboard', 'index.html'));
});

app.get('/clubs', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_student_attendance', 'club_information', 'index.html'));
});

app.get('/events', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_student_attendance', 'events_hub', 'index.html'));
});

app.get('/timetable', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_student_attendance', 'timetable_&_holidays', 'index.html'));
});

app.get('/gemini-settings', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_student_attendance', 'gemini_settings', 'index.html'));
});

// Health check
app.get('/health', (req, res) => {
    res.json({ status: 'Marvel Frontend Server Running', port: 3000 });
});

// Error handling middleware
app.use((err, req, res, next) => {
    console.error('Error:', err);
    res.status(500).json({
        status: 'error',
        message: 'Internal server error'
    });
});

// Start server
const PORT = process.env.PORT || 3000;
const server = http.createServer(app);

server.listen(PORT, () => {
    console.log(`🚀 Marvel Frontend Server running on http://localhost:${PORT}`);
    // Live Backend URL clearly visible in logs now
    console.log(`📡 Connected to Live Backend: ${API_BASE_URL}`);
});

module.exports = app;