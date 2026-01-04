# Voice-Controlled TV Platform: Implementation Plan
## With Render.com Cloud Deployment

---

## Updated Architecture (Cloud-Hosted)

```
┌──────────────────┐              ┌─────────────────────┐              ┌──────────────────┐
│     iPHONE       │   Internet   │    RENDER.COM       │   Internet   │    DELL 5070     │
│  Safari Web App  │ ──────────►  │    "Cloud Brain"    │ ──────────►  │  "TV Platform"   │
│                  │   Audio/WSS  │                     │     WSS      │                  │
│  • Push-to-talk  │              │  • Web Server       │              │  • Custom TV UI  │
│  • D-pad nav     │              │  • WebSocket Server │              │  • Chromium      │
│  • Status UI     │ ◄────────────│  • Claude API       │ ◄────────────│  • Streaming     │
│                  │   Response   │  • Whisper STT      │    State     │                  │
└──────────────────┘              └─────────────────────┘              └──────────────────┘
                                           │
                                           │ HTTPS
                                           ▼
                                  ┌─────────────────────┐
                                  │   External APIs     │
                                  │  • Anthropic        │
                                  │  • TMDB             │
                                  └─────────────────────┘
```

## Key Changes with Render.com

| Component | Before (Local) | After (Render) |
|-----------|----------------|----------------|
| **Server URL** | `ws://192.168.1.100:8765` | `wss://tv-brain.onrender.com` |
| **HTTPS** | Self-signed cert | Automatic SSL |
| **Access** | Home network only | Anywhere |
| **Whisper** | Local GPU/CPU | Cloud CPU (or offload to Groq) |
| **Cost** | Free (your hardware) | ~$7-25/month |

## Render.com Service Options

| Tier | RAM | CPU | Cost | Whisper Model |
|------|-----|-----|------|---------------|
| **Free** | 512MB | Shared | $0 | ❌ Too small |
| **Starter** | 512MB | Shared | $7/mo | ❌ Too small |
| **Standard** | 2GB | 1 CPU | $25/mo | ✅ `tiny.en` or `base.en` |
| **Pro** | 4GB | 2 CPU | $85/mo | ✅ `small.en` |

**Recommendation**: Start with **Standard ($25/mo)** using `base.en` model, or use **Groq API for Whisper** (free tier available) to stay on cheaper Render tier.

---

# PHASE 1: Render.com Project Setup (Day 1)

## 1.1: Project Structure for Render

```
tv-brain/
├── Dockerfile
├── render.yaml              # Render blueprint
├── requirements.txt
├── .env.example
├── src/
│   ├── __init__.py
│   ├── main.py              # Main server
│   ├── config.py            # Configuration
│   ├── services/
│   │   ├── __init__.py
│   │   ├── whisper_service.py
│   │   ├── claude_service.py
│   │   └── groq_whisper.py  # Alternative: Groq for STT
│   └── handlers/
│       ├── __init__.py
│       ├── phone_handler.py
│       └── tv_handler.py
└── web/
    └── index.html           # Phone UI (served by same app)
```

## 1.2: Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system dependencies for faster-whisper
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Whisper model at build time (faster cold starts)
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8')"

# Copy application
COPY src/ ./src/
COPY web/ ./web/

# Expose port
EXPOSE 10000

# Run server
CMD ["python", "-m", "src.main"]
```

## 1.3: requirements.txt

```
# Core
anthropic>=0.40.0
websockets>=12.0
aiohttp>=3.9.0

# Speech-to-Text (choose one)
faster-whisper>=1.0.0
# groq>=0.4.0  # Alternative: Groq API for Whisper

# Utilities
python-dotenv>=1.0.0
httpx>=0.26.0
pydantic>=2.5.0
```

## 1.4: render.yaml (Infrastructure as Code)

```yaml
services:
  # Main WebSocket + Web Server
  - type: web
    name: tv-brain
    runtime: docker
    plan: standard  # $25/mo, 2GB RAM - needed for Whisper
    
    # Health check
    healthCheckPath: /health
    
    # Environment variables (set in Render dashboard)
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false  # Set manually in dashboard
      - key: WHISPER_MODEL
        value: base.en
      - key: WHISPER_DEVICE
        value: cpu
      - key: PORT
        value: 10000
      - key: ENVIRONMENT
        value: production
    
    # Auto-deploy from GitHub
    autoDeploy: true
```

## 1.5: Configuration Module

Create `src/config.py`:

```python
import os
from dataclasses import dataclass

@dataclass
class Config:
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", 10000))  # Render uses PORT env var
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Whisper
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base.en")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")
    USE_GROQ_WHISPER: bool = os.getenv("USE_GROQ_WHISPER", "false").lower() == "true"
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    # Claude
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    
    # Content
    TMDB_API_KEY: str = os.getenv("TMDB_API_KEY", "")
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

config = Config()
```

## 1.6: Main Server (Updated for Render)

Create `src/main.py`:

```python
#!/usr/bin/env python3
"""
TV Brain Server - Cloud version for Render.com
Serves both WebSocket API and static web files
"""

import asyncio
import json
import logging
import os
import io
from pathlib import Path
from typing import Optional, Set
from datetime import datetime

from aiohttp import web
import aiohttp
import websockets
from websockets.server import WebSocketServerProtocol

from .config import config

# Conditional import based on Whisper backend
if config.USE_GROQ_WHISPER:
    from .services.groq_whisper import transcribe
else:
    from .services.whisper_service import WhisperService
    whisper_service = None

import anthropic

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("tv-brain")

# ============ Claude Tools ============
TV_TOOLS = [
    {
        "name": "navigate",
        "description": "Navigate TV interface. Use for up/down/left/right/select/back/home commands.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "left", "right", "select", "back", "home"]
                },
                "repeat": {"type": "integer", "default": 1}
            },
            "required": ["direction"]
        }
    },
    {
        "name": "playback",
        "description": "Control playback (play/pause/stop/skip).",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["play", "pause", "stop", "skip_forward", "skip_backward", "rewind", "fast_forward"]
                },
                "seconds": {"type": "integer"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "volume",
        "description": "Control volume.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["up", "down", "mute", "unmute", "set"]},
                "level": {"type": "integer", "minimum": 0, "maximum": 100},
                "steps": {"type": "integer", "default": 1}
            },
            "required": ["action"]
        }
    },
    {
        "name": "launch_app",
        "description": "Open a streaming app.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app": {"type": "string"}
            },
            "required": ["app"]
        }
    },
    {
        "name": "play_content",
        "description": "Play specific content by title.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "service": {"type": "string"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "search",
        "description": "Search for content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "type": {"type": "string", "enum": ["movie", "series", "any"]},
                "service": {"type": "string"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "type_text",
        "description": "Type text into current input field.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "power",
        "description": "Control TV power.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["on", "off", "toggle"]}
            },
            "required": ["action"]
        }
    }
]


class TVBrain:
    def __init__(self):
        self.claude: Optional[anthropic.Anthropic] = None
        self.phone_clients: Set[WebSocketServerProtocol] = set()
        self.tv_client: Optional[WebSocketServerProtocol] = None
        
        self.tv_state = {
            "power": "unknown",
            "app": None,
            "screen": "home",
            "volume": 50,
            "now_playing": None
        }
        
        self.conversation_history = []
    
    async def initialize(self):
        """Initialize services"""
        global whisper_service
        
        logger.info("Initializing TV Brain...")
        
        # Initialize Whisper (if not using Groq)
        if not config.USE_GROQ_WHISPER:
            logger.info(f"Loading Whisper model: {config.WHISPER_MODEL}")
            whisper_service = WhisperService()
            await whisper_service.initialize()
            logger.info("✓ Whisper loaded")
        else:
            logger.info("✓ Using Groq API for transcription")
        
        # Initialize Claude
        self.claude = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        logger.info("✓ Claude client ready")
        
        logger.info("TV Brain initialized")
    
    def get_system_prompt(self) -> str:
        return f"""You are a TV voice assistant. Parse voice commands and control the TV.

CURRENT STATE:
- Power: {self.tv_state.get('power', 'unknown')}
- App: {self.tv_state.get('app', 'Home')}
- Volume: {self.tv_state.get('volume', '?')}
- Playing: {self.tv_state.get('now_playing', 'Nothing')}

INSTRUCTIONS:
1. Use tools to execute commands
2. Keep responses SHORT (spoken aloud)
3. Make assumptions rather than asking questions

EXAMPLES:
- "Pause" → respond "Paused"
- "Open Netflix" → respond "Opening Netflix"
- "Turn it up" → respond "Volume up"
"""

    async def transcribe(self, audio_bytes: bytes) -> dict:
        """Transcribe audio to text"""
        try:
            if config.USE_GROQ_WHISPER:
                from .services.groq_whisper import transcribe as groq_transcribe
                text = await groq_transcribe(audio_bytes)
                return {"text": text}
            else:
                return await whisper_service.transcribe(audio_bytes)
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {"text": "", "error": str(e)}

    async def process_with_claude(self, text: str) -> dict:
        """Process through Claude"""
        if not text.strip():
            return {"response": "I didn't catch that", "commands": []}
        
        self.conversation_history.append({"role": "user", "content": text})
        
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        
        try:
            response = self.claude.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=512,
                system=self.get_system_prompt(),
                tools=TV_TOOLS,
                messages=self.conversation_history
            )
            
            tool_calls = []
            text_response = ""
            
            for block in response.content:
                if block.type == "tool_use":
                    tool_calls.append({"tool": block.name, "input": block.input})
                    logger.info(f"Tool: {block.name} → {block.input}")
                elif block.type == "text":
                    text_response = block.text
            
            self.conversation_history.append({"role": "assistant", "content": response.content})
            
            commands = [{"type": tc["tool"], **tc["input"]} for tc in tool_calls]
            
            return {"response": text_response or "Done", "commands": commands}
            
        except Exception as e:
            logger.error(f"Claude error: {e}")
            return {"response": "Sorry, error processing that", "commands": [], "error": str(e)}

    async def send_to_tv(self, commands: list):
        """Send commands to TV"""
        if not self.tv_client:
            logger.warning("TV not connected")
            return False
        
        try:
            for cmd in commands:
                await self.tv_client.send(json.dumps({
                    "type": "command",
                    "timestamp": datetime.now().isoformat(),
                    **cmd
                }))
            return True
        except Exception as e:
            logger.error(f"Error sending to TV: {e}")
            return False

    async def broadcast_to_phones(self, message: dict):
        """Send to all phones"""
        if not self.phone_clients:
            return
        
        data = json.dumps(message)
        await asyncio.gather(
            *[client.send(data) for client in self.phone_clients],
            return_exceptions=True
        )

    async def process_voice(self, audio_bytes: bytes) -> dict:
        """Full voice pipeline"""
        # Transcribe
        result = await self.transcribe(audio_bytes)
        text = result.get("text", "")
        
        if result.get("error"):
            return {"type": "error", "error": result["error"]}
        
        # Process with Claude
        claude_result = await self.process_with_claude(text)
        
        # Send to TV
        if claude_result["commands"]:
            await self.send_to_tv(claude_result["commands"])
        
        return {
            "type": "response",
            "transcription": text,
            "response": claude_result["response"],
            "commands": claude_result["commands"]
        }

    # WebSocket handlers
    async def handle_phone(self, websocket: WebSocketServerProtocol):
        self.phone_clients.add(websocket)
        logger.info(f"📱 Phone connected ({len(self.phone_clients)} total)")
        
        await websocket.send(json.dumps({
            "type": "state",
            "tv_connected": self.tv_client is not None,
            "tv_state": self.tv_state
        }))
        
        audio_pending = False
        
        try:
            async for message in websocket:
                if isinstance(message, str):
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    if msg_type == "audio":
                        audio_pending = True
                    elif msg_type == "navigate":
                        await self.send_to_tv([{"type": "navigate", "direction": data["direction"]}])
                    elif msg_type == "playback":
                        await self.send_to_tv([{"type": "playback", "action": data["action"]}])
                else:
                    if audio_pending:
                        audio_pending = False
                        logger.info(f"📱 Audio: {len(message)} bytes")
                        result = await self.process_voice(message)
                        await websocket.send(json.dumps(result))
                        
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.phone_clients.discard(websocket)
            logger.info(f"📱 Phone disconnected ({len(self.phone_clients)} remaining)")

    async def handle_tv(self, websocket: WebSocketServerProtocol):
        self.tv_client = websocket
        logger.info("📺 TV connected")
        
        await self.broadcast_to_phones({"type": "tv_status", "connected": True})
        
        try:
            async for message in websocket:
                data = json.loads(message)
                if data.get("type") == "state":
                    self.tv_state.update(data.get("state", {}))
                    await self.broadcast_to_phones({"type": "tv_state", "state": self.tv_state})
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.tv_client = None
            logger.info("📺 TV disconnected")
            await self.broadcast_to_phones({"type": "tv_status", "connected": False})


# Global brain instance
brain = TVBrain()


# ============ HTTP Routes (aiohttp) ============

async def health_handler(request):
    """Health check endpoint for Render"""
    return web.json_response({
        "status": "healthy",
        "phones_connected": len(brain.phone_clients),
        "tv_connected": brain.tv_client is not None
    })


async def index_handler(request):
    """Serve the phone web interface"""
    return web.FileResponse(Path(__file__).parent.parent / "web" / "index.html")


async def websocket_handler(request):
    """Handle WebSocket upgrade"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    path = request.path
    
    # Convert aiohttp WebSocket to work with our handlers
    # This is a simplified adapter
    if path in ("/ws/voice", "/ws"):
        await handle_phone_aiohttp(ws)
    elif path == "/ws/tv":
        await handle_tv_aiohttp(ws)
    
    return ws


async def handle_phone_aiohttp(ws: web.WebSocketResponse):
    """Phone handler for aiohttp WebSocket"""
    brain.phone_clients.add(ws)
    logger.info(f"📱 Phone connected ({len(brain.phone_clients)} total)")
    
    await ws.send_json({
        "type": "state",
        "tv_connected": brain.tv_client is not None,
        "tv_state": brain.tv_state
    })
    
    audio_pending = False
    
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                msg_type = data.get("type")
                
                if msg_type == "audio":
                    audio_pending = True
                elif msg_type == "navigate":
                    await brain.send_to_tv([{"type": "navigate", "direction": data["direction"]}])
                elif msg_type == "playback":
                    await brain.send_to_tv([{"type": "playback", "action": data["action"]}])
                    
            elif msg.type == aiohttp.WSMsgType.BINARY:
                if audio_pending:
                    audio_pending = False
                    logger.info(f"📱 Audio: {len(msg.data)} bytes")
                    result = await brain.process_voice(msg.data)
                    await ws.send_json(result)
                    
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")
                break
    finally:
        brain.phone_clients.discard(ws)
        logger.info(f"📱 Phone disconnected ({len(brain.phone_clients)} remaining)")


async def handle_tv_aiohttp(ws: web.WebSocketResponse):
    """TV handler for aiohttp WebSocket"""
    brain.tv_client = ws
    logger.info("📺 TV connected")
    
    # Notify phones
    for phone in brain.phone_clients:
        try:
            await phone.send_json({"type": "tv_status", "connected": True})
        except:
            pass
    
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("type") == "state":
                    brain.tv_state.update(data.get("state", {}))
                    for phone in brain.phone_clients:
                        try:
                            await phone.send_json({"type": "tv_state", "state": brain.tv_state})
                        except:
                            pass
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break
    finally:
        brain.tv_client = None
        logger.info("📺 TV disconnected")
        for phone in brain.phone_clients:
            try:
                await phone.send_json({"type": "tv_status", "connected": False})
            except:
                pass


async def init_app():
    """Initialize the application"""
    await brain.initialize()
    
    app = web.Application()
    
    # Routes
    app.router.add_get("/health", health_handler)
    app.router.add_get("/", index_handler)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_get("/ws/voice", websocket_handler)
    app.router.add_get("/ws/tv", websocket_handler)
    
    # Static files (for any additional assets)
    app.router.add_static("/static/", Path(__file__).parent.parent / "web")
    
    return app


def main():
    """Entry point"""
    app = asyncio.get_event_loop().run_until_complete(init_app())
    
    logger.info("=" * 50)
    logger.info(f"🧠 TV Brain starting on port {config.PORT}")
    logger.info("=" * 50)
    logger.info("Endpoints:")
    logger.info(f"  🌐 Web UI:    https://your-app.onrender.com/")
    logger.info(f"  📱 Phone WS:  wss://your-app.onrender.com/ws/voice")
    logger.info(f"  📺 TV WS:     wss://your-app.onrender.com/ws/tv")
    logger.info(f"  ❤️  Health:   https://your-app.onrender.com/health")
    logger.info("=" * 50)
    
    web.run_app(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()
```

## 1.7: Whisper Service

Create `src/services/whisper_service.py`:

```python
"""Local Whisper STT service"""

import io
import logging
from faster_whisper import WhisperModel
from ..config import config

logger = logging.getLogger(__name__)


class WhisperService:
    def __init__(self):
        self.model = None
    
    async def initialize(self):
        logger.info(f"Loading Whisper: {config.WHISPER_MODEL}")
        self.model = WhisperModel(
            config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type="int8"
        )
    
    async def transcribe(self, audio_bytes: bytes) -> dict:
        if not self.model:
            raise RuntimeError("Whisper not initialized")
        
        segments, info = self.model.transcribe(
            io.BytesIO(audio_bytes),
            language="en",
            beam_size=5,
            vad_filter=True
        )
        
        text = " ".join([seg.text.strip() for seg in segments])
        logger.info(f"Transcribed: '{text}'")
        
        return {"text": text, "duration": info.duration}
```

## 1.8: Groq Whisper Alternative (Cheaper Option)

Create `src/services/groq_whisper.py`:

```python
"""
Groq API for Whisper transcription
Much faster and cheaper than running Whisper locally on Render
Free tier: 14,400 requests/day
"""

import httpx
import logging
from ..config import config

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


async def transcribe(audio_bytes: bytes) -> str:
    """Transcribe audio using Groq's Whisper API"""
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {config.GROQ_API_KEY}"
            },
            files={
                "file": ("audio.wav", audio_bytes, "audio/wav")
            },
            data={
                "model": "whisper-large-v3",
                "response_format": "text",
                "language": "en"
            },
            timeout=30.0
        )
        
        if response.status_code != 200:
            logger.error(f"Groq error: {response.status_code} - {response.text}")
            raise Exception(f"Groq API error: {response.status_code}")
        
        text = response.text.strip()
        logger.info(f"Transcribed (Groq): '{text}'")
        
        return text
```

**Groq Benefits:**
- Free tier: 14,400 audio requests/day
- Uses `whisper-large-v3` (best quality)
- ~0.5s latency (faster than local on cheap instances)
- Lets you use Render's cheaper Starter tier ($7/mo)

---

# PHASE 2: Deploy to Render (Day 1-2)

## 2.1: Create GitHub Repository

```bash
cd tv-brain

# Initialize git
git init
git add .
git commit -m "Initial commit"

# Create repo on GitHub and push
gh repo create tv-brain --private --source=. --push
# Or manually: git remote add origin ... && git push
```

## 2.2: Create Render Account & Connect GitHub

1. Go to [render.com](https://render.com) and sign up
2. Connect your GitHub account
3. Click "New +" → "Web Service"
4. Select your `tv-brain` repository

## 2.3: Configure Render Service

**In Render Dashboard:**

| Setting | Value |
|---------|-------|
| Name | `tv-brain` |
| Region | Oregon (closest to you) |
| Branch | `main` |
| Root Directory | (leave empty) |
| Runtime | Docker |
| Instance Type | Standard ($25/mo) or Starter ($7/mo with Groq) |

**Environment Variables** (add in dashboard):

| Key | Value |
|-----|-------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `GROQ_API_KEY` | `gsk_...` (if using Groq) |
| `USE_GROQ_WHISPER` | `true` (if using Groq) |
| `WHISPER_MODEL` | `base.en` (if local) |
| `TMDB_API_KEY` | `your_tmdb_key` (optional) |

## 2.4: Deploy

Click "Create Web Service" — Render will:
1. Clone your repo
2. Build the Docker image
3. Deploy and start the service
4. Provide a URL like `https://tv-brain.onrender.com`

## 2.5: Verify Deployment

```bash
# Health check
curl https://tv-brain.onrender.com/health

# Should return:
# {"status": "healthy", "phones_connected": 0, "tv_connected": false}
```

---

# PHASE 3: Update Phone Interface for Render (Day 2)

## 3.1: Updated index.html with Render URL

The phone interface (`web/index.html`) is served directly from Render. Update the default server URL:

```javascript
// In the CONFIG section, update default URL
const CONFIG = {
    serverUrl: localStorage.getItem('tv_server_url') || 
               'wss://tv-brain.onrender.com/ws/voice',  // Your Render URL
    sampleRate: 16000
};
```

## 3.2: Access the Phone Remote

1. On your iPhone, open Safari
2. Go to: `https://tv-brain.onrender.com/`
3. The web interface loads with HTTPS (no certificate warnings!)
4. Microphone access works automatically (HTTPS = trusted)
5. Add to Home Screen for app-like experience

---

# PHASE 4: Dell 5070 Setup (Day 3-4)

## 4.1: OS Installation (Same as Before)

```bash
# Install Ubuntu Server 24.04 LTS minimal
# SSH: tv@192.168.1.101
```

## 4.2: System Setup

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    git curl nodejs npm \
    chromium-browser chromium-codecs-ffmpeg-extra \
    intel-media-va-driver-non-free \
    pulseaudio cage
```

## 4.3: TV UI with Render WebSocket

Create `~/tv-ui/.env`:

```bash
# Point to Render instead of local ThinkStation
VITE_BRAIN_URL=wss://tv-brain.onrender.com/ws/tv
```

## 4.4: Build and Deploy UI

```bash
cd ~/tv-ui
npm install
npm run build
```

## 4.5: Start Script

```bash
cat > ~/start-tv.sh << 'EOF'
#!/bin/bash
pulseaudio --start
cage -- chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --enable-features=VaapiVideoDecoder \
    --user-data-dir=/home/tv/.config/chromium-tv \
    file:///home/tv/tv-ui/dist/index.html
EOF
chmod +x ~/start-tv.sh
```

---

# PHASE 5: Testing & Monitoring (Day 4-5)

## 5.1: Render Logs

```bash
# View logs in Render dashboard
# Or use Render CLI:
render logs tv-brain --tail
```

## 5.2: Test Checklist

```markdown
### Cloud Connection Tests
- [ ] Phone connects to Render WebSocket
- [ ] Dell 5070 connects to Render WebSocket
- [ ] Health endpoint returns 200
- [ ] Connections survive Render sleep/wake

### Latency Tests
- [ ] Voice command roundtrip < 3 seconds
- [ ] D-pad commands < 500ms
- [ ] Reconnection after network drop

### Voice Tests
- [ ] "Open Netflix" works
- [ ] "Pause" works
- [ ] Complex commands work
```

## 5.3: Render Cold Start Handling

Render's free/starter tiers spin down after inactivity. Handle this in the phone UI:

```javascript
// Add reconnection with exponential backoff
let reconnectDelay = 1000;
const maxDelay = 30000;

ws.onclose = () => {
    statusText.textContent = 'Reconnecting...';
    setTimeout(() => {
        connect();
        reconnectDelay = Math.min(reconnectDelay * 2, maxDelay);
    }, reconnectDelay);
};

ws.onopen = () => {
    reconnectDelay = 1000; // Reset on successful connection
};
```

---

# Cost Summary

## Option A: Local Whisper on Render

| Service | Tier | Cost/Month |
|---------|------|------------|
| Render Web Service | Standard (2GB RAM) | $25 |
| Anthropic Claude | Pay-as-you-go | ~$5-10 |
| **Total** | | **~$30-35/mo** |

## Option B: Groq Whisper (Recommended)

| Service | Tier | Cost/Month |
|---------|------|------------|
| Render Web Service | Starter (512MB) | $7 |
| Groq API | Free tier | $0 |
| Anthropic Claude | Pay-as-you-go | ~$5-10 |
| **Total** | | **~$12-17/mo** |

---

# Quick Reference

## URLs (After Deployment)

```
Web Interface:  https://tv-brain.onrender.com/
Phone WebSocket: wss://tv-brain.onrender.com/ws/voice
TV WebSocket:    wss://tv-brain.onrender.com/ws/tv
Health Check:    https://tv-brain.onrender.com/health
```

## Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...        # If using Groq
USE_GROQ_WHISPER=true       # If using Groq
WHISPER_MODEL=base.en       # If using local Whisper
TMDB_API_KEY=...            # Optional
```

## Local Development

```bash
cd tv-brain
source venv/bin/activate
python -m src.main
# Runs on http://localhost:10000
```

## Deploy Updates

```bash
git add .
git commit -m "Update"
git push origin main
# Render auto-deploys from main branch
```

---

# Migration Path

## Start → Scale

1. **Week 1**: Deploy to Render Starter + Groq ($7/mo)
2. **Month 1**: If latency issues, upgrade to Standard ($25/mo)
3. **Month 3**: If scaling needed, consider Railway or Fly.io
4. **Future**: Self-host on your own server for $0 cloud cost

The architecture is designed so you can move between hosting options easily — the code is the same, just change the URLs.
