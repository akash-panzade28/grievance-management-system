import sqlite3
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from models.models import ComplaintRequest, ComplaintResponse, ComplaintStatus, ComplaintCategory, Complaint
from config.config import Config

class DatabaseManager:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_URL
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create complaints table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS complaints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    complaint_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    mobile TEXT NOT NULL,
                    complaint_details TEXT NOT NULL,
                    category TEXT DEFAULT 'Other',
                    status TEXT DEFAULT 'Registered',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create status_history table for tracking status changes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS status_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    complaint_id TEXT NOT NULL,
                    old_status TEXT,
                    new_status TEXT NOT NULL,
                    notes TEXT,
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (complaint_id) REFERENCES complaints (complaint_id)
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaint_id ON complaints(complaint_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mobile ON complaints(mobile)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON complaints(status)")
            
            conn.commit()
    
    def generate_complaint_id(self) -> str:
        """Generate unique complaint ID"""
        return f"CMP{uuid.uuid4().hex[:8].upper()}"
    
    def register_complaint(self, complaint: ComplaintRequest) -> ComplaintResponse:
        """Register a new complaint"""
        complaint_id = self.generate_complaint_id()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO complaints (complaint_id, name, mobile, complaint_details, category, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                complaint_id,
                complaint.name,
                complaint.mobile,
                complaint.complaint_details,
                complaint.category.value,
                ComplaintStatus.REGISTERED.value
            ))
            
            # Add initial status to history
            cursor.execute("""
                INSERT INTO status_history (complaint_id, new_status, notes)
                VALUES (?, ?, ?)
            """, (complaint_id, ComplaintStatus.REGISTERED.value, "Complaint registered"))
            
            conn.commit()
            
            return self.get_complaint_by_id(complaint_id)
    
    def get_complaint_by_id(self, complaint_id: str) -> Optional[ComplaintResponse]:
        """Get complaint by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM complaints WHERE complaint_id = ?", (complaint_id,))
            row = cursor.fetchone()
            
            if row:
                return ComplaintResponse(
                    complaint_id=row['complaint_id'],
                    name=row['name'],
                    mobile=row['mobile'],
                    complaint_details=row['complaint_details'],
                    category=row['category'],
                    status=ComplaintStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at'])
                )
            return None
    
    def get_complaints_by_mobile(self, mobile: str) -> List[ComplaintResponse]:
        """Enhanced search for complaints by mobile number with flexible matching"""
        import re

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Clean the input mobile number
            clean_mobile = re.sub(r'[-.\s\(\)]', '', mobile)

            # Try multiple search strategies for better matching
            search_queries = [
                # Exact match
                ("SELECT * FROM complaints WHERE mobile = ? ORDER BY created_at DESC", [clean_mobile]),
                # Last 10 digits match (for international numbers)
                ("SELECT * FROM complaints WHERE SUBSTR(mobile, -10) = ? ORDER BY created_at DESC", [clean_mobile[-10:]] if len(clean_mobile) >= 10 else [clean_mobile]),
                # Contains pattern
                ("SELECT * FROM complaints WHERE mobile LIKE ? ORDER BY created_at DESC", [f"%{clean_mobile}%"]),
            ]

            complaints = []
            found_ids = set()  # To avoid duplicates

            for query, params in search_queries:
                try:
                    cursor.execute(query, params)
                    rows = cursor.fetchall()

                    for row in rows:
                        if row['complaint_id'] not in found_ids:
                            complaints.append(ComplaintResponse(
                                complaint_id=row['complaint_id'],
                                name=row['name'],
                                mobile=row['mobile'],
                                complaint_details=row['complaint_details'],
                                category=row['category'],
                                status=ComplaintStatus(row['status']),
                                created_at=datetime.fromisoformat(row['created_at']),
                                updated_at=datetime.fromisoformat(row['updated_at'])
                            ))
                            found_ids.add(row['complaint_id'])

                    # If we found exact matches, prioritize them
                    if complaints and query == search_queries[0][0]:
                        break

                except Exception as e:
                    print(f"Search query failed: {query}, Error: {e}")
                    continue

            return complaints
    
    def update_complaint_status(self, complaint_id: str, new_status: ComplaintStatus, notes: str = None) -> bool:
        """Update complaint status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get current status
            cursor.execute("SELECT status FROM complaints WHERE complaint_id = ?", (complaint_id,))
            row = cursor.fetchone()
            if not row:
                return False
            
            old_status = row['status']
            
            # Update complaint status
            cursor.execute("""
                UPDATE complaints 
                SET status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE complaint_id = ?
            """, (new_status.value, complaint_id))
            
            # Add to status history
            cursor.execute("""
                INSERT INTO status_history (complaint_id, old_status, new_status, notes)
                VALUES (?, ?, ?, ?)
            """, (complaint_id, old_status, new_status.value, notes))
            
            conn.commit()
            return True
    
    def get_status_history(self, complaint_id: str) -> List[Dict[str, Any]]:
        """Get status change history for a complaint"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM status_history
                WHERE complaint_id = ?
                ORDER BY changed_at ASC
            """, (complaint_id,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_all_complaints(self) -> List[Complaint]:
        """Get all complaints in the system"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT complaint_id, name, mobile, complaint_details, category, status, created_at, updated_at
                FROM complaints
                ORDER BY created_at DESC
            """)

            complaints = []
            for row in cursor.fetchall():
                complaints.append(Complaint(
                    complaint_id=row['complaint_id'],
                    name=row['name'],
                    mobile=row['mobile'],
                    complaint_details=row['complaint_details'],
                    category=ComplaintCategory(row['category']),
                    status=ComplaintStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at'])
                ))

            return complaints

    def delete_complaint(self, complaint_id: str) -> bool:
        """Delete a complaint"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Delete from status history first (foreign key constraint)
            cursor.execute("DELETE FROM status_history WHERE complaint_id = ?", (complaint_id,))

            # Delete the complaint
            cursor.execute("DELETE FROM complaints WHERE complaint_id = ?", (complaint_id,))

            conn.commit()
            return cursor.rowcount > 0

    def get_complaint_statistics(self) -> Dict:
        """Get complaint statistics for admin dashboard"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total complaints
            cursor.execute("SELECT COUNT(*) as total FROM complaints")
            total_complaints = cursor.fetchone()['total']

            # Status distribution
            cursor.execute("SELECT status, COUNT(*) as count FROM complaints GROUP BY status")
            status_distribution = [{"status": row['status'], "count": row['count']} for row in cursor.fetchall()]

            # Category distribution
            cursor.execute("SELECT category, COUNT(*) as count FROM complaints GROUP BY category")
            category_distribution = [{"category": row['category'], "count": row['count']} for row in cursor.fetchall()]

            # Recent complaints (last 7 days)
            cursor.execute("SELECT COUNT(*) as recent FROM complaints WHERE created_at >= datetime('now', '-7 days')")
            recent_complaints = cursor.fetchone()['recent']

            return {
                "total_complaints": total_complaints,
                "recent_complaints": recent_complaints,
                "status_distribution": status_distribution,
                "category_distribution": category_distribution
            }
