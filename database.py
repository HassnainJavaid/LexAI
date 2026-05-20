import os
import sqlite3
import json
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(DB_DIR, "lexai_persistent.db")

db_lock = threading.Lock()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                password_hash TEXT,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Documents table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                user_email TEXT,
                doc_name TEXT,
                doc_type TEXT,
                file_path TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_email) REFERENCES users (email)
            )
        ''')
        
        # Audit logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_email TEXT,
                action TEXT,
                details TEXT,
                ip_address TEXT
            )
        ''')
        
        # Analytics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                category TEXT,
                action TEXT,
                country TEXT,
                topic TEXT,
                value REAL
            )
        ''')
        
        # Notifications table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                title TEXT,
                message TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default admin user if not exists
        cursor.execute("SELECT * FROM users WHERE email = 'admin@lexai.app'")
        if not cursor.fetchone():
            import bcrypt
            hashed = bcrypt.hashpw("AdminLexAI2026!".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute('''
                INSERT INTO users (email, first_name, last_name, password_hash, role)
                VALUES (?, ?, ?, ?, ?)
            ''', ('admin@lexai.app', 'LexAI', 'Admin', hashed, 'admin'))
            
        conn.commit()
        conn.close()

# Run init immediately on import
init_db()

# ── User DB Operations ──
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

def create_user(email: str, first_name: str, last_name: str, password_hash: str, role: str = "user") -> bool:
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO users (email, first_name, last_name, password_hash, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (email.lower(), first_name, last_name, password_hash, role))
            conn.commit()
            success = True
        except sqlite3.IntegrityError:
            success = False
        conn.close()
        return success

def update_user_profile(email: str, first_name: str, last_name: str) -> bool:
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET first_name = ?, last_name = ? WHERE email = ?
        ''', (first_name, last_name, email.lower()))
        conn.commit()
        rows_affected = cursor.rowcount
        conn.close()
        return rows_affected > 0

def list_all_users() -> List[Dict[str, Any]]:
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT email, first_name, last_name, role, created_at FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

# ── Document DB Operations ──
def save_document_metadata(doc_id: str, user_email: str, doc_name: str, doc_type: str, file_path: str):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO documents (doc_id, user_email, doc_name, doc_type, file_path)
            VALUES (?, ?, ?, ?, ?)
        ''', (doc_id, user_email.lower(), doc_name, doc_type, file_path))
        conn.commit()
        conn.close()

def get_user_documents(user_email: str) -> List[Dict[str, Any]]:
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE user_email = ? ORDER BY uploaded_at DESC", (user_email.lower(),))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

def get_document_by_id(doc_id: str) -> Optional[Dict[str, Any]]:
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

def delete_document_by_id(doc_id: str, user_email: str) -> bool:
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE doc_id = ? AND user_email = ?", (doc_id, user_email.lower()))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0

# ── Audit & Analytics ──
def record_audit_log(user_email: str, action: str, details: str, ip_address: str):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO audit_logs (user_email, action, details, ip_address)
            VALUES (?, ?, ?, ?)
        ''', (user_email.lower(), action, details, ip_address))
        conn.commit()
        conn.close()

def record_analytics(category: str, action: str, country: str = "Global", topic: str = "General", value: float = 1.0):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO analytics (category, action, country, topic, value)
            VALUES (?, ?, ?, ?, ?)
        ''', (category, action, country, topic, value))
        conn.commit()
        conn.close()

def get_analytics_summary() -> Dict[str, Any]:
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM users")
        total_users = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as count FROM documents")
        total_docs = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as count FROM audit_logs WHERE action LIKE '%api%'")
        total_api_calls = cursor.fetchone()["count"]
        
        cursor.execute("SELECT COUNT(*) as count FROM analytics")
        total_queries = cursor.fetchone()["count"]
        
        cursor.execute("SELECT topic, COUNT(*) as count FROM analytics WHERE category = 'legal_chat' GROUP BY topic ORDER BY count DESC LIMIT 5")
        top_topics = [dict(r) for r in cursor.fetchall()]
        
        cursor.execute("SELECT country, COUNT(*) as count FROM analytics WHERE category = 'legal_chat' GROUP BY country ORDER BY count DESC LIMIT 5")
        top_countries = [dict(r) for r in cursor.fetchall()]
        
        conn.close()
        return {
            "total_users": total_users,
            "total_documents": total_docs,
            "total_api_calls": total_api_calls,
            "total_queries": total_queries,
            "top_topics": top_topics,
            "top_countries": top_countries,
            "system_health": "Optimal",
            "uptime_percent": 99.98
        }

def get_recent_audit_logs(limit: int = 50) -> List[Dict[str, Any]]:
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

# ── Notifications ──
def create_notification(user_email: str, title: str, message: str):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notifications (user_email, title, message)
            VALUES (?, ?, ?)
        ''', (user_email.lower(), title, message))
        conn.commit()
        conn.close()

def get_user_notifications(user_email: str) -> List[Dict[str, Any]]:
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM notifications WHERE user_email = ? ORDER BY created_at DESC LIMIT 30", (user_email.lower(),))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

def mark_notifications_read(user_email: str):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_email = ?", (user_email.lower(),))
        conn.commit()
        conn.close()
