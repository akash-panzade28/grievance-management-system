#!/usr/bin/env python3
"""
Simple script to run the Grievance Management System
"""

import subprocess
import sys
import time
import os

def main():
    print("🎯 GRIEVANCE MANAGEMENT SYSTEM")
    print("=" * 50)
    print("🚀 Starting the system...")
    
    # Change to project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    try:
        # Start the system using the existing start_system.py
        subprocess.run([sys.executable, "start_system.py"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 System stopped by user")
    except FileNotFoundError:
        print("❌ start_system.py not found. Please run from project root directory.")
    except Exception as e:
        print(f"❌ Error starting system: {e}")

if __name__ == "__main__":
    main()
