# 📊 Database Directory

## 💾 Database Files

This directory contains the SQLite database files for the Grievance Management System.

### 📁 Contents:
- `grievance_system.db` - Main application database (auto-generated)

### 🔄 Auto-Generation:
The database file is automatically created when you first run the system:
```bash
python start_system.py
```

### 📋 Database Schema:
- **complaints** - Main complaints table
- **status_history** - Status change tracking
- **users** - User information (if applicable)

### 🧪 Sample Data:
The system automatically creates 5 sample complaints for testing:
1. John Doe - Hardware issue
2. Sarah Smith - Software issue  
3. Mike Johnson - Network issue
4. Emily Davis - Other issue
5. Robert Wilson - Hardware issue

### ⚠️ Note:
Database files are excluded from Git repository for security and size reasons. The database will be automatically initialized on first run.
