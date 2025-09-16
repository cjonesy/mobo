# 🤖 Mobo - Intelligent Discord AI Bot

A sophisticated Discord bot powered by LangGraph with RAG memory, adaptive user learning, and comprehensive tool integration.

## 🚀 Features

### ✅ **LangGraph Workflow Architecture**

- **Multi-node StateGraph** with load context → supervisor → tools → context learning → message generation
- **Supervisor pattern** for intelligent tool selection and response orchestration
- **Conditional routing** based on tool requirements and conversation flow
- **Async execution** with proper error handling and state management

### ✅ **Advanced RAG Memory System**

- **PostgreSQL + pgvector** for semantic similarity search
- **OpenAI embeddings** (text-embedding-3-small) for message vectorization
- **Hybrid context retrieval** combining recent + semantically relevant conversations
- **Persistent conversation memory** across Discord sessions
- **Configurable similarity thresholds** and context limits

### ✅ **Adaptive User Context Learning**

- **Real-time interaction analysis** using LLM-powered conversation assessment
- **Dynamic response tone adaptation** based on user communication patterns
- **Automatic preference learning** (likes/dislikes from conversation context)
- **Conservative learning approach** to prevent over-adjustments
- **Bot-centric strategy** - learns how the bot should interact with each user

### ✅ **Comprehensive Tool System**

**Communication & Social:**
- Emoji reactions and custom stickers
- Discord polls for group decisions
- Activity status management
- User profile and member information

**AI-Powered Features:**
- Image analysis with OpenAI Vision
- DALL-E avatar generation and customization
- Web search with Google Custom Search
- URL content fetching and summarization

**Server Management:**
- Channel listing and information
- Custom emoji and sticker discovery
- User mention and interaction tools

### ✅ **Smart Discord Integration**

- **Mention-based triggering** (@bot or replies to bot messages)
- **Typing indicators** during processing
- **Rate limiting** with per-resource controls
- **Structured Pydantic responses** for all tool outputs

## 🛠️ Tech Stack

| Component            | Technology                    |
| -------------------- | ----------------------------- |
| **Language**         | Python 3.11+                  |
| **Bot Framework**    | discord.py                    |
| **AI Orchestration** | LangGraph                     |
| **LLM Provider**     | OpenAI GPT-4o                 |
| **Embeddings**       | OpenAI text-embedding-3-small |
| **Vector Store**     | PostgreSQL + pgvector         |
| **Database**         | PostgreSQL (async)            |
| **Configuration**    | Pydantic Settings             |

## 📋 Prerequisites

- Python 3.11 or higher
- PostgreSQL with pgvector extension
- Discord Bot Token
- OpenAI API Key

## 🔧 Installation

1. **Clone and setup**:

```bash
git clone <your-repo>
cd mobo
```

2. **Install dependencies**:

```bash
pip install -e .
# or with uv (recommended)
uv pip install -e .
```

3. **Set up PostgreSQL with pgvector**:

```bash
# Install pgvector extension in your PostgreSQL database
CREATE EXTENSION vector;
```

4. **Configure environment variables**:

```bash
cp .env.example .env
# Edit .env with your configuration
```

### Environment Variables

Create a `.env` file with the following:

**Note**: All environment variables now use the `MOBO_` prefix. Nested settings (Discord, OpenRouter) use double underscores (`__`).

```env
# Required (all variables use MOBO_ prefix)
MOBO_DISCORD__TOKEN=your_discord_bot_token
MOBO_OPENROUTER__API_KEY=your_openrouter_api_key
MOBO_OPENAI_API_KEY=your_openai_api_key

# Database
MOBO_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mobo

# OpenRouter Configuration
MOBO_OPENROUTER__BASE_URL=https://openrouter.ai/api/v1

# Bot Configuration
MOBO_MAX_BOT_RESPONSES=3
MOBO_SUPERVISOR_LLM__MODEL=openai/gpt-4o
MOBO_SUPERVISOR_LLM__TEMPERATURE=0.7

# Response LLM Configuration
MOBO_RESPONSE_LLM__MODEL=openai/gpt-4.1
MOBO_RESPONSE_LLM__TEMPERATURE=0.8
# Memory and RAG Configuration
MOBO_SIMILARITY_THRESHOLD=0.7          # Minimum similarity for relevant conversations (0.0-1.0)
MOBO_RECENT_MESSAGES_LIMIT=5           # Number of recent messages in context (1-20)
MOBO_RELEVANT_MESSAGES_LIMIT=3         # Number of relevant messages in context (0-10)

# Image Generation
MOBO_IMAGE_MODEL=dall-e-3
MOBO_IMAGE_SIZE=1024x1024
MOBO_IMAGE_QUALITY=standard
MOBO_IMAGE_DAILY_LIMIT=20
MOBO_IMAGE_HOURLY_LIMIT=2

# Logging
MOBO_LOG_LEVEL=INFO
```

## 🚀 Usage

1. **Check configuration**:

```bash
mobo check-config
```

2. **Initialize database**:

```bash
mobo init-db
```

3. **Run the bot**:

```bash
mobo run
```

### CLI Commands

- `mobo run` - Start the Discord bot
- `mobo check-config` - Validate configuration
- `mobo init-db` - Initialize database schema
- `mobo --help` - Show all available commands

## 🏗️ Architecture

### LangGraph Workflow

```mermaid
graph TD
    A[Discord Message] --> B[Load Context]
    B --> C[RAG Memory Lookup]
    B --> D[User Profile Retrieval]
    C --> E[Supervisor LLM]
    D --> E
    E --> F{Tool Calls?}
    F -->|Yes| G[Execute Tools]
    F -->|No| H[Learn User Context]
    G --> H
    H --> I[Generate Response]
    I --> J[Save Conversation]
    J --> K[Discord Response]
```

### Project Structure

```
src/mobo/
├── core/                         # Core workflow logic
│   ├── workflow.py              # Main LangGraph StateGraph
│   ├── state.py                 # Bot state management
│   ├── message_generator.py     # Response generation node
│   └── learn_user_context_node.py  # Context learning node
├── models/                      # Database models
│   ├── base.py                  # Base model classes
│   └── user.py                  # User profile models
├── services/                    # Business logic
│   ├── user_service.py          # User profile management
│   └── rate_limiting.py         # Rate limiting service
├── tools/                       # LangGraph tools
│   ├── discord_tools.py         # Discord-specific tools
│   ├── web_tools.py             # Web search and URL tools
│   ├── common.py                # Tool decorators
│   └── schemas.py               # Tool response schemas
├── utils/                       # Utilities
│   ├── embeddings.py            # OpenAI embedding generation
│   └── rate_limiting.py         # Rate limiting decorators
├── db.py                        # Database connection
├── config.py                    # Configuration management
└── main.py                      # Entry point
```

## 🎯 Key Features

### Adaptive Context Learning

The bot learns how to interact with each user individually:

- **Dynamic response tone adaptation** - Adjusts communication style based on user patterns
- **Preference learning** - Automatically discovers what users like/dislike from conversation
- **Conservative updates** - Only changes strategy when there's clear evidence
- **Bot-centric approach** - Learns the bot's optimal interaction strategy, not user preferences

### Advanced RAG Memory

- **Semantic search** using OpenAI embeddings and PostgreSQL pgvector
- **Hybrid context retrieval** combining recent + semantically relevant messages
- **Persistent conversation memory** across Discord sessions
- **Configurable similarity thresholds** for fine-tuning relevance

### LangGraph Workflow Architecture

- **Supervisor pattern** - Intelligent tool selection and orchestration
- **Multi-node StateGraph** - Load Context → Supervisor → Tools → Learn Context → Generate Response
- **Conditional routing** - Dynamic flow based on tool requirements
- **Async execution** with comprehensive error handling

### Comprehensive Tool Integration

- **Discord native tools** - Reactions, polls, stickers, channel management
- **AI-powered features** - Vision analysis, DALL-E generation, web search
- **Rate-limited execution** - Per-resource limits to prevent abuse
- **Structured responses** - Type-safe Pydantic schemas for all outputs

## 🔧 Customization

### Adding New Tools

Create new tools in `src/mobo/tools/`:

```python
from .common import tool
from .schemas import MyToolResponse

@tool
async def my_custom_tool(parameter: str) -> MyToolResponse:
    """Description of what the tool does.

    Args:
        parameter: Description of parameter

    Returns:
        Structured tool response
    """
    # Your tool logic here
    return MyToolResponse(success=True, result="Tool response")
```

Add to the tool registry in `src/mobo/tools/__init__.py`.

### Context Learning Configuration

Control how the bot learns and adapts:

```env
# Context Learning LLM (uses cheaper model for analysis)
MOBO_CONTEXT_LEARNING_LLM__MODEL=openai/gpt-4o-mini
MOBO_CONTEXT_LEARNING_LLM__TEMPERATURE=0.1

# Learning behavior
MOBO_ENABLE_CONTEXT_LEARNING=true          # Enable/disable learning
MOBO_LEARNING_CONFIDENCE_THRESHOLD=0.7     # How confident analysis must be
```

### Memory and RAG Configuration

The bot uses semantic similarity to find relevant past conversations. You can
tune these settings:

```env
# How similar past conversations need to be to include in context (0.0-1.0)
# Lower values = more conversations included, higher values = only very similar ones
MOBO_SIMILARITY_THRESHOLD=0.7

# Number of recent messages to always include (1-20)
MOBO_RECENT_MESSAGES_LIMIT=5

# Number of semantically relevant messages to include (0-10)
MOBO_RELEVANT_MESSAGES_LIMIT=3
```

**Examples:**

- `MOBO_SIMILARITY_THRESHOLD=0.9` - Only include very similar conversations
- `MOBO_SIMILARITY_THRESHOLD=0.5` - Include more loosely related conversations
- `MOBO_RECENT_MESSAGES_LIMIT=10` - Include more recent context
- `MOBO_RELEVANT_MESSAGES_LIMIT=0` - Disable semantic search, only use recent
  messages

### Database Configuration

The bot automatically creates the required database schema. For custom setups:

```python
# Custom database configuration
MOBO_DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
DATABASE_ECHO=true  # Enable SQL logging
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
```

## 📊 Monitoring & Logs

- **Structured logging** with configurable levels
- **Database query logging** (optional)
- **Tool execution tracking**
- **Error handling** with user-friendly messages

## 🔒 Security

- **Environment variable** configuration for secrets
- **Database connection pooling** with proper cleanup
- **Error message sanitization** to prevent information leakage
- **Rate limiting** through OpenAI client configuration

## 🤝 Contributing

1. Follow existing code patterns and documentation
2. Add type hints to all functions
3. Include comprehensive error handling
4. Test with both bot and human users
5. Update documentation for new features

## 📝 License

MIT License - see LICENSE file for details.

---

**Built with ❤️ using LangGraph, OpenAI, and PostgreSQL**
