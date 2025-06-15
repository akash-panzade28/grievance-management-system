# 🚀 How to Run the Grievance Management System

## 📋 **STEP-BY-STEP GUIDE**

### **Prerequisites:**
- Python 3.8+ installed
- Terminal/Command Prompt access
- 4GB RAM minimum

---

## 🎯 **OPTION 1: One-Command Start (Recommended)**

### **Step 1: Open Terminal**
```bash
cd "/Users/akash/Documents/Project and Assignments/cyfuture assign1"
```

### **Step 2: Install Dependencies (First Time Only)**
```bash
pip install -r requirements.txt
```

### **Step 3: Start the System**
```bash
python start_system.py
```

### **Step 4: Access the Application**
The system will automatically start both services and display:
```
🎉 SYSTEM STARTED SUCCESSFULLY!
🌐 Frontend URL: http://localhost:8502
🔧 API Documentation: http://127.0.0.1:8000/docs
👨‍💼 Admin Panel: http://localhost:8502/admin
```

---

## 🔧 **OPTION 2: Manual Start (Two Terminals)**

### **Terminal 1 - Start API Server:**
```bash
cd "/Users/akash/Documents/Project and Assignments/cyfuture assign1"
python src/api/api_server.py
```
*Wait for: "Uvicorn running on http://127.0.0.1:8000"*

### **Terminal 2 - Start Frontend:**
```bash
cd "/Users/akash/Documents/Project and Assignments/cyfuture assign1"
streamlit run src/frontend/app.py --server.port 8502
```
*Wait for: "You can now view your Streamlit app in your browser"*

---

## 🌐 **ACCESS URLS**

Once the system is running, open these URLs in your browser:

### **🎨 Main Application:**
```
http://localhost:8502
```
- Register new complaints
- Check complaint status
- Natural language queries

### **👨‍💼 Admin Panel:**
```
http://localhost:8502/admin
```
- **Username:** `admin`
- **Password:** `admin123`
- Manage all complaints (CRUD operations)

### **📚 API Documentation:**
```
http://127.0.0.1:8000/docs
```
- Interactive API documentation
- Test API endpoints directly

---

## 📱 **SAMPLE USAGE**

### **For Users:**

**1. Register Complaint:**
- Go to http://localhost:8502
- Type: "I have a complaint"
- Follow prompts: Name → Mobile → Details

**2. Check Status:**
- Type your mobile number: "9876543210"
- Or type: "Check status CMP12345678"

**3. Natural Language:**
- "My self John give all record complaint register on my name"
- "Show all my complaints"
- "What's the status of my laptop issue?"

### **For Admins:**

**1. Login:**
- Go to http://localhost:8502/admin
- Username: `admin`, Password: `admin123`

**2. Manage Complaints:**
- View all complaints
- Update status (Registered → In Progress → Resolved)
- Delete complaints with confirmation
- Export data to CSV

---

## 🧪 **SAMPLE DATA AVAILABLE**

The system comes with 5 pre-loaded sample complaints:

| Mobile Number | Name | Category | Issue |
|---------------|------|----------|-------|
| 9876543210 | John Doe | Hardware | Laptop screen flickering |
| 8765432109 | Sarah Smith | Software | Login portal issues |
| 7654321098 | Mike Johnson | Network | Slow internet connection |
| 6543210987 | Emily Davis | Other | AC not working |
| 5432109876 | Robert Wilson | Hardware | Printer jamming |

**Test with any of these mobile numbers!**

---

## 🔧 **TROUBLESHOOTING**

### **Problem: Port Already in Use**
```bash
# Kill existing processes
lsof -ti:8502 | xargs kill -9
lsof -ti:8000 | xargs kill -9

# Then restart
python start_system.py
```

### **Problem: Module Not Found**
```bash
# Ensure you're in the correct directory
cd "/Users/akash/Documents/Project and Assignments/cyfuture assign1"

# Install dependencies
pip install -r requirements.txt
```

### **Problem: Database Issues**
```bash
# The database is automatically initialized
# If issues persist, restart the system
```

---

## 🛑 **HOW TO STOP THE SYSTEM**

### **If using start_system.py:**
- Press `Ctrl+C` in the terminal
- System will automatically stop all services

### **If using manual start:**
- Press `Ctrl+C` in both terminals (API and Frontend)

---

## ✅ **VERIFICATION CHECKLIST**

After starting the system, verify:

- [ ] ✅ API Server running: http://127.0.0.1:8000 shows "Grievance Management API"
- [ ] ✅ Frontend accessible: http://localhost:8502 shows the chat interface
- [ ] ✅ Admin panel works: http://localhost:8502/admin accepts admin/admin123
- [ ] ✅ Sample data loaded: Admin panel shows 5 complaints
- [ ] ✅ User interaction: Can type "9876543210" and see John Doe's complaint

---

## 🎯 **QUICK TEST SCENARIOS**

### **Test 1: User Registration**
1. Go to http://localhost:8502
2. Type: "I want to register a complaint"
3. Enter name: "Test User"
4. Enter mobile: "1234567890"
5. Enter details: "Test complaint for verification"
6. Verify complaint is registered

### **Test 2: Admin Management**
1. Go to http://localhost:8502/admin
2. Login with admin/admin123
3. Find the test complaint
4. Update status to "In Progress"
5. Verify status change

### **Test 3: Status Check**
1. Go to http://localhost:8502
2. Type: "1234567890"
3. Verify the test complaint appears with "In Progress" status

---

## 🎉 **SUCCESS INDICATORS**

When everything is working correctly, you should see:

✅ **Terminal Output:**
```
🎉 SYSTEM STARTED SUCCESSFULLY!
🌐 Frontend URL: http://localhost:8502
🔧 API Documentation: http://127.0.0.1:8000/docs
👨‍💼 Admin Panel: http://localhost:8502/admin
```

✅ **Browser Access:**
- Main app loads with chat interface
- Admin panel shows 5 sample complaints
- API docs show all endpoints

✅ **Functionality:**
- Can register new complaints
- Can check status by mobile number
- Admin can update/delete complaints
- Natural language queries work

---

**🚀 The system is now ready for professional use and demonstration!**
