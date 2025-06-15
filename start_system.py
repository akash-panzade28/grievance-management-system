#!/usr/bin/env python3
"""
Grievance Management System Startup Script
Starts both API server and Streamlit frontend
"""

import subprocess
import time
import sys
import os
import signal
import requests
from threading import Thread

def check_port(port):
    """Check if a port is available"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result != 0

def wait_for_server(url, timeout=30):
    """Wait for server to be ready"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False

def start_api_server():
    """Start the FastAPI server"""
    print("🚀 Starting API Server...")
    
    # Change to project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    # Start API server
    api_process = subprocess.Popen([
        sys.executable, "src/api/api_server.py"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for API to be ready
    if wait_for_server("http://127.0.0.1:8000", timeout=30):
        print("✅ API Server started successfully on http://127.0.0.1:8000")
        return api_process
    else:
        print("❌ API Server failed to start")
        api_process.terminate()
        return None

def start_streamlit_app():
    """Start the Streamlit app"""
    print("🎨 Starting Streamlit Frontend...")
    
    # Find available port
    port = 8501
    while not check_port(port) and port < 8510:
        port += 1
    
    if port >= 8510:
        print("❌ No available ports for Streamlit")
        return None
    
    # Start Streamlit
    streamlit_process = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", 
        "src/frontend/app.py", 
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for Streamlit to be ready
    if wait_for_server(f"http://localhost:{port}", timeout=30):
        print(f"✅ Streamlit Frontend started successfully on http://localhost:{port}")
        return streamlit_process, port
    else:
        print("❌ Streamlit Frontend failed to start")
        streamlit_process.terminate()
        return None, None

def initialize_database():
    """Initialize the database"""
    print("💾 Initializing Database...")
    try:
        sys.path.append('src')
        from database.database import DatabaseManager
        
        db = DatabaseManager()
        db.init_database()
        print("✅ Database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

def main():
    """Main startup function"""
    print("=" * 80)
    print("🎯 GRIEVANCE MANAGEMENT SYSTEM")
    print("🚀 Professional AI-Powered Complaint Management")
    print("=" * 80)
    
    # Initialize database
    if not initialize_database():
        print("❌ Cannot start system without database")
        return
    
    processes = []
    
    try:
        # Start API server
        api_process = start_api_server()
        if not api_process:
            print("❌ Failed to start API server")
            return
        processes.append(api_process)
        
        # Start Streamlit app
        streamlit_result = start_streamlit_app()
        if streamlit_result[0] is None:
            print("❌ Failed to start Streamlit frontend")
            return
        
        streamlit_process, port = streamlit_result
        processes.append(streamlit_process)
        
        print("\n" + "=" * 80)
        print("🎉 SYSTEM STARTED SUCCESSFULLY!")
        print("=" * 80)
        print(f"🌐 Frontend URL: http://localhost:{port}")
        print(f"🔧 API Documentation: http://127.0.0.1:8000/docs")
        print(f"👨‍💼 Admin Panel: http://localhost:{port}/admin")
        print("\n📋 Default Admin Credentials:")
        print("   Username: admin")
        print("   Password: admin123")
        print("\n🔄 System Features:")
        print("   ✅ AI-Powered Complaint Processing")
        print("   ✅ Mobile Number-Based Search")
        print("   ✅ Real-time Status Updates")
        print("   ✅ Professional Admin Dashboard")
        print("   ✅ Context-Aware Responses")
        print("   ✅ RAG-Enhanced Knowledge Base")
        print("\n⚠️  Press Ctrl+C to stop all services")
        print("=" * 80)
        
        # Keep running until interrupted
        try:
            while True:
                time.sleep(1)
                # Check if processes are still running
                for process in processes:
                    if process.poll() is not None:
                        print("⚠️  A service has stopped unexpectedly")
                        break
        except KeyboardInterrupt:
            print("\n🛑 Shutting down services...")
            
    except Exception as e:
        print(f"❌ Error starting system: {e}")
    
    finally:
        # Clean up processes
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                try:
                    process.kill()
                except:
                    pass
        
        print("✅ All services stopped")

if __name__ == "__main__":
    main()
