# mobo

MOckBOt: A Discord/ChatGPT bot that can take on whatever personality you write.

## ⚙️ Installation

### Local Development

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd mobo
   ```

2. **Install dependencies**

   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -e .
   ```

3. **Set up environment variables**

   ```bash
   cp env.example .env
   # Edit .env with your keys
   ```

4. **Run the bot**

   ```bash
   # Using uv
   uv run python -m src.mobo

   # Or directly
   python -m src.mobo
   ```

### 🐳 Docker Deployment

1. **Build and run with Docker Compose**

   ```bash
   # Edit docker-compose.yml with your environment variables
   docker-compose up -d
   ```

2. **View logs**
   ```bash
   docker-compose logs -f bot
   ```
