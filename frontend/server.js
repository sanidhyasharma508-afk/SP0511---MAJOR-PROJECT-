const express = require('express');
const cors = require('cors');
const path = require('path');
const http = require('http');
require('dotenv').config();

const app = express();
const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

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

// Proxy middleware to forward requests to backend
const axios = require('axios');

// Forward API requests to backend
app.all('/api/*', async (req, res) => {
    try {
        const backendPath = req.path.startsWith('/api/v1/')
            ? req.path
            : req.path.replace(/^\/api(?=\/|$)/, '');
        
        const proxyHeaders = { ...req.headers, host: new URL(backendUrl).host };
        delete proxyHeaders['content-length'];

        const config = {
            method: req.method,
            url: `${backendUrl}${backendPath}`,
            headers: proxyHeaders
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
        const status = error.response?.status || 500;
        const errorDetail = error.response?.data?.detail || error.response?.data?.message || error.message;
        const message = typeof errorDetail === 'string' 
            ? errorDetail 
            : (Array.isArray(errorDetail) ? errorDetail.map(d => d.msg || d).join(', ') : JSON.stringify(errorDetail));
        
        console.error(`API Error [${req.method} ${req.path} -> ${status}]:`, message);
        res.status(status).json({
            status: 'error',
            detail: errorDetail,
            message: message
        });
    }
});

// Serve frontend pages
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

app.get('/attendance', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_student_attendance', 'student_attendance', 'code.html'));
});

app.get('/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_student_attendance', 'student_performance_dashboard', 'code.html'));
});

app.get('/clubs', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_student_attendance', 'club_information', 'code.html'));
});

app.get('/events', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_student_attendance', 'events_hub', 'code.html'));
});

app.get('/timetable', (req, res) => {
    res.sendFile(path.join(__dirname, 'stitch_student_attendance', 'timetable_&_holidays', 'code.html'));
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
    console.log(`📡 Backend API: ${backendUrl}`);
});

module.exports = app;
 