"""
用户配额管理器
限制每个用户每日多模态 API 调用次数
"""
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from nonebot.log import logger


class QuotaManager:
    """用户配额管理器"""
    
    def __init__(self):
        # 配置
        self.quota_file = Path(os.getenv("QUOTA_FILE", "data/user_quotas.json"))
        self.daily_limit = int(os.getenv("DAILY_MULTIMODAL_LIMIT", "100"))
        self.enabled = os.getenv("ENABLE_QUOTA_LIMIT", "true").lower() == "true"
        
        # 创建目录
        self.quota_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载配额数据
        self.quotas = self._load_quotas()
        
        logger.info(
            f"QuotaManager initialized: limit={self.daily_limit}/day, "
            f"enabled={self.enabled}"
        )
    
    def _load_quotas(self) -> dict:
        """加载配额数据"""
        if not self.quota_file.exists():
            return {"date": datetime.now().strftime("%Y-%m-%d"), "users": {}}
        
        try:
            with open(self.quota_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load quotas: {e}")
            return {"date": datetime.now().strftime("%Y-%m-%d"), "users": {}}
    
    def _save_quotas(self):
        """保存配额数据"""
        try:
            with open(self.quota_file, 'w', encoding='utf-8') as f:
                json.dump(self.quotas, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save quotas: {e}")
    
    def _reset_if_new_day(self):
        """如果是新的一天，重置配额"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self.quotas.get("date") != today:
            logger.info(f"New day detected, resetting quotas (was {self.quotas.get('date')}, now {today})")
            self.quotas = {"date": today, "users": {}}
            self._save_quotas()
    
    def check_quota(self, user_id: str, is_multimodal: bool = False) -> tuple[bool, int, int]:
        """
        检查用户配额
        
        Args:
            user_id: 用户ID
            is_multimodal: 是否为多模态请求
            
        Returns:
            tuple[bool, int, int]: (是否允许, 已使用次数, 剩余次数)
        """
        if not self.enabled:
            return True, 0, self.daily_limit
        
        # 重置配额（如果是新的一天）
        self._reset_if_new_day()
        
        # 获取用户当前使用次数
        user_data = self.quotas["users"].get(user_id, {
            "total": 0,
            "multimodal": 0
        })
        
        used = user_data.get("multimodal", 0)
        remaining = self.daily_limit - used
        
        # 如果是查询，直接返回
        if not is_multimodal:
            return True, used, remaining
        
        # 检查是否超过限额
        if used >= self.daily_limit:
            logger.warning(f"User {user_id} exceeded daily multimodal quota: {used}/{self.daily_limit}")
            return False, used, 0
        
        return True, used, remaining
    
    def use_quota(self, user_id: str, is_multimodal: bool = False):
        """
        使用配额
        
        Args:
            user_id: 用户ID
            is_multimodal: 是否为多模态请求
        """
        if not self.enabled:
            return
        
        # 重置配额（如果是新的一天）
        self._reset_if_new_day()
        
        # 初始化用户数据
        if user_id not in self.quotas["users"]:
            self.quotas["users"][user_id] = {
                "total": 0,
                "multimodal": 0
            }
        
        # 增加计数
        self.quotas["users"][user_id]["total"] += 1
        
        if is_multimodal:
            self.quotas["users"][user_id]["multimodal"] += 1
            logger.info(
                f"User {user_id} used multimodal quota: "
                f"{self.quotas['users'][user_id]['multimodal']}/{self.daily_limit}"
            )
        
        # 保存
        self._save_quotas()
    
    def get_user_stats(self, user_id: str) -> dict:
        """
        获取用户统计信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            dict: 用户统计
        """
        self._reset_if_new_day()
        
        user_data = self.quotas["users"].get(user_id, {
            "total": 0,
            "multimodal": 0
        })
        
        return {
            "total_today": user_data.get("total", 0),
            "multimodal_today": user_data.get("multimodal", 0),
            "multimodal_remaining": self.daily_limit - user_data.get("multimodal", 0),
            "daily_limit": self.daily_limit,
            "date": self.quotas.get("date")
        }
    
    def get_all_stats(self) -> dict:
        """
        获取所有用户统计
        
        Returns:
            dict: 全局统计
        """
        self._reset_if_new_day()
        
        total_users = len(self.quotas["users"])
        total_requests = sum(u.get("total", 0) for u in self.quotas["users"].values())
        total_multimodal = sum(u.get("multimodal", 0) for u in self.quotas["users"].values())
        
        return {
            "date": self.quotas.get("date"),
            "total_users": total_users,
            "total_requests": total_requests,
            "total_multimodal": total_multimodal,
            "daily_limit": self.daily_limit,
            "enabled": self.enabled
        }
    
    def reset_user_quota(self, user_id: str):
        """
        重置用户配额（管理员功能）
        
        Args:
            user_id: 用户ID
        """
        if user_id in self.quotas["users"]:
            self.quotas["users"][user_id] = {
                "total": 0,
                "multimodal": 0
            }
            self._save_quotas()
            logger.info(f"Reset quota for user {user_id}")


# 全局单例
quota_manager = QuotaManager()
