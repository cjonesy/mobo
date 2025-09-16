# Mobo Architecture

This document outlines key architectural decisions and patterns used in the Mobo Discord bot.

## Core Architecture

### LangGraph Workflow Pattern

We use LangGraph for conversation management with the following pattern:

```
load_context → chatbot (supervisor) → tools → message_generator → save_conversation → END
```

**Key Decision**: Follow proper LangGraph patterns instead of manual state management.

### Node Responsibilities

#### Chatbot Node (Supervisor)
- **Role**: Decides what tools to use based on personality and context
- **Pattern**: Returns state updates, lets LangGraph handle message flow automatically
- **Key Decision**: Simplified from manual message state management to proper LangGraph patterns

#### Tool Node
- **Role**: Executes tool calls automatically
- **Pattern**: Uses LangGraph's built-in ToolNode for automatic tool execution
- **Key Decision**: Let framework handle tool call/response pairing

#### Message Generator Node
- **Role**: Creates final personality-driven response
- **Pattern**: Takes tool results and generates user-facing message

### State Management

**Key Decision**: Use LangGraph's built-in state management rather than manual message handling.

- **Messages**: Managed automatically by LangGraph checkpointer
- **Tool Calls**: Framework handles tool call/response lifecycle
- **Persistence**: PostgreSQL with AsyncPostgresSaver and PostgresStore

### Tool Call Architecture

**Problem Solved**: Tool call/response mismatch errors when manually managing conversation state.

**Solution**:
1. Chatbot node returns AI message with tool calls
2. LangGraph automatically routes to tool execution
3. ToolNode executes tools and adds responses to state
4. Framework manages complete tool call/response pairs

**Anti-pattern Avoided**: Manual conversation history reconstruction that can create orphaned tool calls.

## Component Architecture

### Configuration Management
- Pydantic models for type safety
- Environment variable validation
- Centralized settings with `get_settings()`

### Tool System
- Decorator-based tool registration (`@registered_tool()`)
- Google-style docstrings with detailed JSON response structures
- Runtime context injection via RunnableConfig

### Discord Integration
- Event-driven message handling
- Per-message workflow execution
- Context injection for Discord-specific tools

## Key Architectural Decisions

### 1. LangGraph Over Custom State Management
**Decision**: Use LangGraph's built-in patterns for conversation flow
**Rationale**: Reduces complexity, prevents tool call/response mismatches
**Impact**: Simplified codebase, more reliable tool execution

### 2. Tool Registration Pattern
**Decision**: Centralized tool registry with decorator pattern
**Rationale**: Easy to add/remove tools, automatic discovery
**Impact**: Scalable tool system

### 3. PostgreSQL for Persistence
**Decision**: Use PostgreSQL for both conversation storage and LangGraph checkpointing
**Rationale**: ACID compliance, rich querying capabilities
**Impact**: Reliable state persistence, conversation history

### 4. Supervisor Pattern for Tool Selection
**Decision**: Separate LLM for tool selection vs. message generation
**Rationale**: Personality consistency, better tool usage decisions
**Impact**: More coherent personality, strategic tool usage

### 5. Context Injection Over Direct Access
**Decision**: Inject Discord context via RunnableConfig rather than global access
**Rationale**: Better testability, cleaner dependencies
**Impact**: More maintainable tool system

## Logging and Observability

### LangGraph Built-in Logging
**Decision**: Use LangGraph's built-in logging instead of manual workflow tracking
**Rationale**: Reduces code complexity, automatic tool call logging, standard framework patterns
**Implementation**:
- Enable LangGraph debug logging: `logging.getLogger("langgraph").setLevel(logging.DEBUG)`
- Automatic node entry/exit logging
- Automatic tool call/response logging
- Built-in state transition tracking

### Removed Manual Logging
- ❌ Manual `log_workflow_step()` calls in each node
- ❌ Custom `workflow_path` state tracking
- ❌ Verbose logging messages with emojis
- ✅ LangGraph handles execution flow automatically
- ✅ Tool calls logged by framework
- ✅ Cleaner, more maintainable code

## Error Handling

### Tool Call Errors
- Graceful fallback when tool execution fails
- Continue workflow to message generation
- Log errors for debugging

### LLM Errors
- Catch and log LLM API errors
- Return minimal state to continue workflow
- Prevent conversation state corruption

## Testing Strategy

### Unit Tests
- Test individual nodes with mocked dependencies
- Validate state transformations
- Tool execution testing

### Integration Tests
- End-to-end workflow testing
- Database persistence validation
- Discord integration testing

## Future Considerations

### Scalability
- Consider horizontal scaling with multiple bot instances
- Tool execution rate limiting already in place
- Database connection pooling configured

### Monitoring
- Structured logging for observability
- Workflow path tracking
- Performance metrics collection

### Security
- No credential exposure in logs
- Rate limiting for tool usage
- Input validation for tool parameters