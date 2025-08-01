# 🤖 Discord AI Bot (LangGraph + RAG)

A Discord bot powered by LangGraph with intelligent RAG conversation memory,
user profiles, and anti-bot loop protection.

## 🚀 Features

### ✅ **LangGraph Workflow**

- **StateGraph-based agent** with nodes for context retrieval, LLM processing,
  tool execution, and profile updates
- **Conditional edges** for intelligent tool calling flow
- **Async tool execution** with proper error handling

### ✅ **RAG Memory System**

- **PostgreSQL + pgvector** for semantic similarity search
- **OpenAI embeddings** for message vectorization
- **Context-aware responses** using similar past conversations
- **Long-term memory** that persists across sessions

### ✅ **User Profile Tracking**

- **Dynamic user profiles** with likes, dislikes, and interaction tone
- **Personalized responses** based on user history
- **Automatic profile updates** from conversation analysis

### ✅ **Anti-Bot Loop Protection**

- **Configurable interaction limits** to prevent bot-to-bot loops
- **Automatic reset** when humans join conversations
- **Smart bot detection** and response throttling

### ✅ **Smart Message Triggering**

- Only responds when **@mentioned** or **replying to bot messages**
- **Context-aware** message processing with personality preservation
- **Typing indicators** during response generation

### ✅ **Tool System**

- **Image generation** with DALL-E integration
- **Nickname management** (self-changing capability)
- **User mention** functionality
- **Profile management** tools
- **Extensible tool framework** for easy additions

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

```env
# Required
DISCORD_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mobo

# Bot Configuration
MAX_BOT_RESPONSES=3
TOP_K_MEMORY_RESULTS=5
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.7

# Image Generation
IMAGE_MODEL=dall-e-3
IMAGE_SIZE=1024x1024
IMAGE_QUALITY=standard
IMAGE_DAILY_LIMIT=20
IMAGE_HOURLY_LIMIT=2

# Logging
LOG_LEVEL=INFO
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
    A[User Message] --> B[Get Context]
    B --> C[RAG Memory Lookup]
    B --> D[User Profile Retrieval]
    C --> E[LLM with Tools]
    D --> E
    E --> F{Tool Calls?}
    F -->|Yes| G[Execute Tools]
    F -->|No| H[Update Profiles]
    G --> H
    H --> I[Store in Memory]
    I --> J[Response]
```

### Project Structure

```
mobo/
├── agent/                    # LangGraph agent logic
│   ├── agent_graph.py       # StateGraph implementation
│   ├── memory.py            # RAG memory system
│   ├── user_profiles.py     # User profile management
│   ├── bot_interaction_tracker.py  # Anti-loop protection
│   └── tools.py             # LangGraph tools
├── bot/                     # Discord client
│   ├── client.py            # Discord bot client
│   ├── message_handler.py   # Message processing
│   └── config.py            # Configuration management
├── data/                    # Static data
│   └── personality.txt      # Bot personality prompt
└── cli.py                   # Command line interface
```

## 🎯 Key Features

### Personality Preservation

The bot maintains consistent personality through conversation by:

- Wrapping personality prompts with preservation instructions
- Injecting personality context into every LLM call
- Supporting file-based, URL-based, or direct personality configuration

### RAG Memory System

- **Semantic search** using OpenAI embeddings and pgvector
- **Context retrieval** of similar past conversations
- **Recent message** continuity for natural conversation flow
- **Automatic storage** of all user and bot messages

### User Profiles

- **Dynamic tone tracking** (friendly, neutral, rude)
- **Interest tracking** (likes and dislikes)
- **Custom tags** for additional metadata
- **Automatic profile updates** based on interactions

### Anti-Bot Loop Protection

- **Configurable limits** for bot-to-bot interactions
- **Automatic detection** of bot users
- **Smart reset** when humans join conversations
- **Prevents infinite loops** between multiple bots

## 🔧 Customization

### Adding New Tools

Create new tools in `agent/tools.py`:

```python
@tool
async def my_custom_tool(parameter: str) -> str:
    """Description of what the tool does.

    Args:
        parameter: Description of parameter

    Returns:
        Tool response
    """
    # Your tool logic here
    return "Tool response"
```

Add to the tool list in `get_all_tools()`.

### Modifying Personality

Edit `data/personality.txt` or set environment variables:

```env
PERSONALITY_PROMPT="Your custom personality prompt"
# or
PERSONALITY_PROMPT_FILE="path/to/custom/personality.txt"
# or
PERSONALITY_PROMPT_URL="https://example.com/personality.txt"
```

### Database Configuration

The bot automatically creates the required database schema. For custom setups:

```python
# Custom database configuration
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
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
