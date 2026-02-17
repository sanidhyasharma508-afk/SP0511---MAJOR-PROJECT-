# 🚀 Multiple Agent Project - Deployment Guide

**Project**: Campus Automation - Multiple Agent System  
**Version**: 1.0  
**Date**: January 22, 2026

---

## 📋 Deployment Overview

This guide covers deploying the complete Multiple Agent Project with all frontend and backend agents to different environments.

---

## 🎯 Deployment Levels

```
Development       → Local machine with npm/python
Staging          → Pre-production testing environment
Production       → Live public system
Disaster Recovery→ Failover system
```

---

## 🔧 Development Deployment

### Quick Setup (5 minutes)

```bash
# 1. Clone or navigate to project
cd c:/campus\ automation

# 2. Install backend dependencies
cd backend
pip install -r requirements.txt

# 3. Install frontend dependencies
cd ../frontend
npm install

# 4. Create .env file
cd ..
cp .env.template .env

# Edit .env:
# - ENV=development
# - DATABASE_URL=sqlite:///./test.db
# - SECRET_KEY=dev-secret-key
# - ALLOWED_ORIGINS=http://localhost:3000
```

### Start Development Servers

**Terminal 1 - Backend Agents:**
```bash
cd backend
python -m uvicorn backend.main:app --reload --port 8000 --host 127.0.0.1
```

**Terminal 2 - Frontend Agents:**
```bash
cd frontend
npm start
```

**Access Points:**
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/health

---

## 🧪 Staging Deployment

### Environment Configuration

```bash
# .env for staging
ENV=staging
DEBUG=False
DATABASE_URL=postgresql://user:pass@staging-db:5432/campus
SECRET_KEY=your-strong-staging-key-change-this
ALLOWED_ORIGINS=https://staging.example.com,http://localhost:3000
REDIS_URL=redis://staging-redis:6379/0
```

### Deploy Backend Agents

```bash
# 1. Build Docker image (if using containers)
docker build -f backend/Dockerfile -t campus-backend:staging .

# 2. Run container
docker run -d \
  --name campus-backend-staging \
  -p 8000:8000 \
  -e ENV=staging \
  -e DATABASE_URL=postgresql://... \
  campus-backend:staging

# 3. Or use: Gunicorn with multiple workers
gunicorn \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 60 \
  backend.main:app
```

### Deploy Frontend Agents

```bash
# 1. Build frontend
cd frontend
npm install
npm run build  # if applicable

# 2. Deploy to static host or run Node server
node server.js

# 3. Or deploy to CDN:
# - Upload stitch_student_attendance/ to S3
# - Configure CloudFront distribution
# - Point domain to CDN
```

### Verify Agents

```bash
# Health checks
curl https://staging.example.com/api/health
curl https://staging-api.example.com/health

# Agent status
curl https://staging.example.com/api/agents/status
```

---

## 🌍 Production Deployment

### Security Checklist

```bash
# 1. Change all secrets
❌ SECRET_KEY = "your-secret-key-change-in-production"
✅ SECRET_KEY = "$(openssl rand -hex 32)"

# 2. Change all passwords
❌ Default database password
✅ Strong random password from password manager

# 3. Enable HTTPS
❌ http://example.com
✅ https://example.com (with SSL certificate)

# 4. Restrict CORS origins
❌ ALLOWED_ORIGINS=*
✅ ALLOWED_ORIGINS=https://example.com

# 5. Set debug to false
❌ DEBUG=True
✅ DEBUG=False

# 6. Use production database
❌ SQLite
✅ PostgreSQL or MySQL

# 7. Set up logging
✅ Configure centralized logging (ELK, CloudWatch)

# 8. Set up monitoring
✅ Configure alerts (Datadog, New Relic)

# 9. Set up backups
✅ Automated database backups
✅ Automated code backups
```

### Production Configuration

```bash
# .env for production
ENV=production
DEBUG=False
HOST=0.0.0.0
PORT=8000
API_PREFIX=/api

# Database (PostgreSQL)
DATABASE_URL=postgresql://prod_user:strong_password@prod-db.region.rds.amazonaws.com:5432/campus_prod
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Security
SECRET_KEY=very-strong-random-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
ALLOWED_ORIGINS=https://campus.example.com,https://api.campus.example.com
ALLOWED_METHODS=GET,POST,PUT,DELETE,PATCH,OPTIONS
ALLOWED_HEADERS=Content-Type,Authorization

# Logging
LOG_LEVEL=WARNING
LOG_FILE=/var/log/campus/app.log

# Caching (Redis)
REDIS_URL=redis://prod-redis.region.cache.amazonaws.com:6379/0
CACHE_TTL=3600

# Background Jobs
CELERY_BROKER_URL=redis://prod-redis.region.cache.amazonaws.com:6379/1
CELERY_RESULT_BACKEND=redis://prod-redis.region.cache.amazonaws.com:6379/2

# Email Notifications
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=notifications@example.com
SMTP_PASSWORD=app-specific-password

# Feature Flags
ENABLE_CACHING=True
ENABLE_BACKGROUND_TASKS=True
ENABLE_EMAIL_NOTIFICATIONS=True
ENABLE_METRICS=True

# Performance
MAX_POOL_SIZE=20
WORKER_THREADS=8
REQUEST_TIMEOUT=30
METRICS_PORT=9090
```

### Multi-Agent Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Internet / Users                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│         CloudFront / CDN (Static Assets)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│    Load Balancer (AWS ELB / Nginx)                         │
│    ├─ HTTPS/SSL Termination                               │
│    ├─ Request routing                                      │
│    └─ Session affinity                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
    ┌───▼──┐      ┌────▼───┐    ┌───▼──┐
    │ Pod1 │      │ Pod2   │    │ Pod3 │  Frontend Agents
    │ Port │      │ Port   │    │ Port │  (Express.js)
    │ 3000 │      │ 3000   │    │ 3000 │
    └───┬──┘      └────┬───┘    └───┬──┘
        │              │              │
        └──────────────┼──────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
    ┌───▼──┐      ┌────▼───┐    ┌───▼──┐
    │ Pod1 │      │ Pod2   │    │ Pod3 │  Backend Agents
    │ Port │      │ Port   │    │ Port │  (FastAPI)
    │ 8000 │      │ 8000   │    │ 8000 │
    └───┬──┘      └────┬───┘    └───┬──┘
        │              │              │
        └──────────────┼──────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
    ┌───▼──────────────▼─────────────▼──┐
    │   PostgreSQL (Primary)             │
    │   - Student data                   │
    │   - Attendance records             │
    │   - Club information               │
    └────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
    ┌───▼──┐      ┌────▼───┐    ┌───▼──┐
    │Redis │      │Redis   │    │Redis  │  Cache Layer
    │Cache │      │Queue   │    │Events │  (Replication)
    └──────┘      └────────┘    └───────┘
```

### Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: campus-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: campus-backend
  template:
    metadata:
      labels:
        app: campus-backend
    spec:
      containers:
      - name: backend
        image: campus-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENV
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: campus-secrets
              key: database-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: campus-backend-service
spec:
  type: LoadBalancer
  selector:
    app: campus-backend
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
```

### Docker Deployment

**Backend Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/ .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend Dockerfile:**
```dockerfile
FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY frontend/package*.json ./
RUN npm ci --only=production

# Copy application
COPY frontend/ .

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:3000/health || exit 1

# Run application
CMD ["node", "server.js"]
```

---

## 📊 Monitoring & Logging

### Centralized Logging

```bash
# ELK Stack (Elasticsearch, Logstash, Kibana)
# or CloudWatch / Datadog

# Configure in backend:
LOG_LEVEL=INFO
LOG_FILE=/var/log/campus/app.log

# All agents log to:
- Console (stdout/stderr)
- File system (/var/log/campus/)
- Centralized service
```

### Metrics Collection

```bash
# Prometheus metrics on port 9090
GET http://localhost:9090/metrics

# Tracks:
- Request count
- Response times
- Error rates
- Agent health
- Database performance
- Cache hit rate
```

### Health Checks

```bash
# Agent health endpoint
GET /api/health

Response:
{
  "status": "healthy",
  "agents": {
    "auth": "ready",
    "students": "ready",
    "attendance": "ready",
    "database": "connected",
    "cache": "connected"
  },
  "timestamp": "2024-01-22T10:30:00Z"
}
```

---

## 🔄 Blue-Green Deployment

```
1. Current Production (Blue)
   └─ Running version 1.0
   
2. Deploy New Version (Green)
   └─ Deploy version 2.0 alongside
   
3. Test Green Environment
   └─ Run integration tests
   
4. Switch Traffic
   └─ Load balancer routes to Green
   
5. Keep Blue as Rollback
   └─ If issues, switch back to Blue
   
6. Cleanup
   └─ After stable, remove Blue
```

---

## 🔙 Rollback Procedure

```bash
# If production deployment fails:

# 1. Identify issue
curl https://api.example.com/api/health

# 2. Switch to previous version
# - Update Docker image tag
# - Redeploy with previous version
# - Update load balancer

# 3. Verify rollback
curl https://api.example.com/api/health

# 4. Investigate issue
- Review logs
- Check database migrations
- Verify configuration

# 5. Fix and redeploy
# - Apply fix to code
# - Run tests
# - Deploy again
```

---

## 📈 Scaling Agents

### Horizontal Scaling

```bash
# Add more pod replicas
kubectl scale deployment campus-backend --replicas=5

# Load balancer distributes traffic:
Request 1 → Pod 1 (Auth Agent)
Request 2 → Pod 2 (Student Agent)
Request 3 → Pod 3 (Attendance Agent)
Request 4 → Pod 4 (Analytics Agent)
Request 5 → Pod 5 (AI Agent)
```

### Vertical Scaling

```bash
# Increase resources per pod
- Increase CPU (500m → 1000m)
- Increase Memory (1Gi → 2Gi)
- Upgrade to larger node types
```

### Agent-Specific Scaling

```
If specific agents bottleneck:
- Auth Agent: Scale to 2-3 replicas
- Student Agent: Scale to 3-4 replicas
- AI Agent: Scale with GPU nodes
- Cache Agent: Use Redis Cluster
- Event Bus: Use Message Queue
```

---

## 🔐 Security Hardening

```bash
# SSL/TLS Certificates
- Use Let's Encrypt or AWS ACM
- Auto-renew certificates
- Enforce HTTPS only

# Network Security
- VPC with private subnets
- Security groups restrict access
- WAF (Web Application Firewall)

# Database Security
- Encrypted connections
- Encrypted at rest
- Isolated network
- Regular backups

# Application Security
- Secret management (HashiCorp Vault)
- API rate limiting
- Input validation
- Output encoding
- CSRF protection
```

---

## 🚨 Disaster Recovery

### Backup Strategy

```bash
# Database Backups
- Daily full backups
- Hourly incremental backups
- Encrypted storage
- Cross-region replication

# Code Backups
- Git repository
- Multiple remotes
- Tagged releases
- Archived versions

# Configuration Backups
- .env files (encrypted)
- Kubernetes manifests
- Docker images (registry)
```

### Recovery Plan

```bash
# RTO (Recovery Time Objective): 4 hours
# RPO (Recovery Point Objective): 1 hour

1. Failure detected
   └─ Monitoring alerts triggered

2. Assess damage
   └─ Determine what failed

3. Restore infrastructure
   └─ Spin up new instances

4. Restore data
   └─ Restore from latest backup

5. Restore configuration
   └─ Apply previous settings

6. Verify agents
   └─ Run health checks

7. Resume operations
   └─ Route traffic back
```

---

## ✅ Deployment Checklist

### Pre-Deployment
- [ ] Code reviewed and tested
- [ ] All agents functional
- [ ] Database migrations prepared
- [ ] Backups created
- [ ] Security patches applied
- [ ] Configuration ready
- [ ] Team notified
- [ ] Rollback plan ready

### Deployment
- [ ] Deploy database agents
- [ ] Deploy backend agents
- [ ] Verify backend health
- [ ] Deploy frontend agents
- [ ] Verify frontend health
- [ ] Run integration tests
- [ ] Load testing
- [ ] Security scanning

### Post-Deployment
- [ ] Monitor logs
- [ ] Check alerts
- [ ] Verify all endpoints
- [ ] Test user workflows
- [ ] Performance review
- [ ] Document changes
- [ ] Team debriefing

---

## 📞 Support & Monitoring

### On-Call Procedures

```
If alert triggered:
1. Check monitoring dashboard
2. Review logs in centralized logging
3. Check agent health endpoints
4. Verify database connectivity
5. Check external dependencies
6. Escalate if critical
7. Start incident response
```

### Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| High latency | Too many requests | Scale horizontally |
| Database locked | Long transactions | Kill long queries |
| Cache miss | Memory pressure | Clear cache, increase size |
| Agent timeout | Slow dependency | Check external services |
| Memory leak | Agent issue | Restart pod |

---

## 🎯 Summary

The Multiple Agent Project deployment includes:

✅ **Development Setup** - Quick local setup (5 min)  
✅ **Staging Environment** - Pre-production testing  
✅ **Production Deployment** - High availability setup  
✅ **Kubernetes Ready** - Container orchestration  
✅ **Monitoring & Logging** - Full observability  
✅ **Disaster Recovery** - Backup and restore  
✅ **Scaling Strategy** - Horizontal & vertical  
✅ **Security Hardening** - Production-grade security  

All agents work together seamlessly across all deployment levels.

---

**Document Version**: 1.0  
**Last Updated**: January 22, 2026  
**Status**: Production Ready
