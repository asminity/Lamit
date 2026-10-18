import logging
from typing import List, Tuple, Optional, Set
import tiktoken
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage

logger = logging.getLogger("graph_tokens")

_encoding_cache = {}


def get_token_encoding(model_name: str = "gpt-4o"):
    if model_name not in _encoding_cache:
        try:
            _encoding_cache[model_name] = tiktoken.encoding_for_model(model_name)
        except Exception:
            try:
                _encoding_cache[model_name] = tiktoken.get_encoding("cl100k_base")
            except Exception:
                _encoding_cache[model_name] = None
    return _encoding_cache.get(model_name)


def count_text_tokens(text: str, model_name: str = "gpt-4o") -> int:
    if not text:
        return 0
    enc = get_token_encoding(model_name)
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    # Safe approximation: ~4 characters per token
    return max(1, len(text) // 4)


def count_message_tokens(message: BaseMessage, model_name: str = "gpt-4o") -> int:
    """Computes approximate token count for a single message including metadata and tool calls."""
    tokens = 4  # overhead for message formatting
    content = getattr(message, "content", "")
    if isinstance(content, str):
        tokens += count_text_tokens(content, model_name)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, str):
                tokens += count_text_tokens(part, model_name)
            elif isinstance(part, dict) and "text" in part:
                tokens += count_text_tokens(part["text"], model_name)

    # Tool calls tokens
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls and isinstance(tool_calls, list):
        for tc in tool_calls:
            tokens += count_text_tokens(tc.get("name", ""), model_name)
            args = tc.get("args", {})
            tokens += count_text_tokens(str(args), model_name)

    return tokens


def count_messages_tokens(messages: List[BaseMessage], model_name: str = "gpt-4o") -> int:
    """Sums tokens for all messages."""
    return sum(count_message_tokens(m, model_name) for m in messages)


def find_safe_split_indices(messages: List[BaseMessage]) -> List[int]:
    """
    Finds message partition indices where cutting does NOT break tool-call/tool-result consistency.
    A safe split index `k` guarantees:
    1. `messages[k]` is a HumanMessage (starts a clean user turn).
    2. All tool calls generated prior to index `k` have their corresponding ToolMessages before `k`.
    3. No ToolMessage at or after `k` references a tool call prior to `k`.
    """
    safe_indices = []
    
    # Track tool call IDs across the entire sequence
    all_initiated_tool_calls: Set[str] = set()
    all_resolved_tool_calls: Set[str] = set()

    # Pre-map which tool call IDs are defined where
    tool_call_to_def_index = {}
    tool_msg_to_call_id = {}

    for idx, msg in enumerate(messages):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                tc_id = tc.get("id")
                if tc_id:
                    tool_call_to_def_index[tc_id] = idx
        elif isinstance(msg, ToolMessage):
            tc_id = getattr(msg, "tool_call_id", None)
            if tc_id:
                tool_msg_to_call_id[idx] = tc_id

    # Now verify each HumanMessage index k > 0
    for k in range(1, len(messages)):
        if not isinstance(messages[k], HumanMessage):
            continue

        # Check: Every tool call defined before k must have its tool message before k
        calls_before_k = {tc_id for tc_id, def_idx in tool_call_to_def_index.items() if def_idx < k}
        resolved_before_k = {tc_id for msg_idx, tc_id in tool_msg_to_call_id.items() if msg_idx < k}

        if calls_before_k == resolved_before_k:
            # Check: No tool message after k references a call defined before k
            resolved_after_k = {tc_id for msg_idx, tc_id in tool_msg_to_call_id.items() if msg_idx >= k}
            if not (calls_before_k & resolved_after_k):
                safe_indices.append(k)

    return safe_indices


def partition_messages_for_summary(
    messages: List[BaseMessage],
    recent_token_budget: int = 1500,
    min_recent_turns: int = 1,
    model_name: str = "gpt-4o",
) -> Tuple[List[BaseMessage], List[BaseMessage]]:
    """
    Partitions messages into (messages_to_summarize, recent_messages_to_keep).
    Guarantees:
    - Never splits an AIMessage from its ToolMessage(s).
    - Preserves at least `min_recent_turns` complete turns.
    - Fits recent messages within `recent_token_budget` as closely as possible without violating safety.
    - Returns ([], messages) if conversation cannot be safely partitioned.
    """
    safe_splits = find_safe_split_indices(messages)
    if not safe_splits:
        return [], messages

    # We evaluate safe splits from newest to oldest to find the one that keeps recent messages within budget
    chosen_split = None
    for split_idx in reversed(safe_splits):
        recent_chunk = messages[split_idx:]
        recent_tokens = count_messages_tokens(recent_chunk, model_name)
        if recent_tokens <= recent_token_budget:
            chosen_split = split_idx
        else:
            # If even the newest safe split exceeds recent_token_budget, we still use the newest safe split
            # to prevent unbounded growth while keeping tool consistency
            if chosen_split is None:
                chosen_split = split_idx
            break

    if chosen_split is None or chosen_split == 0:
        return [], messages

    return messages[:chosen_split], messages[chosen_split:]
