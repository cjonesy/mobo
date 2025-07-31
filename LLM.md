# 🤖 Discord AI Bot Spec (LangGraph, Local Hosting)

## 📦 Tech Stack

| Component         | Technology                                                    |
| ----------------- | ------------------------------------------------------------- |
| Language          | Python                                                        |
| Bot Framework     | `discord.py`                                                  |
| LLM Orchestration | [LangGraph](https://docs.langgraph.dev)                       |
| LLM Provider      | OpenAI (but keep implementation open for future use)          |
| Embeddings        | OpenAI                                                        |
| Vector Store      | PostgreSQL + [pgvector](https://github.com/pgvector/pgvector) |
| Storage           | PostgreSQL (for history + profiles)                           |
| Hosting           | Local (e.g. Docker, bare metal)                               |

## 🧠 Features

### ✅ Message Triggering

- Only responds if:
  - Bot is @-mentioned directly
  - The message is a reply to one of the bot's messages

### ✅ Personality Injection

- A static `personality_prompt` is always injected as a system message
- Prevents personality drift over time or from chat history

### ✅ Chat History (RAG Memory)

- Long-term memory via PostgreSQL + pgvector
- Embed each message and store in `conversation_memory` table
- At runtime:
  - Embed incoming message
  - Query for top-K similar past messages
  - Inject those + recent N messages as context

### ✅ Nickname Self-Change

- Bot can **change its own nickname** without user request
- Determined internally by the agent logic

### ✅ Image Generation

- Bot can **generate an image on its own whim**
- Tool: `generate_image(prompt: str)`
- Powered by OpenAI DALL·E or local Stable Diffusion

### ✅ Anti-Bot Loop Protection

- Bot will only respond to other bots **N times**
- Configurable via `MAX_BOT_RESPONSES`

### ✅ User Profile Tracking

- `user_profiles` table stores:
  - likes / dislikes
  - tone toward the user (friendly, rude, neutral)
  - tags or traits
- Bot can update profile over time (e.g., user is nice → bot gets friendly)

### ✅ Tool: Active Chat Users

- Tool: `get_current_chat_users(channel_id)`
- Uses Discord API to get user list in channel
- Lets bot know who is present

### ✅ Tool: User @-Mentions

- Bot can resolve Discord user IDs to proper `@username` format
- Uses `<@user_id>` formatting to mention users programmatically

---

## 🗃️ PostgreSQL Schema

### `conversation_memory`

```sql
CREATE TABLE conversation_memory (
    id SERIAL PRIMARY KEY,
    user_id TEXT,
    channel_id TEXT,
    role TEXT, -- 'user' or 'assistant'
    content TEXT,
    embedding VECTOR(1536),
    timestamp TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_conversation_embedding ON conversation_memory USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

user_profiles

CREATE TABLE user_profiles (
    user_id TEXT PRIMARY KEY,
    likes TEXT[],
    dislikes TEXT[],
    tone TEXT, -- e.g., 'friendly', 'rude', 'neutral'
    custom_tags JSONB DEFAULT '{}'
);


⸻

🧠 LangGraph Agent Layout

graph = StateGraph()

graph.add_node("get_context", rag_context_lookup)
graph.add_node("llm", chat_with_tools)
graph.add_node("tool_dispatch", tool_executor)
graph.add_node("update_user_profile", profile_update_logic)

graph.set_entry_point("get_context")
graph.add_edge("get_context", "llm")
graph.add_conditional_edges(
    "llm",
    condition_func=tool_or_not,
    path_map={
        "tool_call": "tool_dispatch",
        "response_only": "update_user_profile"
    }
)
graph.add_edge("tool_dispatch", "update_user_profile")
graph.add_edge("update_user_profile", END)


⸻

📁 Suggested Project Structure

discord-chatbot/
├── bot/
│   ├── main.py                      # Discord entry point
│   ├── handlers/
│   │   ├── message_handler.py       # Trigger logic and routing
│   │   └── tool_dispatch.py         # Execute called tools
│   └── config.py                    # Tokens, personality, etc.
│
├── agent/
│   ├── agent_graph.py               # LangGraph state logic
│   ├── llm_client.py                # LLM abstraction layer
│   ├── memory.py                    # RAG + vector query code
│   ├── tools.py                     # Tool definitions and schemas
│   ├── user_profiles.py             # Load/update user profile logic
│   └── rag.py                       # Semantic memory query builder
│
├── data/
│   └── seed_personality.txt         # Personality prompt text
├── requirements.txt
├── .env
└── README.md


⸻

✅ Tasks Overview
	•	Create discord.py bot event loop
	•	Build LangGraph agent with:
	•	Tool calling
	•	User profile access
	•	Personality preservation
	•	Implement RAG: store + retrieve vector context
	•	Write tools:
	•	generate_image()
	•	change_nickname()
	•	get_current_chat_users()
	•	mention_user()
	•	Create PostgreSQL tables
	•	Add bot loop limiter
	•	Design and update user profiles over time

⸻

🛠️ Configuration Examples

MAX_BOT_RESPONSES = 3
PERSONALITY_PROMPT = open("data/seed_personality.txt").read()
EMBEDDING_MODEL = "text-embedding-ada-002"
TOP_K_MEMORY_RESULTS = 5
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")


⸻

🚀 Hosting
	•	Run locally via Python or Docker
	•	Optional: use supervisor or systemd to keep it running
	•	Store data in local PostgreSQL + pgvector instance
```
