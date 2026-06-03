# Contributing to Safe-CLI-Agent

Thank you for your interest in contributing! This document provides guidelines and standards for development.

## Table of Contents

- [Development Philosophy](#development-philosophy)
- [Architecture Overview](#architecture-overview)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Git Workflow](#git-workflow)
- [Testing](#testing)
- [Building & Releasing](#building--releasing)

---

## Development Philosophy

### 1. Don't Be Overconfident — Ask Before Acting

- When encountering an uncertain problem, **present options to the user first** rather than blindly implementing a solution
- If there are multiple possible approaches, **list the pros and cons** of each before proceeding
- If you're unsure about the root cause, **discuss your analysis** with the user before coding

### 2. Communicate More, Code Less

- **Discuss before implementing**: Talk through the design with the user to find a solution that better fits their needs
- **Present trade-offs**: "Approach A is faster but harder to maintain; Approach B is slower but cleaner. Which do you prefer?"
- **Don't assume**: What seems "obvious" to you may not match the user's mental model

### 3. Sometimes the Best Code Is No Code

- Before writing code, ask: **"Is there a simpler way to solve this?"**
- Consider: Could a configuration change, a UI tweak, or a workflow adjustment solve the problem without new code?
- **Think twice, code once**: Spending 5 minutes discussing can save hours of refactoring

### 4. User Experience First

- **Every interaction matters**: Loading states, error messages, confirmations — these shape the user's trust
- **Fail gracefully**: When something goes wrong, tell the user what happened and what they can do about it
- **Respect the user's time**: Don't make them wait without feedback, don't make them click without purpose

### 5. Incremental Improvement

- **Small, tested changes** are better than big, risky rewrites
- **Fix one thing at a time** — verify it works, then move to the next
- **Document what you learned** — if you found a tricky issue, add a comment or update the docs

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Electron Desktop App                       │
├─────────────┬───────────────────────────────────┬───────────────┤
│   Main      │         Renderer (Vue 3)          │    Preload    │
│   Process   │                                   │    Bridge     │
│             │  ┌─────────────────────────────┐  │               │
│  - Window   │  │  ChatView / SetupView / ... │  │  - IPC API    │
│  - IPC      │  │  Components / Stores        │  │  - Security   │
│  - Python   │  │  Composables / Router       │  │    Context    │
│    Manager  │  └─────────────────────────────┘  │               │
├─────────────┴───────────────────────────────────┴───────────────┤
│                    FastAPI Backend (Python)                      │
├─────────────────────────────────────────────────────────────────┤
│  Routes (API)  →  Services  →  Agent System  →  Executor/Docker │
├─────────────────────────────────────────────────────────────────┤
│  Agent Layer: WorkerAgent / JudgeAgent / CuratorAgent            │
│  State Machine: IDLE → THINKING → EXECUTING → COMPLETED         │
│  Context Manager: Memory decay, incremental summarization       │
│  Plugin System: YAML-driven, exec/command/compose/local types   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Directories

| Directory | Description |
|-----------|-------------|
| `electron/src/` | Electron main process (TypeScript) |
| `frontend/src/` | Vue 3 frontend application |
| `src/agent/` | Agent framework (state machine, context, prompts) |
| `src/api/` | FastAPI routes and services |
| `src/executor/` | Docker container management |
| `src/llm/` | LLM client wrapper (OpenAI-compatible) |
| `config/` | Plugin YAML configs, context policy |

---

## Development Setup

### Prerequisites

- **Python 3.10+** (conda recommended)
- **Node.js 18+**
- **Docker Desktop** (running)
- **LLM API Key** (OpenAI-compatible format)

### Quick Start

```bash
# 1. Clone
git clone https://github.com/wu222222/cli-agent.git
cd cli-agent

# 2. Python environment
conda create -n safe-cli-agent python=3.10
conda activate safe-cli-agent
pip install -r requirements.txt
pip install ruff pytest  # dev dependencies

# 3. Frontend
cd frontend && npm install && cd ..

# 4. Start (dev mode)
npm run dev
```

### Development Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Electron + backend in dev mode |
| `npm run dev:backend` | Start Python backend only |
| `npm run dev:frontend` | Start Vue dev server only |
| `npm run typecheck` | TypeScript type checking |
| `npm run build:win` | Build Windows installer |

---

## Code Standards

### Python Standards

#### Naming Conventions

```python
# Variables, functions, methods → snake_case
def calculate_score():
    user_name = "test"

# Classes → PascalCase
class ContextManager:
    pass

# Constants → UPPER_SNAKE_CASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30

# Private attributes → prefix with underscore
class Agent:
    def __init__(self):
        self._internal_state = None
        self.__private = None  # name mangling (rare)
```

#### Type Annotations (Required)

All public functions and methods MUST have type annotations:

```python
# ✅ Good
def process_message(content: str, sender: str) -> dict[str, Any]:
    ...

# ✅ Good - Optional types
def get_tool(name: str) -> Optional[Tool]:
    ...

# ❌ Bad - No type annotations
def process_message(content, sender):
    ...
```

#### Logging (Never use `print`)

```python
from src.logger import get_logger

logger = get_logger(__name__)

# ✅ Good
logger.info(f"Processing message: {message_id}")
logger.warning(f"Retry attempt {attempt}/{max_retries}")
logger.error(f"Failed to connect: {e}")

# ❌ Bad
print(f"Processing: {message_id}")
```

#### Error Handling (Never swallow exceptions silently)

```python
# ✅ Good - Log and re-raise or return error
try:
    result = await execute_command(cmd)
except DockerError as e:
    logger.error(f"Docker execution failed: {e}")
    return {"success": False, "error": str(e)}

# ❌ Bad - Silent failure
try:
    result = await execute_command(cmd)
except:
    pass
```

#### Import Order

```python
# 1. Standard library
import os
import json
from typing import Dict, List, Optional

# 2. Third-party
from fastapi import APIRouter
from pydantic import BaseModel

# 3. Local modules
from src.agent.types import AgentState
from src.logger import get_logger
```

#### Ruff Configuration

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Check code
ruff check src/

# Format code
ruff format src/

# Fix auto-fixable issues
ruff check --fix src/
```

---

### TypeScript / Vue Standards

#### Naming Conventions

```typescript
// Variables, functions → camelCase
const userName = 'test'
function handleClick() { ... }

// Components → PascalCase
// Files: PascalCase.vue
MessageBubble.vue
HistoryPanel.vue

// Interfaces/Types → PascalCase
interface ChatResponse { ... }
type ToolStatus = 'running' | 'stopped'

// Constants → UPPER_SNAKE_CASE or camelCase
const MAX_CMD_LEN = 120
const defaultTimeout = 60000
```

#### Vue Component Structure

```vue
<template>
  <!-- Template first -->
</template>

<script setup lang="ts">
// Script setup with TypeScript
import { ref, computed } from 'vue'
import type { Message } from '@/types'

// Props definition (Type-based)
const props = defineProps<{
  message: Message
  editable?: boolean
}>()

// Emits definition
const emit = defineEmits<{
  (e: 'update', value: string): void
  (e: 'delete'): void
}>()

// Reactive state
const isExpanded = ref(false)

// Computed
const displayContent = computed(() => { ... })

// Methods
function handleClick() { ... }
</script>

<style scoped>
/* Scoped styles */
</style>
```

#### State Management (Pinia Store)

```typescript
// stores/chat.ts
import { reactive } from 'vue'

// Use reactive() for simple stores (current pattern)
const store = reactive({
  messages: [] as Message[],
  isThinking: false,
  // ...
})

export function useChatStore() {
  return store
}
```

---

### Electron Standards

#### IPC Channel Definition

All IPC channels MUST be defined in `electron/src/ipc-channels.ts`:

```typescript
// ipc-channels.ts
export interface IpcChannelMap {
  'channel-name': { input: InputType; output: OutputType }
}
```

#### Path Handling

Always use `app.asar.unpacked` (with 'd') for unpacked resources:

```typescript
// ✅ Good
const configPath = app.isPackaged
  ? path.join(process.resourcesPath, 'app.asar.unpacked', 'config', 'config.json')
  : path.join(__dirname, '../../config/config.json')

// ❌ Bad - Missing 'd'
const configPath = path.join(process.resourcesPath, 'app.asar.unpack', ...)
```

#### Security

- Enable `contextIsolation: true`
- Disable `nodeIntegration: false`
- Use `contextBridge.exposeInMainWorld()` for renderer API

---

## Git Workflow

### Branch Strategy

```
main          ← Production releases only
  └── dev     ← Development branch
       └── feature/xxx   ← Feature branches
       └── fix/xxx       ← Bug fix branches
```

### Commit Messages (Conventional Commits)

Format: `<type>(<scope>): <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Build process, dependencies
- `perf`: Performance improvement

Examples:

```
feat(agent): add incremental context summarization
fix(electron): resolve Python path detection on Windows
docs(readme): update installation instructions
refactor(api): extract session management to separate module
test(agent): add unit tests for state machine transitions
```

### Pull Request Process

1. Create feature branch from `dev`
2. Make changes with proper commits
3. Write/update tests if needed
4. Ensure all checks pass
5. Create PR to `dev` branch
6. Request review
7. Squash merge after approval

### Code Review Checklist

Before submitting PR, verify:

- [ ] Code follows naming conventions
- [ ] Type annotations are complete (Python & TypeScript)
- [ ] No `print()` statements (use logger)
- [ ] No empty `catch/except` blocks
- [ ] Error messages are user-friendly
- [ ] No hardcoded paths (use relative or config)
- [ ] Tests added for new functionality
- [ ] Documentation updated if needed

---

## Testing

### Python Tests (pytest)

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/test_agent.py -v
```

Test file structure:

```
tests/
├── test_agent/
│   ├── test_statemachine.py
│   └── test_context.py
├── test_api/
│   └── test_routes.py
└── conftest.py
```

Example test:

```python
# tests/test_agent/test_statemachine.py
import pytest
from src.agent.statemachine import WorkerStateMachine
from src.agent.types import AgentState

class TestWorkerStateMachine:
    def test_initial_state(self):
        sm = WorkerStateMachine()
        assert sm.is_in_state(AgentState.IDLE)
    
    def test_transition_to_thinking(self):
        sm = WorkerStateMachine()
        sm.set_agent(mock_agent)
        assert sm.transition(AgentState.THINKING) is True
        assert sm.is_in_state(AgentState.THINKING)
```

### Frontend Tests (vitest)

```bash
cd frontend

# Run tests
npm run test

# Run with coverage
npm run test:coverage
```

Example test:

```typescript
// src/components/__tests__/MessageBubble.test.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageBubble from '../MessageBubble.vue'

describe('MessageBubble', () => {
  it('renders message content', () => {
    const wrapper = mount(MessageBubble, {
      props: {
        message: {
          role: 'system',
          content: 'Hello',
          timestamp: '12:00',
          thought: '',
          type: 'text',
        }
      }
    })
    expect(wrapper.text()).toContain('Hello')
  })
})
```

---

## Building & Releasing

### Version Management

Version is defined in `package.json`:

```json
{
  "version": "1.0.3"
}
```

Update version before release:

```bash
npm version patch  # 1.0.3 → 1.0.4
npm version minor  # 1.0.4 → 1.1.0
npm version major  # 1.1.0 → 2.0.0
```

### Build Process

```bash
# Build frontend
cd frontend && npm run build && cd ..

# Build Electron app
npm run build:win    # Windows
npm run build:mac    # macOS
npm run build:linux  # Linux
```

### Release Checklist

1. Update version in `package.json`
2. Update CHANGELOG.md
3. Run full test suite
4. Build installer
5. Test installer on clean machine
6. Create GitHub Release
7. Upload installer to Release

---

## Common Issues

### Port Already in Use

```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process
taskkill /PID <pid> /F
```

### Docker Permission Issues

```bash
# Windows: Run Docker Desktop as Administrator
# Linux: Add user to docker group
sudo usermod -aG docker $USER
```

### Python Environment Issues

```bash
# Reset conda environment
conda deactivate
conda env remove -n safe-cli-agent
conda create -n safe-cli-agent python=3.10
conda activate safe-cli-agent
pip install -r requirements.txt
```

---

## Questions?

Open an issue on GitHub or contact the maintainers.

Thank you for contributing! 🎉
