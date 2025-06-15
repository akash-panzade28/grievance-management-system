# 🐳 Docker Setup Guide

## 📋 Quick Docker Setup

This project includes basic Docker configuration files that you can use to containerize the Grievance Management System.

### 📁 Docker Files Included:
- `Dockerfile` - Basic container configuration
- `docker-compose.yml` - Container orchestration setup
- `.dockerignore` - Files to exclude from Docker build

---

## 🚀 Quick Start

### **Option 1: Docker Build & Run**
```bash
# Build the image
docker build -t grievance-management-system .

# Run the container
docker run -d --name grievance-management-system \
  -p 8000:8000 -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  grievance-management-system
```

### **Option 2: Docker Compose**
```bash
# Start with docker-compose
docker-compose up -d

# Stop the services
docker-compose down
```

---

## 🌐 Access URLs

Once running, access the application at:
- **Frontend**: http://localhost:8501
- **API Documentation**: http://localhost:8000/docs
- **Admin Panel**: http://localhost:8501/admin (admin/admin123)

---

## 🔧 Management Commands

```bash
# View logs
docker logs grievance-management-system

# Stop container
docker stop grievance-management-system

# Remove container
docker rm grievance-management-system

# Rebuild after changes
docker build -t grievance-management-system . --no-cache
```

---

## 📦 Container Specifications

- **Base Image**: python:3.11-slim
- **Ports**: 8000 (API), 8501 (Frontend)
- **Volume**: `./data` for database persistence
- **Health Check**: API endpoint monitoring

---

## ⚠️ Notes

- Make sure Docker is installed and running
- The container will automatically initialize the database
- Sample data is included for testing
- Modify the Dockerfile as needed for your specific requirements

---

## 🔧 Customization

You can customize the Docker setup by:
1. Modifying the `Dockerfile` for different base images or dependencies
2. Updating `docker-compose.yml` for different port mappings or environment variables
3. Adding environment variables for configuration

---

**🚀 The Docker files provide a starting point for containerizing the application. Modify them according to your deployment needs!**
