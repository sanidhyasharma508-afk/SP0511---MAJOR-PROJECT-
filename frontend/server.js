const express = require('express');
const cors = require('cors');
const path = require('path');
const http = require('http');

const app = express();

// Middleware
app.use(cors({
    origin: ['http://localhost:3000', 'http://localhost:8000', 'http://127.0.0.1:3000'],
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization']
}));

app.use(express.json());

// Serve static files from root directory first (for modern UI)
app.use(express.static(path.join(__dirname)));

// Also serve old interface if needed
app.use(express.static(path.join(__dirname, 'stitch_student_attendance')));

// API Base URL for backend
const API_BASE_URL = 'http://localhost:8000/api';

// Proxy middleware to forward requests to backend
const axios = require('axios');

// Forward API requests to backend
app.all('/api/*', async (req, res) => {
    try {
        const backendUrl = API_BASE_URL + req.path.replace('/api', '');
        const config = {
            method: req.method,
            url: backendUrl,
            headers: {
                ...req.headers,
                'host': 'localhost:8000'
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

// Serve frontend pages
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
    console.log(`📡 Backend API: http://localhost:8000/api`);
});

module.exports = app;
 