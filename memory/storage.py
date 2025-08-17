import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import sqlite3
import threading
from dataclasses import dataclass, asdict

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConversationEntry:
    """Represents a single conversation entry"""
    session_id: str
    timestamp: str
    user_message: str
    agent_response: str
    agent_used: str
    tools_used: List[str]
    confidence: float
    routing_confidence: float
    metadata: Dict[str, Any]


class ConversationStorage:
    """Handles persistent storage of conversation data using SQLite and JSON files"""
    
    def __init__(self):
        self.storage_path = Path(settings.memory_storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        # SQLite database for structured queries
        self.db_path = self.storage_path / "conversations.db"
        
        # JSON files for session-based storage
        self.sessions_path = self.storage_path / "sessions"
        self.sessions_path.mkdir(exist_ok=True)
        
        # Thread lock for database operations
        self._db_lock = threading.Lock()
        
        # Initialize database
        self._init_database()
        
        logger.info(f"Conversation storage initialized at {self.storage_path}")
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        user_message TEXT NOT NULL,
                        agent_response TEXT NOT NULL,
                        agent_used TEXT NOT NULL,
                        tools_used TEXT,  -- JSON array
                        confidence REAL,
                        routing_confidence REAL,
                        metadata TEXT  -- JSON object
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_id 
                    ON conversations(session_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON conversations(timestamp)
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS session_metadata (
                        session_id TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        last_activity TEXT NOT NULL,
                        message_count INTEGER DEFAULT 0,
                        metadata TEXT  -- JSON object
                    )
                """)
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
    
    async def store_conversation(self, conversation_entry: Dict[str, Any]):
        """Store a conversation entry"""
        
        try:
            # Convert to ConversationEntry for validation
            entry = ConversationEntry(
                session_id=conversation_entry["session_id"],
                timestamp=conversation_entry["timestamp"],
                user_message=conversation_entry["user_message"],
                agent_response=conversation_entry["agent_response"],
                agent_used=conversation_entry["agent_used"],
                tools_used=conversation_entry.get("tools_used", []),
                confidence=conversation_entry.get("confidence", 0.0),
                routing_confidence=conversation_entry.get("routing_confidence", 0.0),
                metadata=conversation_entry.get("metadata", {})
            )
            
            # Store in database
            await self._store_in_database(entry)
            
            # Store in session file
            await self._store_in_session_file(entry)
            
            # Update session metadata
            await self._update_session_metadata(entry.session_id)
            
            logger.debug(f"Stored conversation entry for session {entry.session_id}")
            
        except Exception as e:
            logger.error(f"Failed to store conversation: {e}")
    
    async def _store_in_database(self, entry: ConversationEntry):
        """Store entry in SQLite database"""
        
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT INTO conversations 
                        (session_id, timestamp, user_message, agent_response, 
                         agent_used, tools_used, confidence, routing_confidence, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        entry.session_id,
                        entry.timestamp,
                        entry.user_message,
                        entry.agent_response,
                        entry.agent_used,
                        json.dumps(entry.tools_used),
                        entry.confidence,
                        entry.routing_confidence,
                        json.dumps(entry.metadata)
                    ))
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Database storage failed: {e}")
    
    async def _store_in_session_file(self, entry: ConversationEntry):
        """Store entry in session-specific JSON file"""
        
        try:
            session_file = self.sessions_path / f"{entry.session_id}.json"
            
            # Load existing session data
            session_data = []
            if session_file.exists():
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)
                except:
                    session_data = []
            
            # Add new entry
            session_data.append(asdict(entry))
            
            # Keep only last N entries to prevent files from growing too large
            max_entries = settings.max_conversation_history
            if len(session_data) > max_entries:
                session_data = session_data[-max_entries:]
            
            # Save updated session data
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Session file storage failed: {e}")
    
    async def _update_session_metadata(self, session_id: str):
        """Update session metadata"""
        
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    # Check if session exists
                    cursor = conn.execute(
                        "SELECT session_id FROM session_metadata WHERE session_id = ?",
                        (session_id,)
                    )
                    
                    now = datetime.now().isoformat()
                    
                    if cursor.fetchone():
                        # Update existing session
                        conn.execute("""
                            UPDATE session_metadata 
                            SET last_activity = ?, message_count = message_count + 1
                            WHERE session_id = ?
                        """, (now, session_id))
                    else:
                        # Create new session
                        conn.execute("""
                            INSERT INTO session_metadata 
                            (session_id, created_at, last_activity, message_count)
                            VALUES (?, ?, ?, 1)
                        """, (session_id, now, now))
                    
                    conn.commit()
                    
        except Exception as e:
            logger.error(f"Session metadata update failed: {e}")
    
    def get_recent_conversations(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversations for a session"""
        
        try:
            # First try to get from session file (faster)
            session_file = self.sessions_path / f"{session_id}.json"
            
            if session_file.exists():
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)
                    
                    # Return most recent entries
                    recent_data = session_data[-limit:] if session_data else []
                    
                    # Convert to expected format
                    result = []
                    for entry in recent_data:
                        result.append({
                            "user": entry["user_message"],
                            "response": entry["agent_response"],
                            "agent_used": entry["agent_used"],
                            "timestamp": entry["timestamp"],
                            "tools_used": entry.get("tools_used", []),
                            "confidence": entry.get("confidence", 0.0)
                        })
                    
                    return result
                    
                except Exception as e:
                    logger.warning(f"Failed to read session file, falling back to database: {e}")
            
            # Fallback to database
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("""
                        SELECT user_message, agent_response, agent_used, timestamp, 
                               tools_used, confidence
                        FROM conversations 
                        WHERE session_id = ? 
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (session_id, limit))
                    
                    result = []
                    for row in cursor.fetchall():
                        result.append({
                            "user": row[0],
                            "response": row[1],
                            "agent_used": row[2],
                            "timestamp": row[3],
                            "tools_used": json.loads(row[4]) if row[4] else [],
                            "confidence": row[5] or 0.0
                        })
                    
                    # Reverse to get chronological order
                    return list(reversed(result))
                    
        except Exception as e:
            logger.error(f"Failed to get recent conversations: {e}")
            return []
    
    def get_conversation_by_date(self, session_id: str, start_date: str, 
                               end_date: str) -> List[Dict[str, Any]]:
        """Get conversations within a date range"""
        
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("""
                        SELECT user_message, agent_response, agent_used, timestamp, 
                               tools_used, confidence, metadata
                        FROM conversations 
                        WHERE session_id = ? AND timestamp BETWEEN ? AND ?
                        ORDER BY timestamp ASC
                    """, (session_id, start_date, end_date))
                    
                    result = []
                    for row in cursor.fetchall():
                        result.append({
                            "user_message": row[0],
                            "agent_response": row[1],
                            "agent_used": row[2],
                            "timestamp": row[3],
                            "tools_used": json.loads(row[4]) if row[4] else [],
                            "confidence": row[5] or 0.0,
                            "metadata": json.loads(row[6]) if row[6] else {}
                        })
                    
                    return result
                    
        except Exception as e:
            logger.error(f"Failed to get conversations by date: {e}")
            return []
    
    def search_conversations(self, session_id: str, query: str, 
                           limit: int = 20) -> List[Dict[str, Any]]:
        """Search conversations by content"""
        
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("""
                        SELECT user_message, agent_response, agent_used, timestamp, 
                               tools_used, confidence
                        FROM conversations 
                        WHERE session_id = ? AND 
                              (user_message LIKE ? OR agent_response LIKE ?)
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """, (session_id, f"%{query}%", f"%{query}%", limit))
                    
                    result = []
                    for row in cursor.fetchall():
                        result.append({
                            "user_message": row[0],
                            "agent_response": row[1],
                            "agent_used": row[2],
                            "timestamp": row[3],
                            "tools_used": json.loads(row[4]) if row[4] else [],
                            "confidence": row[5] or 0.0
                        })
                    
                    return result
                    
        except Exception as e:
            logger.error(f"Failed to search conversations: {e}")
            return []
    
    def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """Get statistics for a session"""
        
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    # Get basic stats
                    cursor = conn.execute("""
                        SELECT COUNT(*) as total_messages,
                               MIN(timestamp) as first_message,
                               MAX(timestamp) as last_message,
                               AVG(confidence) as avg_confidence
                        FROM conversations 
                        WHERE session_id = ?
                    """, (session_id,))
                    
                    row = cursor.fetchone()
                    
                    # Get agent usage stats
                    cursor = conn.execute("""
                        SELECT agent_used, COUNT(*) as count
                        FROM conversations 
                        WHERE session_id = ?
                        GROUP BY agent_used
                        ORDER BY count DESC
                    """, (session_id,))
                    
                    agent_usage = {row[0]: row[1] for row in cursor.fetchall()}
                    
                    # Get tool usage stats
                    cursor = conn.execute("""
                        SELECT tools_used
                        FROM conversations 
                        WHERE session_id = ? AND tools_used IS NOT NULL
                    """, (session_id,))
                    
                    tool_usage = {}
                    for (tools_json,) in cursor.fetchall():
                        try:
                            tools = json.loads(tools_json)
                            for tool in tools:
                                tool_usage[tool] = tool_usage.get(tool, 0) + 1
                        except:
                            continue
                    
                    return {
                        "session_id": session_id,
                        "total_messages": row[0] if row else 0,
                        "first_message": row[1] if row and row[1] else None,
                        "last_message": row[2] if row and row[2] else None,
                        "average_confidence": row[3] if row and row[3] else 0.0,
                        "agent_usage": agent_usage,
                        "tool_usage": tool_usage
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get session statistics: {e}")
            return {"session_id": session_id, "error": str(e)}
    
    def clear_session(self, session_id: str):
        """Clear all data for a session"""
        
        try:
            # Remove session file
            session_file = self.sessions_path / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
            
            # Remove from database
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
                    conn.execute("DELETE FROM session_metadata WHERE session_id = ?", (session_id,))
                    conn.commit()
            
            logger.info(f"Cleared session {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
    
    def cleanup_old_sessions(self, days_old: int = 30):
        """Clean up sessions older than specified days"""
        
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
            
            # Get old sessions
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("""
                        SELECT session_id FROM session_metadata 
                        WHERE last_activity < ?
                    """, (cutoff_date,))
                    
                    old_sessions = [row[0] for row in cursor.fetchall()]
            
            # Remove old sessions
            for session_id in old_sessions:
                self.clear_session(session_id)
            
            logger.info(f"Cleaned up {len(old_sessions)} old sessions")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
    
    def export_session(self, session_id: str, format: str = "json") -> Dict[str, Any]:
        """Export session data"""
        
        try:
            # Get all conversations for session
            conversations = self.get_recent_conversations(session_id, limit=1000)
            stats = self.get_session_statistics(session_id)
            
            export_data = {
                "session_id": session_id,
                "exported_at": datetime.now().isoformat(),
                "statistics": stats,
                "conversations": conversations
            }
            
            if format == "json":
                return export_data
            else:
                return {"error": f"Unsupported export format: {format}"}
                
        except Exception as e:
            logger.error(f"Failed to export session: {e}")
            return {"error": str(e)}
    
    def get_all_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get list of all sessions"""
        
        try:
            with self._db_lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("""
                        SELECT session_id, created_at, last_activity, message_count
                        FROM session_metadata 
                        ORDER BY last_activity DESC 
                        LIMIT ?
                    """, (limit,))
                    
                    sessions = []
                    for row in cursor.fetchall():
                        sessions.append({
                            "session_id": row[0],
                            "created_at": row[1],
                            "last_activity": row[2],
                            "message_count": row[3]
                        })
                    
                    return sessions
                    
        except Exception as e:
            logger.error(f"Failed to get sessions: {e}")
            return []
