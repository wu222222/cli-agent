from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field
import logging

from src.agent.types import *

logger = logging.getLogger("context")


class ContextManager:
    def __init__(self, policy: Optional[ContextPolicy] = None):
        self.messages: List[Message] = []
        self.state_trace: List[StateTrace] = []
        self.system_prompts: dict[str, str] = {}
        self.final_answer: Optional[str] = None
        # === 记忆衰减 ===
        self.current_step: int = 0
        self.policy: ContextPolicy = policy or ContextPolicy()
        self.context_summaries: List[Message] = []  # LLM 生成的摘要消息

    # ============================================================
    # System Prompt
    # ============================================================

    def set_system_prompt(self, agent_name: str, prompt: str) -> None:
        self.system_prompts[agent_name] = prompt

    def get_system_prompt(self, agent_name: str) -> str:
        return self.system_prompts.get(agent_name, "")

    def get_system_format_prompt(self, agent_name: str) -> Dict[str, str]:
        return {"role": "system", "content": self.system_prompts.get(agent_name, "")}

    # ============================================================
    # 消息写入
    # ============================================================

    def add_message(self, role: str, content: str, sender: str,
                    receivers: List[str] = None, tool_call_id: Optional[str] = None,
                    tool_name: Optional[str] = None,
                    importance: str = "normal") -> None:
        msg = Message(
            role=role,
            content=content,
            sender=sender,
            receivers=receivers or ["*"],
            step_index=self.current_step,
            importance=importance,
        )
        if role == "tool":
            msg.tool_call_id = tool_call_id
            msg.tool_name = tool_name
        self.messages.append(msg)

    @staticmethod
    def create_assistant_message(sender: str, content: str,
                                 receivers: List[str] = None) -> Message:
        return Message(role="assistant", sender=sender, content=content,
                       receivers=receivers or ["*"])

    def add_user_message(self, agent_name: str, content: str,
                         receivers: List[str] = None) -> None:
        self.add_message(role="user", content=content, sender=agent_name,
                         receivers=receivers or ["*"], importance="critical")

    def add_assistant_message(self, agent_name: str, content: str,
                              receivers: List[str] = None) -> None:
        self.add_message(role="assistant", content=content, sender=agent_name,
                         receivers=receivers or ["*"])

    def add_tool_result(self, agent_name: str, result: str, tool_name: str,
                        tool_call_id: Optional[str] = None,
                        receivers: List[str] = None) -> None:
        self.add_message(role="tool", sender=agent_name, content=result,
                         tool_call_id=tool_call_id, tool_name=tool_name,
                         receivers=receivers or ["*"], importance="normal")

    def inject_summary(self, summary_text: str) -> None:
        """注入一条 LLM 生成的上下文摘要（独立消息，带时间戳）"""
        msg = Message(
            role="summary",
            content=summary_text,
            sender="ContextCompress",
            receivers=["*"],
            step_index=self.current_step,
            importance="normal",
        )
        self.messages.append(msg)
        self.context_summaries.append(msg)
        logger.info(f"上下文摘要已注入 (step {self.current_step}): {summary_text[:100]}...")

    # ============================================================
    # 消息检索（含记忆衰减）
    # ============================================================

    def _get_message_age(self, msg: Message) -> int:
        return self.current_step - msg.step_index

    def _is_error(self, content: str) -> bool:
        """检测消息是否包含错误"""
        lower = content.lower()
        return any(kw in lower for kw in
                   ["error", "exit_code: 1", "exit_code: 2", "failed",
                    "traceback", "exception", "denied", "not found"])

    def _truncate_content(self, content: str) -> str:
        """截断：保留前 N 行 + 后 M 行"""
        lines = content.split('\n')
        head = self.policy.truncate_head_lines
        tail = self.policy.truncate_tail_lines
        if len(lines) <= head + tail + 2:
            return content
        skipped = len(lines) - head - tail
        return '\n'.join(lines[:head]) + \
               f"\n... [中间省略 {skipped} 行] ...\n" + \
               '\n'.join(lines[-tail:])

    def _one_line_summary(self, msg: Message) -> str:
        """生成一行摘要"""
        who = msg.sender
        tool = msg.tool_name or "tool"
        content = msg.content.strip()
        # 取内容前 80 个字符作为摘要
        preview = content[:80].replace('\n', ' ').strip()
        if len(content) > 80:
            preview += "..."
        return f"[工具结果] {who}/{tool}: {preview}"

    def _format_message(self, msg: Message, agent_name: str,
                        effective_content: str) -> Dict[str, Any]:
        """格式化一条消息为 LLM 可读格式"""
        # summary 角色不被 LLM API 接受，映射为 user + 前缀
        if msg.role == "summary":
            item = {
                "role": "user",
                "content": f"[历史摘要]\n{effective_content}",
            }
        else:
            item = {"role": msg.role, "content": effective_content}

        if msg.role == "tool":
            item["tool_call_id"] = msg.tool_call_id
            item["name"] = msg.tool_name
        elif msg.sender != agent_name and msg.role != "system":
            item["name"] = msg.sender
        return item

    def get_agent_messages(self, agent_name: str,
                           include_system_prompt: bool = True) -> List[Dict[str, Any]]:
        """
        为特定 Agent 提取可见消息，应用记忆衰减策略。

        衰减规则（按消息年龄）:
        - age ≤ tool_full_turns: 完整内容
        - age ≤ tool_truncate_turns: 截断（保留头尾）
        - age ≤ tool_max_turns: 一行摘要
        - age > tool_max_turns: 跳过（彻底遗忘）

        例外:
        - importance="critical": 永不衰减
        - role="user" + keep_user_messages: 永不衰减
        - role="summary": 永不过滤（摘要消息本身就是压缩过的）
        - is_error + keep_errors: 永不衰减
        """
        formatted = []

        # 1. System prompt
        if include_system_prompt and agent_name in self.system_prompts:
            formatted.append({
                "role": "system",
                "content": self.system_prompts[agent_name]
            })

        # 2. 遍历消息，应用衰减
        for msg in self.messages:
            # 可见性检查
            is_broadcast = "*" in msg.receivers
            is_recipient = agent_name in msg.receivers
            is_self = msg.sender == agent_name

            if not (is_broadcast or is_recipient or is_self):
                continue

            age = self._get_message_age(msg)
            effective_content = msg.content

            # 永不衰减
            if msg.importance == "critical":
                pass  # keep full

            elif msg.role == "summary":
                # 摘要消息也不截断（已是压缩格式）
                pass

            elif msg.role == "user" and self.policy.keep_user_messages:
                pass  # user 消息永远完整

            elif msg.role == "tool":
                if self._is_error(msg.content) and self.policy.keep_errors:
                    pass  # 错误消息永远完整
                elif age <= self.policy.tool_full_turns:
                    pass  # 完整
                elif age <= self.policy.tool_truncate_turns:
                    effective_content = self._truncate_content(msg.content)
                elif age <= self.policy.tool_max_turns:
                    effective_content = self._one_line_summary(msg)
                else:
                    continue  # 彻底遗忘

            elif msg.role == "assistant":
                if age > self.policy.tool_max_turns * 2:
                    continue  # 旧的 assistant 消息也遗忘

            formatted.append(self._format_message(msg, agent_name, effective_content))

        return formatted

    def get_recent_messages(self, agent_name: str, limit: int = 5,
                            include_system_prompt: bool = True) -> List[Dict[str, Any]]:
        """只获取最近 N 条该 Agent 可见的消息（含衰减）"""
        all_msgs = self.get_agent_messages(agent_name, include_system_prompt)
        if len(all_msgs) <= limit + 1:
            return all_msgs
        if include_system_prompt and all_msgs:
            return [all_msgs[0]] + all_msgs[-limit:]
        return all_msgs[-limit:]

    def get_all_messages(self, agent_name: str = None,
                         include_system_prompt: bool = True) -> List[Dict[str, Any]]:
        """获取所有消息（不做衰减，用于调试和 Curator）"""
        formatted = []

        if include_system_prompt and agent_name and agent_name in self.system_prompts:
            formatted.append({
                "role": "system",
                "content": self.system_prompts[agent_name]
            })

        for msg in self.messages:
            role = "user" if msg.role == "summary" else msg.role
            content = f"[历史摘要]\n{msg.content}" if msg.role == "summary" else msg.content
            item = {"role": role, "content": content}
            if msg.role == "tool":
                item["tool_call_id"] = msg.tool_call_id
                item["name"] = msg.tool_name
            formatted.append(item)

        return formatted

    # ============================================================
    # 智能摘要
    # ============================================================

    def should_compress(self) -> bool:
        """是否需要触发上下文压缩"""
        if not self.policy.summary_enabled:
            return False
        interval = self.policy.summary_interval
        if interval <= 0:
            return False
        return self.current_step > 0 and self.current_step % interval == 0

    def collect_expired_messages(self) -> List[Message]:
        """收集已过期的消息（将被压缩/删除）"""
        expired = []
        for msg in self.messages:
            if msg.importance == "critical":
                continue
            if msg.role in ("system",):
                continue
            age = self._get_message_age(msg)
            if age > self.policy.tool_max_turns:
                expired.append(msg)
        return expired

    def mark_compressed(self, expired: List[Message]) -> None:
        """将已压缩的消息标记为删除（不实际删除，仅设置 step_index 使其被遗忘）"""
        for msg in expired:
            # 移到远古时间，确保下次检索时被跳过
            msg.step_index -= 9999

    # ============================================================
    # 清理
    # ============================================================

    def clear(self) -> None:
        """清空上下文"""
        self.messages.clear()
        self.context_summaries.clear()
        self.final_answer = None
        self.current_step = 0

    def format_history(self, format_type: str = "simple") -> str:
        """格式化历史消息"""
        if format_type == "simple":
            lines = [f"历史消息（共 {len(self.messages)} 条）:"]
            for i, msg in enumerate(self.messages, 1):
                content_preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
                lines.append(f"{i}. [{msg.role}] {content_preview}")
            return "\n".join(lines)
        elif format_type == "detailed":
            lines = [f"历史消息详情（共 {len(self.messages)} 条）:"]
            for i, msg in enumerate(self.messages, 1):
                lines.append(f"\n{i}. 角色:{msg.role} 发送者:{msg.sender} 接收者:{msg.receivers} step:{msg.step_index}")
                if msg.tool_name:
                    lines.append(f"   工具: {msg.tool_name}")
                lines.append(f"   内容: {msg.content}")
            return "\n".join(lines)
        elif format_type == "json":
            import json
            return json.dumps([{
                "role": m.role, "sender": m.sender,
                "content": m.content, "step": m.step_index
            } for m in self.messages], ensure_ascii=False, indent=2)
        return self.get_context_summary()

    # ============================================================
    # 状态追踪
    # ============================================================

    def add_state_trace(self, agent_name: str, from_state: str, to_state: str,
                        data: Optional[StateData] = None) -> None:
        self.state_trace.append(StateTrace(
            agent_name=agent_name, from_state=from_state, to_state=to_state, data=data))

    def get_state_trace(self) -> str:
        lines = [f"--- 状态转换追踪 (Total: {len(self.state_trace)}) ---"]
        for i, trace in enumerate(self.state_trace, 1):
            line = f"{i:02d}. [{trace.agent_name}] [{trace.from_state}] -> [{trace.to_state}]"
            lines.append(line)
            if trace.data:
                lines.append(f"    └─ {trace.data.format_for_log()}")
        return "\n".join(lines)

    def set_final_answer(self, answer: str) -> None:
        self.final_answer = answer

    def get_final_answer(self) -> str:
        return self.final_answer or "操作已完成"

    def get_context_summary(self) -> str:
        """返回上下文摘要"""
        return f"上下文: {len(self.messages)} 条消息, {len(self.context_summaries)} 条摘要, step={self.current_step}"
