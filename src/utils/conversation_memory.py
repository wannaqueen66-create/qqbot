from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from nonebot.log import logger
from src.utils.database import db

class ConversationMemory:
    """
    Three-tier memory architecture using SQLite database:
    1. Personal short-term memory (user-specific, stored in DB)
    2. Shared group context (group-wide, compressed, recent topics)
    3. Long-term group memory (summaries from ai_summary, persistent)
    """
    
    def __init__(self):
        # No in-memory storage needed, everything goes to database
        logger.info("ConversationMemory initialized with SQLite backend")
    
    def add_personal_message(self, user_id: str, role: str, content: str):
        """Add a message to personal memory (Tier 1)"""
        db.add_conversation(user_id, role, content)
    
    def add_group_context(self, group_id: str, user_name: str, content: str):
        """Add a message to shared group context (Tier 2)"""
        db.add_group_context(group_id, user_name, content)
    
    def add_group_summary(self, group_id: str, summary: str):
        """Add a long-term summary (Tier 3, from ai_summary)"""
        db.add_group_summary(group_id, summary)
    
    def get_personal_history(self, user_id: str) -> List[Dict[str, str]]:
        """Get personal conversation history (Tier 1)"""
        return db.get_conversation_history(user_id, max_rounds=10)
    
    def get_group_context_text(self, group_id: str) -> Optional[str]:
        """Get compressed group context (Tier 2)"""
        context = db.get_group_context(group_id, limit=10)
        
        if not context:
            return None
        
        # Compress recent messages into a brief summary
        recent = context[-5:]  # Last 5 messages
        context_lines = [f"{name}: {msg[:50]}..." for _, name, msg in recent]
        return "最近群聊上下文：\n" + "\n".join(context_lines)
    
    def get_group_summaries_text(self, group_id: str) -> Optional[str]:
        """Get long-term summaries (Tier 3)"""
        summaries = db.get_group_summaries(group_id, limit=5)
        
        if not summaries:
            return None
        
        summary_texts = []
        for ts, summary in summaries[-3:]:  # Last 3 summaries
            time_str = ts.strftime("%H:%M")
            summary_texts.append(f"[{time_str}] {summary[:200]}...")
        
        return "历史总结：\n" + "\n".join(summary_texts)
    
    def build_full_context(self, user_id: str, group_id: Optional[str] = None) -> Tuple[List[Dict], Optional[str]]:
        """
        Build complete context for AI:
        - Returns: (personal_history, system_context)
        - system_context includes group context + summaries
        """
        personal_history = self.get_personal_history(user_id)
        
        if not group_id:
            return personal_history, None
        
        # Build system context from Tier 2 + Tier 3
        context_parts = []
        
        group_ctx = self.get_group_context_text(group_id)
        if group_ctx:
            context_parts.append(group_ctx)
        
        summaries = self.get_group_summaries_text(group_id)
        if summaries:
            context_parts.append(summaries)
        
        system_context = "\n\n".join(context_parts) if context_parts else None
        
        return personal_history, system_context
    
    def clear_user(self, user_id: str):
        """Clear personal memory for a specific user"""
        db.clear_user_conversation(user_id)
    
    def get_stats(self) -> Dict[str, int]:
        """Get memory usage statistics"""
        stats = db.get_stats()
        
        return {
            "users_cached": stats.get('active_users', 0),
            "personal_messages": stats.get('total_conversations', 0),
            "group_contexts": stats.get('active_groups', 0),
            "total_summaries": stats.get('total_summaries', 0),
            "db_size_mb": stats.get('db_size_mb', 0)
        }

# Global instance
conversation_memory = ConversationMemory()
