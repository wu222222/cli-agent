
# NOTE

Agent : context , state_machine
state_machine : state
context: history

state状态转移的信息应该保存在哪？

- 应该保存在 state_machine 中，而不是 context 中。
- 因为 state_machine 是 Agent 的核心，负责管理状态的转换。
- 而 context 是 Agent 的上下文，负责存储对话历史。

如果state状态转移的信息既需要用于状态转移，又需要用于上下文管理呢？

- 同时保存在 state_machine 和 context 中。

ContextManager 在管理多个Agent时，共享context。

我先把worker agent 和 judge agent 分离。
我想建立一个group , group member 包含 worker agent 和 judge agent。他们通过通信协议，传递消息。