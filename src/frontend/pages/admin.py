#!/usr/bin/env python3
"""
Admin Dashboard for Grievance Management System
Provides comprehensive admin interface for managing complaints
"""

import streamlit as st
import sqlite3
import pandas as pd
import requests
import json
import time
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Any

# Page configuration
st.set_page_config(
    page_title="Admin Dashboard - Grievance Management",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database connection
def get_db_connection():
    """Get database connection"""
    import os
    # Look for database in data directory
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'grievance_system.db')
    if not os.path.exists(db_path):
        # Fallback to current directory
        db_path = 'grievance_system.db'
    return sqlite3.connect(db_path)

# API endpoints
API_BASE_URL = "http://127.0.0.1:8000"

def check_api_server():
    """Check if API server is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        return response.status_code == 200
    except:
        return False

def update_complaint_status(complaint_id: str, new_status: str) -> Dict[str, Any]:
    """Update complaint status via API"""
    try:
        response = requests.put(
            f"{API_BASE_URL}/admin/complaint/{complaint_id}/status",
            json={"status": new_status},
            timeout=10
        )

        if response.status_code == 200:
            return {"success": True, "message": "Status updated successfully"}
        elif response.status_code == 404:
            return {"success": False, "message": "Complaint not found"}
        else:
            return {"success": False, "message": f"Server error: {response.status_code}"}

    except requests.exceptions.Timeout:
        return {"success": False, "message": "Request timeout"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Connection error"}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

def delete_complaint(complaint_id: str) -> Dict[str, Any]:
    """Delete complaint via API"""
    try:
        response = requests.delete(f"{API_BASE_URL}/admin/complaint/{complaint_id}", timeout=10)

        if response.status_code == 200:
            return {"success": True, "message": "Complaint deleted successfully"}
        elif response.status_code == 404:
            return {"success": False, "message": "Complaint not found"}
        else:
            return {"success": False, "message": f"Server error: {response.status_code}"}

    except requests.exceptions.Timeout:
        return {"success": False, "message": "Request timeout"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Connection error"}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

def get_all_complaints() -> List[Dict]:
    """Get all complaints from database"""
    try:
        conn = get_db_connection()
        query = """
        SELECT complaint_id, name, mobile, complaint_details, category, status, 
               created_at, updated_at 
        FROM complaints 
        ORDER BY created_at DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df.to_dict('records')
    except Exception as e:
        st.error(f"Database error: {e}")
        return []

def get_complaint_stats() -> Dict:
    """Get complaint statistics"""
    try:
        conn = get_db_connection()
        
        # Total complaints
        total_query = "SELECT COUNT(*) as total FROM complaints"
        total_result = pd.read_sql_query(total_query, conn)
        total_complaints = total_result['total'].iloc[0]
        
        # Status distribution
        status_query = "SELECT status, COUNT(*) as count FROM complaints GROUP BY status"
        status_df = pd.read_sql_query(status_query, conn)
        
        # Category distribution
        category_query = "SELECT category, COUNT(*) as count FROM complaints GROUP BY category"
        category_df = pd.read_sql_query(category_query, conn)
        
        # Recent complaints (last 7 days)
        recent_query = """
        SELECT COUNT(*) as recent 
        FROM complaints 
        WHERE created_at >= datetime('now', '-7 days')
        """
        recent_result = pd.read_sql_query(recent_query, conn)
        recent_complaints = recent_result['recent'].iloc[0]
        
        conn.close()
        
        return {
            "total": total_complaints,
            "recent": recent_complaints,
            "status_distribution": status_df.to_dict('records'),
            "category_distribution": category_df.to_dict('records')
        }
    except Exception as e:
        st.error(f"Statistics error: {e}")
        return {"total": 0, "recent": 0, "status_distribution": [], "category_distribution": []}

def check_admin_auth():
    """Check admin authentication"""
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        st.markdown("""
        <div class="admin-header">
            <h1 style="margin: 0; font-size: 2.5rem; font-weight: 300;">Admin Login</h1>
            <p style="font-size: 1.1rem; margin: 0.5rem 0 0 0; opacity: 0.9;">Secure Access Required</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("admin_login"):
            st.markdown("### 🔐 Administrator Login")
            admin_id = st.text_input("Admin ID", placeholder="Enter admin username")
            admin_pass = st.text_input("Password", type="password", placeholder="Enter password")

            col1, col2 = st.columns([1, 2])
            with col1:
                login_button = st.form_submit_button("🔑 Login", use_container_width=True)

            if login_button:
                # Default credentials (in production, use secure authentication)
                if admin_id == "admin" and admin_pass == "admin123":
                    st.session_state.admin_authenticated = True
                    st.success("✅ Login successful! Redirecting...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials. Please try again.")
                    st.info("💡 Default credentials: admin / admin123")

        st.markdown("---")
        st.markdown("### 🔒 Security Notice")
        st.info("This admin panel provides access to sensitive complaint data. Only authorized personnel should access this area.")

        return False

    return True

def main():
    """Main admin dashboard"""

    # Check authentication first
    if not check_admin_auth():
        return

    # Custom CSS for admin dashboard
    st.markdown("""
    <style>
    .main .block-container {
        padding: 1rem 2rem;
        max-width: 1400px;
    }
    
    .admin-header {
        background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }
    
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-left: 4px solid #e74c3c;
        margin: 1rem 0;
    }
    
    .status-badge {
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 500;
        color: white;
    }
    
    .status-registered { background-color: #3498db; }
    .status-in-progress { background-color: #f39c12; }
    .status-resolved { background-color: #27ae60; }
    .status-closed { background-color: #95a5a6; }
    .status-rejected { background-color: #e74c3c; }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="admin-header">
        <h1 style="margin: 0; font-size: 2.5rem; font-weight: 300;">Admin Dashboard</h1>
        <p style="font-size: 1.1rem; margin: 0.5rem 0 0 0; opacity: 0.9;">Grievance Management System</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Check API status
    api_status = check_api_server()
    if not api_status:
        st.error("⚠️ API Server is offline. Some features may not work properly.")
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("### Navigation")
        page = st.selectbox(
            "Select Page",
            ["Dashboard", "Manage Complaints", "Analytics", "System Settings"]
        )
        
        st.markdown("### Quick Stats")
        stats = get_complaint_stats()
        st.metric("Total Complaints", stats["total"])
        st.metric("Recent (7 days)", stats["recent"])
        
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()
        
        if st.button("🏠 Back to Chat", use_container_width=True):
            st.switch_page("app.py")

        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            st.session_state.admin_authenticated = False
            st.rerun()
    
    # Main content based on selected page
    if page == "Dashboard":
        show_dashboard(stats)
    elif page == "Manage Complaints":
        show_complaint_management()
    elif page == "Analytics":
        show_analytics(stats)
    elif page == "System Settings":
        show_system_settings()

def show_dashboard(stats: Dict):
    """Show main dashboard"""
    st.markdown("## Dashboard Overview")
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Complaints",
            value=stats["total"],
            delta=f"+{stats['recent']} this week"
        )
    
    with col2:
        resolved_count = sum(s['count'] for s in stats["status_distribution"] if s['status'] == 'Resolved')
        st.metric(
            label="Resolved",
            value=resolved_count,
            delta=f"{(resolved_count/max(stats['total'], 1)*100):.1f}% resolution rate"
        )
    
    with col3:
        in_progress_count = sum(s['count'] for s in stats["status_distribution"] if s['status'] == 'In Progress')
        st.metric(
            label="In Progress",
            value=in_progress_count
        )
    
    with col4:
        pending_count = sum(s['count'] for s in stats["status_distribution"] if s['status'] == 'Registered')
        st.metric(
            label="Pending",
            value=pending_count
        )
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Status Distribution")
        if stats["status_distribution"]:
            status_df = pd.DataFrame(stats["status_distribution"])
            fig = px.pie(status_df, values='count', names='status', 
                        color_discrete_sequence=px.colors.qualitative.Set3)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### Category Distribution")
        if stats["category_distribution"]:
            category_df = pd.DataFrame(stats["category_distribution"])
            fig = px.bar(category_df, x='category', y='count',
                        color='count', color_continuous_scale='Blues')
            st.plotly_chart(fig, use_container_width=True)
    
    # Recent complaints
    st.markdown("### Recent Complaints")
    complaints = get_all_complaints()
    if complaints:
        recent_complaints = complaints[:5]  # Show last 5
        for complaint in recent_complaints:
            with st.expander(f"🎫 {complaint['complaint_id']} - {complaint['name']}"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**Mobile:** {complaint['mobile']}")
                    st.write(f"**Category:** {complaint['category']}")
                    st.write(f"**Details:** {complaint['complaint_details'][:100]}...")
                with col2:
                    st.write(f"**Status:** {complaint['status']}")
                    st.write(f"**Created:** {complaint['created_at'][:10]}")

def show_complaint_management():
    """Show complaint management interface"""
    st.markdown("## Complaint Management")

    # Add refresh button and stats
    col1, col2, col3 = st.columns([1, 2, 3])
    with col1:
        if st.button("🔄 Refresh Data"):
            st.rerun()

    complaints = get_all_complaints()

    with col2:
        st.write(f"**Total Complaints:** {len(complaints)}")

    with col3:
        # API Status indicator
        if check_api_server():
            st.success("🟢 API Connected")
        else:
            st.error("🔴 API Disconnected")
    
    if not complaints:
        st.info("No complaints found in the system.")
        return
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All"] + list(set(c['status'] for c in complaints))
        )
    
    with col2:
        category_filter = st.selectbox(
            "Filter by Category", 
            ["All"] + list(set(c['category'] for c in complaints))
        )
    
    with col3:
        search_term = st.text_input("Search by ID or Name")
    
    # Apply filters
    filtered_complaints = complaints
    if status_filter != "All":
        filtered_complaints = [c for c in filtered_complaints if c['status'] == status_filter]
    if category_filter != "All":
        filtered_complaints = [c for c in filtered_complaints if c['category'] == category_filter]
    if search_term:
        filtered_complaints = [c for c in filtered_complaints 
                             if search_term.lower() in c['complaint_id'].lower() 
                             or search_term.lower() in c['name'].lower()]
    
    st.markdown(f"### Showing {len(filtered_complaints)} complaints")
    
    # Complaints table with actions
    for complaint in filtered_complaints:
        with st.expander(f"🎫 {complaint['complaint_id']} - {complaint['name']} - {complaint['status']}"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**Mobile:** {complaint['mobile']}")
                st.write(f"**Category:** {complaint['category']}")
                st.write(f"**Created:** {complaint['created_at']}")
                st.write(f"**Details:** {complaint['complaint_details']}")
            
            with col2:
                st.write("**Actions:**")
                
                # Status update
                new_status = st.selectbox(
                    "Update Status",
                    ["Registered", "In Progress", "Under Review", "Resolved", "Closed", "Rejected"],
                    index=["Registered", "In Progress", "Under Review", "Resolved", "Closed", "Rejected"].index(complaint['status']),
                    key=f"status_{complaint['complaint_id']}"
                )
                
                if st.button("Update Status", key=f"update_{complaint['complaint_id']}"):
                    result = update_complaint_status(complaint['complaint_id'], new_status)
                    if result["success"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(f"Failed to update status: {result['message']}")

                # Delete with confirmation
                if st.button("🗑️ Delete", key=f"delete_{complaint['complaint_id']}", type="secondary"):
                    # Store the complaint ID for confirmation
                    st.session_state[f"confirm_delete_{complaint['complaint_id']}"] = True

                # Show confirmation dialog if delete was clicked
                if st.session_state.get(f"confirm_delete_{complaint['complaint_id']}", False):
                    st.warning(f"⚠️ Are you sure you want to delete complaint {complaint['complaint_id']}?")
                    col_yes, col_no = st.columns(2)

                    with col_yes:
                        if st.button("✅ Yes, Delete", key=f"confirm_yes_{complaint['complaint_id']}"):
                            result = delete_complaint(complaint['complaint_id'])
                            if result["success"]:
                                st.success(result["message"])
                                # Clear confirmation state
                                if f"confirm_delete_{complaint['complaint_id']}" in st.session_state:
                                    del st.session_state[f"confirm_delete_{complaint['complaint_id']}"]
                                st.rerun()
                            else:
                                st.error(f"Failed to delete complaint: {result['message']}")

                    with col_no:
                        if st.button("❌ Cancel", key=f"confirm_no_{complaint['complaint_id']}"):
                            # Clear confirmation state
                            if f"confirm_delete_{complaint['complaint_id']}" in st.session_state:
                                del st.session_state[f"confirm_delete_{complaint['complaint_id']}"]
                            st.rerun()

def show_analytics(stats: Dict):
    """Show analytics page"""
    st.markdown("## Analytics & Reports")
    
    # Time-based analysis
    try:
        conn = get_db_connection()
        
        # Daily complaints for last 30 days
        daily_query = """
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM complaints 
        WHERE created_at >= datetime('now', '-30 days')
        GROUP BY DATE(created_at)
        ORDER BY date
        """
        daily_df = pd.read_sql_query(daily_query, conn)
        
        if not daily_df.empty:
            st.markdown("### Daily Complaints (Last 30 Days)")
            fig = px.line(daily_df, x='date', y='count', title="Complaint Trends")
            st.plotly_chart(fig, use_container_width=True)
        
        # Status timeline
        status_timeline_query = """
        SELECT status, DATE(updated_at) as date, COUNT(*) as count
        FROM complaints
        WHERE updated_at >= datetime('now', '-30 days')
        GROUP BY status, DATE(updated_at)
        ORDER BY date
        """
        status_timeline_df = pd.read_sql_query(status_timeline_query, conn)
        
        if not status_timeline_df.empty:
            st.markdown("### Status Changes Over Time")
            fig = px.bar(status_timeline_df, x='date', y='count', color='status',
                        title="Status Distribution Over Time")
            st.plotly_chart(fig, use_container_width=True)
        
        conn.close()
        
    except Exception as e:
        st.error(f"Analytics error: {e}")

def show_system_settings():
    """Show system settings"""
    st.markdown("## System Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Database Management")
        
        if st.button("🔄 Backup Database"):
            st.info("Database backup functionality would be implemented here")
        
        if st.button("🧹 Clean Old Records"):
            st.info("Old record cleanup functionality would be implemented here")
        
        if st.button("📊 Export Data"):
            complaints = get_all_complaints()
            if complaints:
                df = pd.DataFrame(complaints)
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"complaints_export_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
    
    with col2:
        st.markdown("### System Status")
        
        api_status = check_api_server()
        if api_status:
            st.success("✅ API Server: Online")
        else:
            st.error("❌ API Server: Offline")
        
        # Database status
        try:
            conn = get_db_connection()
            conn.close()
            st.success("✅ Database: Connected")
        except:
            st.error("❌ Database: Connection Failed")

if __name__ == "__main__":
    main()
