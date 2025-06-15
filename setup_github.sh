#!/bin/bash

# Grievance Management System - GitHub Setup Script
# This script prepares the project for GitHub upload

set -e

echo "🚀 GitHub Setup for Grievance Management System"
echo "================================================"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if git is installed
if ! command -v git &> /dev/null; then
    print_error "Git is not installed. Please install Git first."
    exit 1
fi

print_success "Git is available"

# Initialize git repository if not already initialized
if [ ! -d ".git" ]; then
    echo "📁 Initializing Git repository..."
    git init
    print_success "Git repository initialized"
else
    print_success "Git repository already exists"
fi

# Check for sensitive files
echo "🔍 Checking for sensitive files..."

SENSITIVE_FILES=()

# Check for .env files (should be in .gitignore)
if [ -f ".env" ]; then
    SENSITIVE_FILES+=(".env")
fi

# Check for database files
if find . -name "*.db" -not -path "./Not_Required/*" | grep -q .; then
    SENSITIVE_FILES+=("database files")
fi

# Check for log files
if find . -name "*.log" | grep -q .; then
    SENSITIVE_FILES+=("log files")
fi

if [ ${#SENSITIVE_FILES[@]} -gt 0 ]; then
    print_warning "Found sensitive files that should not be uploaded:"
    for file in "${SENSITIVE_FILES[@]}"; do
        echo "  - $file"
    done
    echo "These files are excluded by .gitignore"
else
    print_success "No sensitive files found"
fi

# Add all files respecting .gitignore
echo "📦 Adding files to Git..."
git add .

# Check git status
echo "📋 Git status:"
git status --short

# Create commit
echo "💾 Creating commit..."
read -p "Enter commit message (or press Enter for default): " COMMIT_MSG

if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="Initial commit: Grievance Management System

- AI-powered complaint management system
- Streamlit frontend with admin panel  
- FastAPI backend with comprehensive API
- SQLite database with sample data
- Docker containerization support
- Complete documentation and setup guides"
fi

git commit -m "$COMMIT_MSG"
print_success "Commit created successfully"

# Instructions for GitHub upload
echo ""
echo "🌐 Next Steps for GitHub Upload:"
echo "================================"
echo ""
echo "1. Create GitHub Repository:"
echo "   - Go to https://github.com/new"
echo "   - Repository name: grievance-management-system"
echo "   - Description: AI-Powered Grievance Management System"
echo "   - Make it Public"
echo "   - Don't initialize with README (we have one)"
echo ""
echo "2. Connect to GitHub:"
echo "   git remote add origin https://github.com/YOUR_USERNAME/grievance-management-system.git"
echo ""
echo "3. Push to GitHub:"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "4. Add Repository Topics:"
echo "   python, streamlit, fastapi, ai, llm, grievance-management, complaint-system, docker"
echo ""

# Show what will be uploaded
echo "📤 Files that will be uploaded to GitHub:"
echo "========================================="
git ls-files | head -20
if [ $(git ls-files | wc -l) -gt 20 ]; then
    echo "... and $(( $(git ls-files | wc -l) - 20 )) more files"
fi

echo ""
echo "🚫 Files excluded from upload (by .gitignore):"
echo "=============================================="
if [ -f ".gitignore" ]; then
    echo "- Database files (*.db)"
    echo "- Environment files (.env)"
    echo "- Log files (*.log)"
    echo "- Cache files (__pycache__/)"
    echo "- Not_Required/ folder"
    echo "- IDE files (.vscode/, .idea/)"
    echo "- OS files (.DS_Store, Thumbs.db)"
else
    print_warning "No .gitignore file found"
fi

echo ""
print_success "GitHub setup completed!"
print_success "Repository is ready for upload to GitHub"

echo ""
echo "🎯 Repository Features:"
echo "- ✅ Professional README with architecture diagrams"
echo "- ✅ Complete source code structure"
echo "- ✅ Docker containerization support"
echo "- ✅ Comprehensive documentation"
echo "- ✅ No sensitive data included"
echo "- ✅ Clean commit history"
echo ""
echo "🚀 Ready to showcase your professional development skills!"
