import json
import logging
import os
import uuid
from datetime import datetime

logger = logging.getLogger("session")


class SessionManager:
    """管理对话历史的持久化存储（JSON 文件）"""

    def __init__(self, sessions_dir: str = "sessions"):
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)
        logger.info(f"SessionManager 初始化: {sessions_dir}")

    def _session_path(self, session_id: str) -> str:
        return os.path.join(self.sessions_dir, f"session_{session_id}.json")

    def list_sessions(self) -> list[dict]:
        """列出所有会话（按 updated_at 倒序）"""
        sessions = []
        for filename in os.listdir(self.sessions_dir):
            if not filename.startswith("session_") or not filename.endswith(".json"):
                continue
            filepath = os.path.join(self.sessions_dir, filename)
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                # 只返回摘要信息，不返回全部消息
                sessions.append({
                    "id": data["id"],
                    "title": data.get("title", "新对话"),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "tool_names": data.get("tool_names", []),
                    "message_count": len(data.get("messages", [])),
                })
            except Exception as e:
                logger.warning(f"加载会话失败: {filename} - {e}")
        # 按 updated_at 倒序
        sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return sessions

    def create_session(self, tool_names: list[str] | None = None) -> str:
        """创建新会话，返回 session_id"""
        session_id = uuid.uuid4().hex[:12]
        now = datetime.now().isoformat()
        data = {
            "id": session_id,
            "title": "新对话",
            "created_at": now,
            "updated_at": now,
            "tool_names": tool_names or [],
            "messages": [],
        }
        with open(self._session_path(session_id), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"创建新会话: {session_id}")
        return session_id

    def save_message(self, session_id: str, message: dict) -> bool:
        """保存单条消息到会话"""
        filepath = self._session_path(session_id)
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            message.setdefault("timestamp", datetime.now().isoformat())
            data["messages"].append(message)
            data["updated_at"] = datetime.now().isoformat()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存消息失败: {session_id} - {e}")
            return False

    def update_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        filepath = self._session_path(session_id)
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            data["title"] = title
            data["updated_at"] = datetime.now().isoformat()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"更新标题失败: {session_id} - {e}")
            return False

    def update_tool_names(self, session_id: str, tool_names: list[str]) -> bool:
        """更新会话的工具配置"""
        filepath = self._session_path(session_id)
        logger.info(f"[SessionManager] update_tool_names: session_id={session_id}, filepath={filepath}, exists={os.path.exists(filepath)}")
        if not os.path.exists(filepath):
            logger.warning(f"[SessionManager] Session file not found: {filepath}")
            return False
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"[SessionManager] Before: tool_names={data.get('tool_names')}")
            data["tool_names"] = tool_names
            data["updated_at"] = datetime.now().isoformat()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[SessionManager] After: tool_names={data.get('tool_names')}")
            return True
        except Exception as e:
            logger.error(f"[SessionManager] update_tool_names failed: {session_id} - {e}")
            return False

    def load_session(self, session_id: str) -> dict | None:
        """加载会话详情（含全部消息）"""
        filepath = self._session_path(session_id)
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载会话失败: {session_id} - {e}")
            return None

    def save_session(self, session_id: str, session_data: dict) -> bool:
        """保存整个会话数据"""
        filepath = self._session_path(session_id)
        try:
            session_data["updated_at"] = datetime.now().isoformat()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存会话失败: {session_id} - {e}")
            return False

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        filepath = self._session_path(session_id)
        if not os.path.exists(filepath):
            return False
        try:
            os.remove(filepath)
            logger.info(f"删除会话: {session_id}")
            return True
        except Exception as e:
            logger.error(f"删除会话失败: {session_id} - {e}")
            return False

    def save_context(self, session_id: str, context_data: dict) -> bool:
        """保存上下文状态到会话文件"""
        filepath = self._session_path(session_id)
        if not os.path.exists(filepath):
            return False
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            data["context"] = context_data
            data["updated_at"] = datetime.now().isoformat()
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存上下文失败: {session_id} - {e}")
            return False

    def load_context(self, session_id: str) -> dict | None:
        """从会话文件加载上下文状态"""
        filepath = self._session_path(session_id)
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("context")
        except Exception as e:
            logger.error(f"加载上下文失败: {session_id} - {e}")
            return None
