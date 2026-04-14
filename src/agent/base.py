@dataclass
class AgentResponse:
    content: str
    action_type: str  # execute_command, stop
    action_params: Dict[str, Any]
    requires_confirmation: bool = False
    confirmation_prompt: str = ""

class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING_CONFIRMATION = "waiting_confirmation"
    COMPLETED = "completed"
    ERROR = "error"