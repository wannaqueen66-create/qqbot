"""
聊天统计管理器
记录和管理群成员的发言统计数据
"""
import os
import json
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta
from typing import Dict, List, Tuple, Optional
from nonebot.log import logger


class ChatStatsManager:
    """聊天统计管理器"""
    
    def __init__(self):
        # 配置
        self.stats_file = Path(os.getenv("STATS_FILE", "data/chat_stats.json"))
        self.top_count = int(os.getenv("STATS_TOP_COUNT", "10"))
        self.push_hour = int(os.getenv("STATS_PUSH_HOUR", "23"))
        
        # 创建目录
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载数据
        self.stats = self._load_stats()
        
        logger.info(f"ChatStatsManager initialized: push_hour={self.push_hour}, top_count={self.top_count}")
    
    def _load_stats(self) -> dict:
        """加载统计数据"""
        if not self.stats_file.exists():
            return self._create_empty_stats()
        
        try:
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load stats: {e}")
            return self._create_empty_stats()
    
    def _create_empty_stats(self) -> dict:
        """创建空统计数据"""
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "groups": {}
        }
    
    def _save_stats(self):
        """保存统计数据"""
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save stats: {e}")
    
    def _reset_if_new_day(self):
        """如果是新的一天，重置统计"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.stats.get("date") != today:
            logger.info(f"New day detected, resetting stats (was {self.stats.get('date')}, now {today})")
            self.stats = self._create_empty_stats()
            self._save_stats()
    
    def record_message(self, group_id: str, user_id: str, nickname: str, message_text: str = ""):
        """
        记录群消息
        
        Args:
            group_id: 群号
            user_id: 用户ID
            nickname: 用户昵称
            message_text: 消息内容（用于AI点评）
        """
        self._reset_if_new_day()
        
        group_id = str(group_id)
        user_id = str(user_id)
        
        # 初始化群数据
        if group_id not in self.stats["groups"]:
            self.stats["groups"][group_id] = {
                "users": {},
                "last_push_time": None
            }
        
        # 初始化用户数据
        if user_id not in self.stats["groups"][group_id]["users"]:
            self.stats["groups"][group_id]["users"][user_id] = {
                "nickname": nickname,
                "count": 0,
                "last_msg_time": None,
                "recent_messages": []  # 存储最近的消息
            }
        
        # 更新数据
        self.stats["groups"][group_id]["users"][user_id]["count"] += 1
        self.stats["groups"][group_id]["users"][user_id]["nickname"] = nickname  # 更新昵称
        self.stats["groups"][group_id]["users"][user_id]["last_msg_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 记录最近的消息内容（保留最近5条，用于AI点评）
        if message_text:
            recent_msgs = self.stats["groups"][group_id]["users"][user_id].get("recent_messages", [])
            recent_msgs.append({
                "text": message_text[:200],  # 限制长度
                "time": datetime.now().strftime("%H:%M:%S")
            })
            # 只保留最近5条
            self.stats["groups"][group_id]["users"][user_id]["recent_messages"] = recent_msgs[-5:]
        
        # 保存（每10条消息保存一次，避免频繁IO）
        total_count = sum(
            u["count"] for u in self.stats["groups"][group_id]["users"].values()
        )
        if total_count % 10 == 0:
            self._save_stats()
    
    def get_ranking(
        self, 
        group_id: str, 
        since_time: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        获取排行榜
        
        Args:
            group_id: 群号
            since_time: 起始时间（可选，用于过滤）
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 排行榜列表
        """
        self._reset_if_new_day()
        
        group_id = str(group_id)
        
        if group_id not in self.stats["groups"]:
            return []
        
        users = self.stats["groups"][group_id]["users"]
        
        # 转换为列表并排序
        ranking = []
        for user_id, data in users.items():
            if data["count"] > 0:  # 只包含有发言的用户
                ranking.append({
                    "user_id": user_id,
                    "nickname": data["nickname"],
                    "count": data["count"],
                    "last_msg_time": data["last_msg_time"]
                })
        
        # 按消息数降序排序
        ranking.sort(key=lambda x: x["count"], reverse=True)
        
        # 限制返回数量
        if limit is None:
            limit = self.top_count
        
        return ranking[:limit]
    
    def get_user_recent_messages(self, group_id: str, user_id: str) -> List[Dict]:
        """
        获取用户最近的消息
        
        Args:
            group_id: 群号
            user_id: 用户ID
            
        Returns:
            List[Dict]: 最近的消息列表
        """
        group_id = str(group_id)
        user_id = str(user_id)
        
        if group_id not in self.stats["groups"]:
            return []
        
        if user_id not in self.stats["groups"][group_id]["users"]:
            return []
        
        return self.stats["groups"][group_id]["users"][user_id].get("recent_messages", [])
    
    def get_group_stats(self, group_id: str) -> Dict:
        """
        获取群统计信息
        
        Args:
            group_id: 群号
            
        Returns:
            Dict: 群统计信息
        """
        self._reset_if_new_day()
        
        group_id = str(group_id)
        
        if group_id not in self.stats["groups"]:
            return {
                "total_messages": 0,
                "active_users": 0,
                "last_push_time": None
            }
        
        users = self.stats["groups"][group_id]["users"]
        
        total_messages = sum(u["count"] for u in users.values())
        active_users = len([u for u in users.values() if u["count"] > 0])
        
        return {
            "total_messages": total_messages,
            "active_users": active_users,
            "last_push_time": self.stats["groups"][group_id].get("last_push_time")
        }
    
    def get_last_push_time(self, group_id: str) -> Optional[str]:
        """
        获取上次推送时间
        
        Args:
            group_id: 群号
            
        Returns:
            Optional[str]: 上次推送时间
        """
        group_id = str(group_id)
        
        if group_id not in self.stats["groups"]:
            return None
        
        return self.stats["groups"][group_id].get("last_push_time")
    
    def update_push_time(self, group_id: str):
        """
        更新推送时间
        
        Args:
            group_id: 群号
        """
        group_id = str(group_id)
        
        if group_id not in self.stats["groups"]:
            self.stats["groups"][group_id] = {
                "users": {},
                "last_push_time": None
            }
        
        self.stats["groups"][group_id]["last_push_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_stats()
        logger.info(f"Updated push time for group {group_id}")
    
    def get_all_active_groups(self) -> List[str]:
        """
        获取所有有统计数据的群
        
        Returns:
            List[str]: 群号列表
        """
        self._reset_if_new_day()
        return list(self.stats.get("groups", {}).keys())
    
    def force_save(self):
        """强制保存数据"""
        self._save_stats()


# 全局单例
chat_stats_manager = ChatStatsManager()
