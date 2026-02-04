import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from nonebot.log import logger
import threading

# Database configuration
DB_FILE = "data/qqbot_data.db"  # Store in data directory for persistence
MAX_MESSAGE_AGE_DAYS = 14  # Keep group messages for 14 days
MAX_CONVERSATION_AGE_DAYS = 7  # Keep conversations for 7 days
MAX_GROUP_CONTEXT_HOURS = 3    # Keep group context for 3 hours
MAX_SUMMARY_AGE_DAYS = 2       # Keep summaries for 2 days

class Database:
    """
    SQLite database manager for QQ Bot.
    Handles conversation memory, chat history, and summaries.
    """
    
    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self._local = threading.local()
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_file, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_database(self):
        """Initialize database tables"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Table 1: User conversations (Tier 1 - Personal memory)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_time 
            ON conversations (user_id, timestamp)
        """)
        
        # Table 2: Group messages (for AI summary)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_time 
            ON group_messages (group_id, timestamp)
        """)
        
        # Table 3: Group context (Tier 2 - Shared context)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ctx_group_time 
            ON group_context (group_id, timestamp)
        """)
        
        # Table 4: Group summaries (Tier 3 - Long-term memory)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sum_group_time 
            ON group_summaries (group_id, timestamp)
        """)
        
        conn.commit()
        # Table 5: Draw usage (rate limit)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS draw_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_draw_user_time
            ON draw_usage (user_id, timestamp)
        """)

        conn.commit()
        logger.info(f"Database initialized: {self.db_file}")
    
    # ==================== Conversation Memory (Tier 1) ====================
    
    def add_conversation(self, user_id: str, role: str, content: str):
        """Add a message to user's conversation history"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO conversations (user_id, role, content)
            VALUES (?, ?, ?)
        """, (user_id, role, content))
        
        conn.commit()
        
        # Auto-clean old conversations
        self._clean_old_conversations(user_id)
    
    def get_conversation_history(self, user_id: str, max_rounds: int = 10) -> List[Dict]:
        """Get recent conversation history for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get last N*2 messages (N rounds = user + assistant)
        cursor.execute("""
            SELECT role, content FROM conversations
            WHERE user_id = ? 
            AND timestamp > datetime('now', '-7 days')
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, max_rounds * 2))
        
        rows = cursor.fetchall()
        
        # Reverse to get chronological order
        history = []
        for row in reversed(rows):
            history.append({
                "role": row['role'],
                "parts": [{"text": row['content']}]
            })
        
        return history
    
    def _clean_old_conversations(self, user_id: str):
        """Remove old conversations for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM conversations
            WHERE user_id = ?
            AND timestamp < datetime('now', '-7 days')
        """, (user_id,))
        
        conn.commit()
    
    def clear_user_conversation(self, user_id: str):
        """Clear all conversation history for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        conn.commit()
        
        logger.info(f"Cleared conversation for user {user_id[:16]}...")
    
    # ==================== Group Messages (AI Summary) ====================
    
    def add_group_message(self, group_id: int, sender: str, content: str):
        """Add a message to group chat history"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO group_messages (group_id, sender, content)
            VALUES (?, ?, ?)
        """, (group_id, sender, content))
        
        conn.commit()
    
    def get_group_messages(self, group_id: int, hours: int = 24, limit: int = 500) -> List[Dict]:
        """Get recent group messages"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT sender, content, timestamp FROM group_messages
            WHERE group_id = ?
            AND timestamp > datetime('now', ? || ' hours')
            ORDER BY timestamp DESC
            LIMIT ?
        """, (group_id, f'-{hours}', limit))
        
        rows = cursor.fetchall()
        
        messages = []
        for row in reversed(rows):
            messages.append({
                "sender": row['sender'],
                "content": row['content'],
                "time": datetime.fromisoformat(row['timestamp'])
            })
        
        return messages
    
    def get_group_messages_since(self, group_id: int, since: datetime) -> List[Dict]:
        """Get group messages since a specific time"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT sender, content, timestamp FROM group_messages
            WHERE group_id = ?
            AND timestamp > ?
            ORDER BY timestamp ASC
        """, (group_id, since.isoformat()))
        
        rows = cursor.fetchall()
        
        messages = []
        for row in rows:
            messages.append({
                "sender": row['sender'],
                "content": row['content'],
                "time": datetime.fromisoformat(row['timestamp'])
            })
        
        return messages
    
    # ==================== Group Context (Tier 2) ====================
    
    def add_group_context(self, group_id: str, user_name: str, content: str):
        """Add a message to shared group context"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO group_context (group_id, user_name, content)
            VALUES (?, ?, ?)
        """, (group_id, user_name, content))
        
        conn.commit()
        
        # Keep only recent messages
        self._clean_old_group_context(group_id)
    
    def get_group_context(self, group_id: str, limit: int = 10) -> List[Tuple[datetime, str, str]]:
        """Get recent group context messages"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, user_name, content FROM group_context
            WHERE group_id = ?
            AND timestamp > datetime('now', '-3 hours')
            ORDER BY timestamp DESC
            LIMIT ?
        """, (group_id, limit))
        
        rows = cursor.fetchall()
        
        context = []
        for row in reversed(rows):
            context.append((
                datetime.fromisoformat(row['timestamp']),
                row['user_name'],
                row['content']
            ))
        
        return context
    
    def _clean_old_group_context(self, group_id: str):
        """Keep only recent group context"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Remove messages older than 3 hours
        cursor.execute("""
            DELETE FROM group_context
            WHERE group_id = ?
            AND timestamp < datetime('now', '-3 hours')
        """, (group_id,))
        
        # Keep only last 10 messages
        cursor.execute("""
            DELETE FROM group_context
            WHERE group_id = ?
            AND id NOT IN (
                SELECT id FROM group_context
                WHERE group_id = ?
                ORDER BY timestamp DESC
                LIMIT 10
            )
        """, (group_id, group_id))
        
        conn.commit()
    
    # ==================== Group Summaries (Tier 3) ====================
    
    def add_group_summary(self, group_id: str, summary: str):
        """Add a long-term group summary"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO group_summaries (group_id, summary)
            VALUES (?, ?)
        """, (group_id, summary))
        
        conn.commit()
        
        # Keep only last 5 summaries
        self._clean_old_summaries(group_id)
    
    def get_group_summaries(self, group_id: str, limit: int = 5) -> List[Tuple[datetime, str]]:
        """Get recent group summaries"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, summary FROM group_summaries
            WHERE group_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (group_id, limit))
        
        rows = cursor.fetchall()
        
        summaries = []
        for row in reversed(rows):
            summaries.append((
                datetime.fromisoformat(row['timestamp']),
                row['summary']
            ))
        
        return summaries
    
    def _clean_old_summaries(self, group_id: str):
        """Keep only summaries from last 2 days per group"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM group_summaries
            WHERE group_id = ?
            AND timestamp < datetime('now', '-2 days')
        """, (group_id,))
        
        conn.commit()
    
    # ==================== Maintenance ====================
    
    def cleanup_old_data(self):
        """Clean up old data from all tables"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Clean old conversations (>7 days)
        cursor.execute("""
            DELETE FROM conversations
            WHERE timestamp < datetime('now', '-7 days')
        """)
        
        # Clean old group messages (>14 days)  
        cursor.execute("""
            DELETE FROM group_messages
            WHERE timestamp < datetime('now', '-14 days')
        """)
        
        # Clean old group context (>3 hours)
        cursor.execute("""
            DELETE FROM group_context
            WHERE timestamp < datetime('now', '-3 hours')
        """)
        
        # Clean old group summaries (>2 days)
        cursor.execute("""
            DELETE FROM group_summaries
            WHERE timestamp < datetime('now', '-2 days')
        """)
        
        conn.commit()
        
        # Vacuum to reclaim space
        cursor.execute("VACUUM")
        
        logger.info("Database cleanup completed")
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Count conversations
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM conversations")
        stats['active_users'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM conversations")
        stats['total_conversations'] = cursor.fetchone()[0]
        
        # Count group messages
        cursor.execute("SELECT COUNT(DISTINCT group_id) FROM group_messages")
        stats['active_groups'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM group_messages")
        stats['total_group_messages'] = cursor.fetchone()[0]
        
        # Count summaries
        cursor.execute("SELECT COUNT(*) FROM group_summaries")
        stats['total_summaries'] = cursor.fetchone()[0]
        
        # Get database file size
        import os
        if os.path.exists(self.db_file):
            stats['db_size_mb'] = round(os.path.getsize(self.db_file) / 1024 / 1024, 2)
        else:
            stats['db_size_mb'] = 0
        
        return stats
    

    # ==================== Draw Rate Limit ====================

    def count_draw_usage(self, user_id: str, window_hours: int = 5) -> int:
        """Count how many /draw a user used within last window_hours."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM draw_usage
            WHERE user_id = ?
            AND timestamp > datetime('now', ? || ' hours')
            """,
            (user_id, f'-{int(window_hours)}'),
        )
        return int(cursor.fetchone()[0] or 0)

    def add_draw_usage(self, user_id: str):
        """Record a /draw usage for user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO draw_usage (user_id) VALUES (?)", (user_id,))
        conn.commit()

    def clean_old_draw_usage(self, keep_hours: int = 48):
        """Clean old draw_usage records."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM draw_usage WHERE timestamp < datetime('now', ? || ' hours')",
            (f'-{int(keep_hours)}',),
        )
        conn.commit()

    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

# Global database instance
db = Database()
