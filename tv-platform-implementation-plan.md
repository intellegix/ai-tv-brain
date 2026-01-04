# Voice-Controlled TV Platform: Implementation Plan

## Architecture Overview

```
┌──────────────────┐              ┌─────────────────────┐              ┌──────────────────┐
│     iPHONE       │    WiFi      │    THINKSTATION     │    WiFi      │    DELL 5070     │
│  Safari Web App  │ ──────────►  │      "Brain"        │ ──────────►  │  "TV Platform"   │
│                  │   Audio      │                     │   Commands   │                  │
│  • Push-to-talk  │   WebSocket  │  • Whisper STT      │   WebSocket  │  • Custom TV UI  │
│  • D-pad nav     │              │  • Claude API       │              │  • Chromium      │
│  • Status UI     │ ◄────────────│  • Orchestrator     │ ◄────────────│  • CEC control   │
│                  │   Response   │  • State manager    │    State     │  • Streaming     │
└──────────────────┘              └─────────────────────┘              └──────────────────┘
                                           │
                                           │ REST API (optional)
                                           ▼
                                  ┌─────────────────────┐
                                  │   Content APIs      │
                                  │  • TMDB             │
                                  │  • Watchmode        │
                                  └─────────────────────┘
```

## Communication Flow

```
1. User holds button, speaks "Play Stranger Things on Netflix"
2. iPhone records audio, sends via WebSocket to ThinkStation
3. ThinkStation:
   a. Whisper transcribes → "Play Stranger Things on Netflix"
   b. Claude processes → {action: "play_content", title: "Stranger Things", service: "netflix"}
   c. Sends command to Dell 5070
4. Dell 5070:
   a. Launches Netflix
   b. Deep-links to Stranger Things
   c. Reports state back to ThinkStation
5. ThinkStation sends response to iPhone
6. iPhone speaks "Playing Stranger Things on Netflix"
```

---

# PHASE 1: ThinkStation Server (Day 1-2)

## Goal: Get the brain running and accepting voice input

### Step 1.1: Create Project Structure

```bash
# On ThinkStation
mkdir -p ~/tv-brain
cd ~/tv-brain

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Create directory structure
mkdir -p src/{services,tools,routes}
touch src/__init__.py
touch src/services/__init__.py
touch src/tools/__init__.py
```

### Step 1.2: Install Dependencies

```bash
# requirements.txt
cat > requirements.txt << 'EOF'
# Core
anthropic>=0.40.0
websockets>=12.0
fastapi>=0.109.0
uvicorn>=0.27.0

# Speech
faster-whisper>=1.0.0

# Utilities
python-dotenv>=1.0.0
httpx>=0.26.0
pydantic>=2.5.0

# Optional: Database
sqlalchemy>=2.0.0
aiosqlite>=0.19.0
EOF

pip install -r requirements.txt
```

### Step 1.3: Environment Configuration

```bash
# .env
cat > .env << 'EOF'
# API Keys
ANTHROPIC_API_KEY=your_anthropic_key_here
TMDB_API_KEY=your_tmdb_key_here

# Whisper Config
WHISPER_MODEL=base.en
WHISPER_DEVICE=cpu

# Network
SERVER_HOST=0.0.0.0
SERVER_PORT=8765
TV_PLATFORM_URL=ws://192.168.1.101:9000

# Claude
CLAUDE_MODEL=claude-sonnet-4-20250514
EOF
```

### Step 1.4: Main Server Implementation

Create `src/main.py`:

```python
#!/usr/bin/env python3
"""
TV Brain Server
Handles voice from phone, processes with Whisper + Claude, controls TV
"""

import asyncio
import json
import logging
import os
import io
from pathlib import Path
from typing import Optional, Set
from datetime import datetime

import websockets
from websockets.server import WebSocketServerProtocol
from faster_whisper import WhisperModel
import anthropic
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("tv-brain")

# ============ Configuration ============
class Config:
    # Server
    HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    PORT = int(os.getenv("SERVER_PORT", 8765))
    
    # Whisper
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base.en")
    WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
    
    # Claude
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    
    # TV Platform
    TV_URL = os.getenv("TV_PLATFORM_URL", "ws://192.168.1.101:9000")


# ============ Claude Tools Definition ============
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
                "repeat": {"type": "integer", "default": 1, "description": "Times to repeat"}
            },
            "required": ["direction"]
        }
    },
    {
        "name": "playback",
        "description": "Control playback. Use for play/pause/stop/skip/rewind.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["play", "pause", "stop", "skip_forward", "skip_backward", "rewind", "fast_forward"]
                },
                "seconds": {"type": "integer", "description": "Seconds to skip"}
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
                "app": {
                    "type": "string",
                    "description": "App name: netflix, hulu, disney, prime, youtube, hbo, paramount, peacock, spotify"
                }
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
                "title": {"type": "string", "description": "Movie or show title"},
                "type": {"type": "string", "enum": ["movie", "series", "episode"]},
                "service": {"type": "string", "description": "Preferred streaming service"},
                "season": {"type": "integer"},
                "episode": {"type": "integer"}
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


# ============ TV Brain Server ============
class TVBrain:
    def __init__(self):
        self.whisper: Optional[WhisperModel] = None
        self.claude: Optional[anthropic.Anthropic] = None
        
        # Connected clients
        self.phone_clients: Set[WebSocketServerProtocol] = set()
        self.tv_client: Optional[WebSocketServerProtocol] = None
        
        # State
        self.tv_state = {
            "power": "unknown",
            "app": None,
            "screen": "home",
            "volume": 50,
            "now_playing": None
        }
        
        # Conversation context (for follow-up commands)
        self.conversation_history = []
    
    async def initialize(self):
        """Load models and initialize clients"""
        logger.info("Initializing TV Brain...")
        
        # Load Whisper
        logger.info(f"Loading Whisper model: {Config.WHISPER_MODEL}")
        self.whisper = WhisperModel(
            Config.WHISPER_MODEL,
            device=Config.WHISPER_DEVICE,
            compute_type="int8" if Config.WHISPER_DEVICE == "cpu" else "float16"
        )
        logger.info("✓ Whisper loaded")
        
        # Initialize Claude
        self.claude = anthropic.Anthropic()
        logger.info("✓ Claude client ready")
        
        logger.info("TV Brain initialized successfully")
    
    def get_system_prompt(self) -> str:
        """Generate system prompt with current TV state"""
        return f"""You are a TV voice assistant. Your job is to understand natural language commands and control the TV.

CURRENT TV STATE:
- Power: {self.tv_state.get('power', 'unknown')}
- App: {self.tv_state.get('app', 'Home')}
- Screen: {self.tv_state.get('screen', 'unknown')}
- Volume: {self.tv_state.get('volume', '?')}
- Now Playing: {self.tv_state.get('now_playing', 'Nothing')}

INSTRUCTIONS:
1. Parse the user's voice command and use appropriate tools
2. Keep responses SHORT - they will be spoken aloud
3. For simple commands (pause, volume up), respond with 1-2 words
4. Make reasonable assumptions rather than asking questions
5. If user says "that" or "it", check conversation history for context

RESPONSE STYLE:
- "Pause" → respond "Paused" 
- "Open Netflix" → respond "Opening Netflix"
- "Play Stranger Things" → respond "Playing Stranger Things on Netflix"
- "Turn it up" → respond "Volume up"

Be concise. Be helpful. Execute commands."""

    async def transcribe(self, audio_bytes: bytes) -> dict:
        """Transcribe audio to text"""
        try:
            segments, info = self.whisper.transcribe(
                io.BytesIO(audio_bytes),
                language="en",
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            text = " ".join([seg.text.strip() for seg in segments])
            
            logger.info(f"Transcribed: '{text}' (duration: {info.duration:.1f}s)")
            
            return {
                "text": text,
                "duration": info.duration,
                "language": info.language
            }
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {"text": "", "error": str(e)}

    async def process_with_claude(self, text: str) -> dict:
        """Process transcribed text through Claude"""
        if not text.strip():
            return {
                "response": "I didn't catch that",
                "commands": []
            }
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": text
        })
        
        # Keep last 10 exchanges for context
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        
        try:
            response = self.claude.messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=512,
                system=self.get_system_prompt(),
                tools=TV_TOOLS,
                messages=self.conversation_history
            )
            
            # Extract tool calls and text response
            tool_calls = []
            text_response = ""
            
            for block in response.content:
                if block.type == "tool_use":
                    tool_calls.append({
                        "tool": block.name,
                        "input": block.input
                    })
                    logger.info(f"Tool call: {block.name} → {block.input}")
                elif block.type == "text":
                    text_response = block.text
            
            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant", 
                "content": response.content
            })
            
            # Convert tool calls to commands
            commands = []
            for tc in tool_calls:
                commands.append({
                    "type": tc["tool"],
                    **tc["input"]
                })
            
            return {
                "response": text_response or "Done",
                "commands": commands
            }
            
        except Exception as e:
            logger.error(f"Claude error: {e}")
            return {
                "response": "Sorry, I had trouble processing that",
                "commands": [],
                "error": str(e)
            }

    async def send_to_tv(self, commands: list):
        """Send commands to TV platform"""
        if not self.tv_client:
            logger.warning("TV not connected")
            return False
        
        try:
            for cmd in commands:
                message = json.dumps({
                    "type": "command",
                    "timestamp": datetime.now().isoformat(),
                    **cmd
                })
                await self.tv_client.send(message)
                logger.info(f"Sent to TV: {cmd['type']}")
            return True
        except Exception as e:
            logger.error(f"Error sending to TV: {e}")
            return False

    async def broadcast_to_phones(self, message: dict):
        """Send message to all connected phone clients"""
        if not self.phone_clients:
            return
        
        data = json.dumps(message)
        await asyncio.gather(
            *[client.send(data) for client in self.phone_clients],
            return_exceptions=True
        )

    # ============ WebSocket Handlers ============
    
    async def handle_phone(self, websocket: WebSocketServerProtocol):
        """Handle phone voice remote connection"""
        self.phone_clients.add(websocket)
        client_id = id(websocket)
        logger.info(f"📱 Phone connected: {client_id}")
        
        # Send current state
        await websocket.send(json.dumps({
            "type": "state",
            "tv_connected": self.tv_client is not None,
            "tv_state": self.tv_state
        }))
        
        audio_pending = False
        
        try:
            async for message in websocket:
                if isinstance(message, str):
                    # JSON message
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    if msg_type == "audio":
                        # Next message will be audio bytes
                        audio_pending = True
                        logger.info("📱 Audio incoming...")
                        
                    elif msg_type == "navigate":
                        # Direct D-pad navigation
                        cmd = [{"type": "navigate", "direction": data["direction"]}]
                        await self.send_to_tv(cmd)
                        
                    elif msg_type == "playback":
                        cmd = [{"type": "playback", "action": data["action"]}]
                        await self.send_to_tv(cmd)
                        
                    elif msg_type == "quick_command":
                        # Pre-defined quick commands
                        cmd = [data["command"]]
                        await self.send_to_tv(cmd)
                
                else:
                    # Binary message - audio data
                    if audio_pending:
                        audio_pending = False
                        logger.info(f"📱 Received {len(message)} bytes audio")
                        
                        # Process audio
                        result = await self.process_voice(message)
                        
                        # Send response back to phone
                        await websocket.send(json.dumps(result))
                        
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Phone handler error: {e}")
        finally:
            self.phone_clients.discard(websocket)
            logger.info(f"📱 Phone disconnected: {client_id}")

    async def handle_tv(self, websocket: WebSocketServerProtocol):
        """Handle TV platform connection"""
        self.tv_client = websocket
        logger.info("📺 TV platform connected")
        
        # Notify phones
        await self.broadcast_to_phones({
            "type": "tv_status",
            "connected": True
        })
        
        try:
            async for message in websocket:
                data = json.loads(message)
                
                if data.get("type") == "state":
                    # TV reporting its state
                    self.tv_state.update(data.get("state", {}))
                    logger.debug(f"TV state: {self.tv_state}")
                    
                    # Forward to phones
                    await self.broadcast_to_phones({
                        "type": "tv_state",
                        "state": self.tv_state
                    })
                    
                elif data.get("type") == "event":
                    # TV event (e.g., user pressed button on physical remote)
                    logger.info(f"TV event: {data}")
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"TV handler error: {e}")
        finally:
            self.tv_client = None
            logger.info("📺 TV platform disconnected")
            
            await self.broadcast_to_phones({
                "type": "tv_status", 
                "connected": False
            })

    async def process_voice(self, audio_bytes: bytes) -> dict:
        """Full voice processing pipeline"""
        # 1. Transcribe
        transcription = await self.transcribe(audio_bytes)
        text = transcription.get("text", "")
        
        if transcription.get("error"):
            return {
                "type": "error",
                "error": transcription["error"],
                "transcription": ""
            }
        
        # 2. Process with Claude
        result = await self.process_with_claude(text)
        
        # 3. Send commands to TV
        if result["commands"]:
            await self.send_to_tv(result["commands"])
        
        # 4. Return response
        return {
            "type": "response",
            "transcription": text,
            "response": result["response"],
            "commands": result["commands"]
        }

    async def router(self, websocket: WebSocketServerProtocol, path: str):
        """Route incoming WebSocket connections"""
        logger.info(f"Connection: {path} from {websocket.remote_address}")
        
        if path in ("/voice", "/phone", "/"):
            await self.handle_phone(websocket)
        elif path == "/tv":
            await self.handle_tv(websocket)
        else:
            logger.warning(f"Unknown path: {path}")
            await websocket.close(1003, "Unknown endpoint")

    async def run(self):
        """Start the server"""
        await self.initialize()
        
        logger.info(f"Starting server on {Config.HOST}:{Config.PORT}")
        
        async with websockets.serve(
            self.router,
            Config.HOST,
            Config.PORT,
            ping_interval=30,
            ping_timeout=10,
            max_size=10 * 1024 * 1024  # 10MB max message (for audio)
        ):
            logger.info("=" * 50)
            logger.info(f"🧠 TV Brain running at ws://{Config.HOST}:{Config.PORT}")
            logger.info("=" * 50)
            logger.info("Endpoints:")
            logger.info(f"  📱 Phone: ws://YOUR_IP:{Config.PORT}/voice")
            logger.info(f"  📺 TV:    ws://YOUR_IP:{Config.PORT}/tv")
            logger.info("=" * 50)
            
            # Run forever
            await asyncio.Future()


# ============ Entry Point ============
async def main():
    brain = TVBrain()
    await brain.run()


if __name__ == "__main__":
    asyncio.run(main())
```

### Step 1.5: Test the Server

```bash
# Start server
source venv/bin/activate
python src/main.py

# You should see:
# ==================================================
# 🧠 TV Brain running at ws://0.0.0.0:8765
# ==================================================
# Endpoints:
#   📱 Phone: ws://YOUR_IP:8765/voice
#   📺 TV:    ws://YOUR_IP:8765/tv
# ==================================================
```

### Step 1.6: Quick WebSocket Test

```python
# test_client.py - run in another terminal
import asyncio
import websockets
import json

async def test():
    async with websockets.connect("ws://localhost:8765/voice") as ws:
        # Send a test text command (simulating transcribed audio)
        print(await ws.recv())  # Initial state
        
asyncio.run(test())
```

---

# PHASE 2: iOS Safari Web Interface (Day 2-3)

## Goal: Push-to-talk voice remote in Safari

### Step 2.1: Create Web Interface

Create `web/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="TV Remote">
    <link rel="apple-touch-icon" href="icon-180.png">
    <title>TV Remote</title>
    <style>
        :root {
            --bg: #000;
            --surface: #1c1c1e;
            --surface-elevated: #2c2c2e;
            --accent: #0a84ff;
            --accent-red: #ff453a;
            --text: #fff;
            --text-secondary: #98989f;
            --success: #30d158;
            --safe-top: env(safe-area-inset-top, 20px);
            --safe-bottom: env(safe-area-inset-bottom, 20px);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
            -webkit-touch-callout: none;
            -webkit-user-select: none;
            user-select: none;
        }

        html, body {
            height: 100%;
            overflow: hidden;
            touch-action: manipulation;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
            background: var(--bg);
            color: var(--text);
            display: flex;
            flex-direction: column;
            padding: var(--safe-top) 16px var(--safe-bottom);
        }

        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0 16px;
        }

        .status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 15px;
            color: var(--text-secondary);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent-red);
            transition: background 0.3s;
        }

        .status-dot.connected { background: var(--success); }

        .settings-btn {
            background: var(--surface);
            border: none;
            color: var(--text);
            width: 36px;
            height: 36px;
            border-radius: 50%;
            font-size: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* Voice Section */
        .voice-section {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 20px;
        }

        .response-area {
            min-height: 80px;
            text-align: center;
            padding: 16px;
            max-width: 300px;
        }

        .transcription {
            font-size: 17px;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }

        .transcription.active {
            color: var(--accent);
        }

        .response {
            font-size: 20px;
            font-weight: 500;
        }

        /* Main Voice Button */
        .voice-btn {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            border: none;
            background: var(--surface);
            color: var(--text);
            font-size: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s ease;
            position: relative;
        }

        .voice-btn::after {
            content: '';
            position: absolute;
            inset: -8px;
            border-radius: 50%;
            border: 3px solid transparent;
            transition: all 0.15s ease;
        }

        .voice-btn.recording {
            background: var(--accent-red);
            transform: scale(1.05);
        }

        .voice-btn.recording::after {
            border-color: var(--accent-red);
            animation: pulse 1s ease-out infinite;
        }

        .voice-btn.processing {
            background: var(--accent);
        }

        @keyframes pulse {
            0% { transform: scale(1); opacity: 0.8; }
            100% { transform: scale(1.4); opacity: 0; }
        }

        .voice-label {
            font-size: 15px;
            color: var(--text-secondary);
        }

        /* D-Pad */
        .dpad-section {
            padding: 20px 0;
        }

        .dpad {
            display: grid;
            grid-template-columns: repeat(3, 56px);
            grid-template-rows: repeat(3, 56px);
            gap: 8px;
            justify-content: center;
        }

        .dpad-btn {
            background: var(--surface);
            border: none;
            border-radius: 12px;
            color: var(--text);
            font-size: 22px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.1s ease;
        }

        .dpad-btn:active {
            background: var(--surface-elevated);
            transform: scale(0.95);
        }

        .dpad-btn.center {
            background: var(--surface-elevated);
            font-size: 13px;
            font-weight: 600;
        }

        .dpad-btn.empty {
            background: transparent;
        }

        /* Quick Actions */
        .quick-actions {
            display: flex;
            justify-content: center;
            gap: 12px;
            padding: 16px 0;
        }

        .quick-btn {
            background: var(--surface);
            border: none;
            border-radius: 12px;
            color: var(--text);
            padding: 12px 16px;
            font-size: 15px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.1s ease;
        }

        .quick-btn:active {
            background: var(--surface-elevated);
            transform: scale(0.97);
        }

        /* Media Controls */
        .media-controls {
            display: flex;
            justify-content: center;
            gap: 24px;
            padding: 8px 0 16px;
        }

        .media-btn {
            background: none;
            border: none;
            color: var(--text);
            font-size: 28px;
            padding: 8px;
        }

        .media-btn:active {
            opacity: 0.6;
        }

        /* Settings Modal */
        .modal {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.85);
            z-index: 100;
            align-items: flex-end;
            justify-content: center;
        }

        .modal.open { display: flex; }

        .modal-content {
            background: var(--surface);
            border-radius: 20px 20px 0 0;
            padding: 24px;
            width: 100%;
            max-width: 500px;
            padding-bottom: calc(var(--safe-bottom) + 24px);
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }

        .modal-header h2 {
            font-size: 20px;
            font-weight: 600;
        }

        .modal-close {
            background: var(--surface-elevated);
            border: none;
            color: var(--text);
            width: 32px;
            height: 32px;
            border-radius: 50%;
            font-size: 18px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .form-group input {
            width: 100%;
            padding: 14px 16px;
            border-radius: 12px;
            border: none;
            background: var(--bg);
            color: var(--text);
            font-size: 17px;
        }

        .save-btn {
            width: 100%;
            padding: 16px;
            border-radius: 12px;
            border: none;
            background: var(--accent);
            color: var(--text);
            font-size: 17px;
            font-weight: 600;
        }

        .save-btn:active {
            opacity: 0.8;
        }

        /* Loading overlay */
        .loading {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.7);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 50;
        }

        .loading.active { display: flex; }

        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--surface);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <!-- Header -->
    <div class="header">
        <div class="status">
            <div class="status-dot" id="statusDot"></div>
            <span id="statusText">Connecting...</span>
        </div>
        <button class="settings-btn" onclick="openSettings()">⚙️</button>
    </div>

    <!-- Voice Section -->
    <div class="voice-section">
        <div class="response-area">
            <div class="transcription" id="transcription"></div>
            <div class="response" id="response">Hold to speak</div>
        </div>

        <button 
            class="voice-btn" 
            id="voiceBtn"
            ontouchstart="startRecording(event)"
            ontouchend="stopRecording(event)"
            ontouchcancel="stopRecording(event)"
        >🎤</button>

        <div class="voice-label" id="voiceLabel">Push to Talk</div>
    </div>

    <!-- D-Pad Navigation -->
    <div class="dpad-section">
        <div class="dpad">
            <div class="dpad-btn empty"></div>
            <button class="dpad-btn" onclick="sendNav('up')">▲</button>
            <div class="dpad-btn empty"></div>
            <button class="dpad-btn" onclick="sendNav('left')">◀</button>
            <button class="dpad-btn center" onclick="sendNav('select')">OK</button>
            <button class="dpad-btn" onclick="sendNav('right')">▶</button>
            <div class="dpad-btn empty"></div>
            <button class="dpad-btn" onclick="sendNav('down')">▼</button>
            <div class="dpad-btn empty"></div>
        </div>
    </div>

    <!-- Media Controls -->
    <div class="media-controls">
        <button class="media-btn" onclick="sendPlayback('rewind')">⏪</button>
        <button class="media-btn" onclick="sendPlayback('play')">▶️</button>
        <button class="media-btn" onclick="sendPlayback('pause')">⏸</button>
        <button class="media-btn" onclick="sendPlayback('fast_forward')">⏩</button>
    </div>

    <!-- Quick Actions -->
    <div class="quick-actions">
        <button class="quick-btn" onclick="sendNav('back')">← Back</button>
        <button class="quick-btn" onclick="sendNav('home')">🏠 Home</button>
    </div>

    <!-- Settings Modal -->
    <div class="modal" id="settingsModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>Settings</h2>
                <button class="modal-close" onclick="closeSettings()">✕</button>
            </div>
            <div class="form-group">
                <label>Server URL</label>
                <input type="url" id="serverUrl" placeholder="ws://192.168.1.100:8765">
            </div>
            <button class="save-btn" onclick="saveSettings()">Save & Connect</button>
        </div>
    </div>

    <!-- Loading Overlay -->
    <div class="loading" id="loading">
        <div class="spinner"></div>
    </div>

    <script>
        // ============ Configuration ============
        const CONFIG = {
            serverUrl: localStorage.getItem('tv_server_url') || '',
            sampleRate: 16000
        };

        // ============ State ============
        let ws = null;
        let isRecording = false;
        let audioContext = null;
        let audioChunks = [];
        let reconnectTimer = null;

        // ============ DOM Elements ============
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        const voiceBtn = document.getElementById('voiceBtn');
        const voiceLabel = document.getElementById('voiceLabel');
        const transcription = document.getElementById('transcription');
        const response = document.getElementById('response');
        const loading = document.getElementById('loading');

        // ============ WebSocket ============
        function connect() {
            if (!CONFIG.serverUrl) {
                statusText.textContent = 'Not configured';
                openSettings();
                return;
            }

            clearTimeout(reconnectTimer);
            statusText.textContent = 'Connecting...';
            statusDot.classList.remove('connected');

            try {
                ws = new WebSocket(CONFIG.serverUrl);

                ws.onopen = () => {
                    console.log('Connected');
                    statusDot.classList.add('connected');
                    statusText.textContent = 'Connected';
                };

                ws.onmessage = (event) => {
                    handleMessage(JSON.parse(event.data));
                };

                ws.onclose = () => {
                    console.log('Disconnected');
                    statusDot.classList.remove('connected');
                    statusText.textContent = 'Disconnected';
                    ws = null;
                    
                    // Reconnect after 3 seconds
                    reconnectTimer = setTimeout(connect, 3000);
                };

                ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    statusText.textContent = 'Connection error';
                };

            } catch (e) {
                console.error('Connection failed:', e);
                statusText.textContent = 'Invalid URL';
            }
        }

        function handleMessage(data) {
            console.log('Message:', data);
            loading.classList.remove('active');

            switch (data.type) {
                case 'state':
                    // Initial state from server
                    if (data.tv_connected) {
                        statusText.textContent = 'TV Connected';
                    }
                    break;

                case 'response':
                    // Voice command response
                    if (data.transcription) {
                        transcription.textContent = `"${data.transcription}"`;
                        transcription.classList.remove('active');
                    }
                    if (data.response) {
                        response.textContent = data.response;
                        speak(data.response);
                    }
                    break;

                case 'tv_status':
                    statusText.textContent = data.connected ? 'TV Connected' : 'TV Offline';
                    break;

                case 'error':
                    response.textContent = data.error || 'Error occurred';
                    break;
            }
        }

        // ============ Audio Recording ============
        async function startRecording(event) {
            event.preventDefault();
            if (isRecording || !ws || ws.readyState !== WebSocket.OPEN) return;
            
            isRecording = true;
            voiceBtn.classList.add('recording');
            voiceLabel.textContent = 'Listening...';
            transcription.textContent = '';
            transcription.classList.add('active');
            response.textContent = 'Listening...';
            
            // Haptic feedback
            if (navigator.vibrate) navigator.vibrate(10);

            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        channelCount: 1,
                        sampleRate: CONFIG.sampleRate,
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    }
                });

                audioContext = new (window.AudioContext || window.webkitAudioContext)({
                    sampleRate: CONFIG.sampleRate
                });

                const source = audioContext.createMediaStreamSource(stream);
                const processor = audioContext.createScriptProcessor(4096, 1, 1);
                
                audioChunks = [];

                processor.onaudioprocess = (e) => {
                    if (isRecording) {
                        const inputData = e.inputBuffer.getChannelData(0);
                        const int16Data = new Int16Array(inputData.length);
                        for (let i = 0; i < inputData.length; i++) {
                            int16Data[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
                        }
                        audioChunks.push(int16Data);
                    }
                };

                source.connect(processor);
                processor.connect(audioContext.destination);

                window._stream = stream;
                window._processor = processor;
                window._source = source;

            } catch (err) {
                console.error('Microphone error:', err);
                response.textContent = 'Microphone access denied';
                stopRecording();
            }
        }

        function stopRecording(event) {
            if (event) event.preventDefault();
            if (!isRecording) return;
            
            isRecording = false;
            voiceBtn.classList.remove('recording');
            voiceLabel.textContent = 'Push to Talk';
            
            // Haptic feedback
            if (navigator.vibrate) navigator.vibrate(10);

            // Cleanup audio
            if (window._stream) {
                window._stream.getTracks().forEach(t => t.stop());
            }
            if (window._processor) window._processor.disconnect();
            if (window._source) window._source.disconnect();
            if (audioContext) {
                audioContext.close();
                audioContext = null;
            }

            // Send audio
            if (audioChunks.length > 0 && ws && ws.readyState === WebSocket.OPEN) {
                voiceBtn.classList.add('processing');
                response.textContent = 'Processing...';
                loading.classList.add('active');
                sendAudio();
            }
        }

        function sendAudio() {
            // Combine chunks
            const totalLength = audioChunks.reduce((acc, c) => acc + c.length, 0);
            const combined = new Int16Array(totalLength);
            let offset = 0;
            for (const chunk of audioChunks) {
                combined.set(chunk, offset);
                offset += chunk.length;
            }

            // Create WAV
            const wavBuffer = createWav(combined, CONFIG.sampleRate);

            // Send metadata
            ws.send(JSON.stringify({
                type: 'audio',
                sample_rate: CONFIG.sampleRate,
                format: 'wav'
            }));

            // Send audio
            ws.send(wavBuffer);

            audioChunks = [];
            voiceBtn.classList.remove('processing');
        }

        function createWav(samples, sampleRate) {
            const buffer = new ArrayBuffer(44 + samples.length * 2);
            const view = new DataView(buffer);

            // RIFF header
            writeString(view, 0, 'RIFF');
            view.setUint32(4, 36 + samples.length * 2, true);
            writeString(view, 8, 'WAVE');
            
            // fmt chunk
            writeString(view, 12, 'fmt ');
            view.setUint32(16, 16, true);
            view.setUint16(20, 1, true);
            view.setUint16(22, 1, true);
            view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * 2, true);
            view.setUint16(32, 2, true);
            view.setUint16(34, 16, true);
            
            // data chunk
            writeString(view, 36, 'data');
            view.setUint32(40, samples.length * 2, true);

            for (let i = 0; i < samples.length; i++) {
                view.setInt16(44 + i * 2, samples[i], true);
            }

            return buffer;
        }

        function writeString(view, offset, string) {
            for (let i = 0; i < string.length; i++) {
                view.setUint8(offset + i, string.charCodeAt(i));
            }
        }

        // ============ TTS ============
        function speak(text) {
            if ('speechSynthesis' in window && text) {
                const utterance = new SpeechSynthesisUtterance(text);
                utterance.rate = 1.1;
                speechSynthesis.speak(utterance);
            }
        }

        // ============ Commands ============
        function sendNav(direction) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'navigate', direction }));
                if (navigator.vibrate) navigator.vibrate(5);
            }
        }

        function sendPlayback(action) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'playback', action }));
                if (navigator.vibrate) navigator.vibrate(5);
            }
        }

        // ============ Settings ============
        function openSettings() {
            document.getElementById('settingsModal').classList.add('open');
            document.getElementById('serverUrl').value = CONFIG.serverUrl;
        }

        function closeSettings() {
            document.getElementById('settingsModal').classList.remove('open');
        }

        function saveSettings() {
            const url = document.getElementById('serverUrl').value.trim();
            if (url) {
                CONFIG.serverUrl = url;
                localStorage.setItem('tv_server_url', url);
                closeSettings();
                connect();
            }
        }

        // ============ Prevent zoom ============
        document.addEventListener('gesturestart', e => e.preventDefault());
        document.addEventListener('gesturechange', e => e.preventDefault());

        // ============ Initialize ============
        document.addEventListener('DOMContentLoaded', () => {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                response.textContent = 'Microphone not supported';
                voiceBtn.disabled = true;
            }
            connect();
        });
    </script>
</body>
</html>
```

### Step 2.2: Serve the Web Interface

```bash
# On ThinkStation, serve the web folder
cd ~/tv-brain

# Create web directory and copy the HTML
mkdir -p web
# Copy index.html to web/

# Serve with Python (for testing)
cd web
python3 -m http.server 8080

# Or add to your server with a simple HTTP handler
```

**Better: Add static file serving to the main server** (add to main.py or use nginx).

### Step 2.3: SSL for iOS Microphone Access

iOS Safari requires HTTPS for microphone access (except localhost). Quick solution:

```bash
# Generate self-signed certificate
cd ~/tv-brain
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes \
    -subj "/CN=tv-brain.local"

# Create a simple HTTPS server for the web interface
# https_server.py
```

```python
# https_server.py
import ssl
import http.server
import socketserver

PORT = 8443
DIRECTORY = "web"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain('cert.pem', 'key.pem')

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    print(f"Serving HTTPS on port {PORT}")
    httpd.serve_forever()
```

### Step 2.4: Access from iPhone

1. Run HTTPS server: `python3 https_server.py`
2. On iPhone, open Safari: `https://YOUR_THINKSTATION_IP:8443`
3. Accept the self-signed certificate warning
4. Tap ⚙️, enter: `wss://YOUR_THINKSTATION_IP:8765/voice` (note: wss for secure)
5. Add to Home Screen for app-like experience

**Note**: For WSS (secure WebSocket), you'll need to add SSL to the main server too. See Phase 2 bonus below.

### Step 2.5 (Bonus): Add SSL to WebSocket Server

Modify the `run()` method in main.py:

```python
import ssl

async def run(self):
    await self.initialize()
    
    # SSL context for WSS
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain('cert.pem', 'key.pem')
    
    async with websockets.serve(
        self.router,
        Config.HOST,
        Config.PORT,
        ssl=ssl_context,  # Add this
        ping_interval=30,
        ping_timeout=10,
        max_size=10 * 1024 * 1024
    ):
        # ...
```

---

# PHASE 3: Dell 5070 TV Platform (Day 4-5)

## Goal: Custom TV UI receiving commands from brain

### Step 3.1: OS Installation

```bash
# 1. Download Ubuntu Server 24.04 LTS (minimal)
# 2. Flash to USB drive with Balena Etcher
# 3. Boot Dell 5070 from USB
# 4. Install with:
#    - Minimal installation
#    - OpenSSH server
#    - Username: tv
#    - Hostname: tv-platform
```

### Step 3.2: Initial System Setup

```bash
# SSH into Dell 5070
ssh tv@192.168.1.101

# Update system
sudo apt update && sudo apt upgrade -y

# Install essentials
sudo apt install -y \
    git curl wget \
    build-essential \
    python3-pip python3-venv \
    nodejs npm \
    chromium-browser \
    chromium-codecs-ffmpeg-extra \
    vainfo intel-media-va-driver \
    pulseaudio alsa-utils \
    xorg cage \
    libcec6 cec-utils

# Enable hardware video acceleration
sudo apt install -y intel-media-va-driver-non-free
```

### Step 3.3: Install Widevine for DRM Streaming

```bash
# Download Widevine from Chrome
cd /tmp
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
dpkg-deb -x google-chrome-stable_current_amd64.deb chrome-tmp
sudo mkdir -p /usr/lib/chromium
sudo cp -r chrome-tmp/opt/google/chrome/WidevineCdm /usr/lib/chromium/
rm -rf chrome-tmp google-chrome-stable_current_amd64.deb

# Verify
ls /usr/lib/chromium/WidevineCdm/
```

### Step 3.4: TV UI Project Setup

```bash
mkdir -p ~/tv-ui
cd ~/tv-ui

# Initialize React project
npm create vite@latest . -- --template react-ts

# Install dependencies
npm install
npm install @norigin/spatial-navigation framer-motion zustand
```

### Step 3.5: TV UI Implementation

Create `src/App.tsx`:

```tsx
import { useEffect, useState, useCallback } from 'react';
import { init, useFocusable, FocusContext } from '@norigin/spatial-navigation';
import './App.css';

// Initialize spatial navigation
init({ debug: false, visualDebug: false });

// WebSocket connection to brain
const BRAIN_URL = import.meta.env.VITE_BRAIN_URL || 'ws://192.168.1.100:8765/tv';

interface TVState {
  power: string;
  app: string | null;
  screen: string;
  volume: number;
  nowPlaying: string | null;
}

interface Command {
  type: string;
  [key: string]: any;
}

function App() {
  const { ref, focusKey, focusSelf } = useFocusable();
  const [connected, setConnected] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [tvState, setTvState] = useState<TVState>({
    power: 'on',
    app: null,
    screen: 'home',
    volume: 50,
    nowPlaying: null
  });

  // Connect to brain
  useEffect(() => {
    function connect() {
      const socket = new WebSocket(BRAIN_URL);
      
      socket.onopen = () => {
        console.log('Connected to brain');
        setConnected(true);
        setWs(socket);
        
        // Send initial state
        socket.send(JSON.stringify({
          type: 'state',
          state: tvState
        }));
      };
      
      socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleCommand(data);
      };
      
      socket.onclose = () => {
        console.log('Disconnected from brain');
        setConnected(false);
        setWs(null);
        setTimeout(connect, 3000);
      };
      
      socket.onerror = (err) => {
        console.error('WebSocket error:', err);
      };
    }
    
    connect();
    focusSelf();
    
    return () => {
      ws?.close();
    };
  }, []);

  // Handle commands from brain
  const handleCommand = useCallback((data: any) => {
    if (data.type !== 'command') return;
    
    const cmd = data as Command;
    console.log('Command:', cmd);
    
    switch (cmd.type) {
      case 'navigate':
        simulateKey(cmd.direction, cmd.repeat || 1);
        break;
        
      case 'launch_app':
        launchApp(cmd.app);
        break;
        
      case 'playback':
        handlePlayback(cmd.action);
        break;
        
      case 'volume':
        handleVolume(cmd.action, cmd.level, cmd.steps);
        break;
        
      case 'play_content':
        playContent(cmd.title, cmd.service);
        break;
        
      case 'type_text':
        typeText(cmd.text);
        break;
    }
  }, []);

  // Simulate keyboard navigation
  const simulateKey = (direction: string, repeat: number = 1) => {
    const keyMap: Record<string, string> = {
      up: 'ArrowUp',
      down: 'ArrowDown', 
      left: 'ArrowLeft',
      right: 'ArrowRight',
      select: 'Enter',
      back: 'Escape',
      home: 'Home'
    };
    
    const key = keyMap[direction];
    if (!key) return;
    
    for (let i = 0; i < repeat; i++) {
      setTimeout(() => {
        window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
      }, i * 100);
    }
  };

  // Launch streaming app
  const launchApp = (app: string) => {
    const appUrls: Record<string, string> = {
      netflix: 'https://www.netflix.com/browse',
      hulu: 'https://www.hulu.com/hub/home',
      disney: 'https://www.disneyplus.com/home',
      disney_plus: 'https://www.disneyplus.com/home',
      prime: 'https://www.amazon.com/gp/video/storefront',
      prime_video: 'https://www.amazon.com/gp/video/storefront',
      youtube: 'https://www.youtube.com/tv',
      hbo: 'https://play.max.com/',
      max: 'https://play.max.com/',
      paramount: 'https://www.paramountplus.com/',
      peacock: 'https://www.peacocktv.com/',
      spotify: 'https://open.spotify.com/'
    };
    
    const url = appUrls[app.toLowerCase()];
    if (url) {
      setTvState(s => ({ ...s, app, screen: 'app' }));
      // In a real implementation, this would navigate to the URL
      // For now, just update state
      console.log(`Launching ${app}: ${url}`);
    }
  };

  // Playback control
  const handlePlayback = (action: string) => {
    // Simulate media key presses
    const mediaKeys: Record<string, string> = {
      play: 'MediaPlayPause',
      pause: 'MediaPlayPause',
      stop: 'MediaStop',
      skip_forward: 'MediaTrackNext',
      skip_backward: 'MediaTrackPrevious',
      rewind: 'MediaRewind',
      fast_forward: 'MediaFastForward'
    };
    
    const key = mediaKeys[action];
    if (key) {
      window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
    }
  };

  // Volume control
  const handleVolume = (action: string, level?: number, steps: number = 1) => {
    // This would integrate with CEC for actual TV volume
    console.log(`Volume: ${action}, level: ${level}, steps: ${steps}`);
  };

  // Play specific content
  const playContent = (title: string, service?: string) => {
    console.log(`Playing: ${title} on ${service || 'best available'}`);
    // This would search for and navigate to the content
  };

  // Type text into search field
  const typeText = (text: string) => {
    const activeElement = document.activeElement as HTMLInputElement;
    if (activeElement && activeElement.tagName === 'INPUT') {
      activeElement.value = text;
      activeElement.dispatchEvent(new Event('input', { bubbles: true }));
    }
  };

  // Report state back to brain
  const reportState = useCallback(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'state',
        state: tvState
      }));
    }
  }, [ws, tvState]);

  useEffect(() => {
    reportState();
  }, [tvState, reportState]);

  return (
    <FocusContext.Provider value={focusKey}>
      <div ref={ref} className="tv-app">
        <header className="header">
          <div className={`connection-status ${connected ? 'connected' : ''}`}>
            {connected ? '🟢 Connected' : '🔴 Disconnected'}
          </div>
          <h1>TV Platform</h1>
        </header>
        
        <main className="main-content">
          {/* Your TV UI content here */}
          <AppGrid onSelectApp={launchApp} />
        </main>
      </div>
    </FocusContext.Provider>
  );
}

// Simple app grid component
function AppGrid({ onSelectApp }: { onSelectApp: (app: string) => void }) {
  const apps = [
    { id: 'netflix', name: 'Netflix', icon: '🔴' },
    { id: 'hulu', name: 'Hulu', icon: '🟢' },
    { id: 'disney', name: 'Disney+', icon: '🔵' },
    { id: 'prime', name: 'Prime Video', icon: '🟡' },
    { id: 'youtube', name: 'YouTube', icon: '▶️' },
    { id: 'max', name: 'Max', icon: '🟣' },
  ];
  
  return (
    <div className="app-grid">
      {apps.map(app => (
        <AppCard key={app.id} app={app} onSelect={onSelectApp} />
      ))}
    </div>
  );
}

function AppCard({ app, onSelect }: { app: { id: string; name: string; icon: string }; onSelect: (id: string) => void }) {
  const { ref, focused } = useFocusable({
    onEnterPress: () => onSelect(app.id)
  });
  
  return (
    <div ref={ref} className={`app-card ${focused ? 'focused' : ''}`}>
      <span className="app-icon">{app.icon}</span>
      <span className="app-name">{app.name}</span>
    </div>
  );
}

export default App;
```

Create `src/App.css`:

```css
:root {
  --bg: #0a0a0a;
  --surface: #1a1a1a;
  --text: #ffffff;
  --text-muted: #888;
  --accent: #e50914;
  --focus-ring: #fff;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
  cursor: none;
}

.tv-app {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 48px;
}

.connection-status {
  font-size: 14px;
  color: var(--text-muted);
}

.connection-status.connected {
  color: #30d158;
}

.main-content {
  flex: 1;
  padding: 0 48px;
}

.app-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 24px;
  padding: 24px 0;
}

.app-card {
  background: var(--surface);
  border-radius: 16px;
  padding: 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  transition: all 0.2s ease;
}

.app-card.focused {
  transform: scale(1.05);
  box-shadow: 0 0 0 4px var(--focus-ring);
}

.app-icon {
  font-size: 48px;
}

.app-name {
  font-size: 18px;
  font-weight: 500;
}
```

### Step 3.6: Build and Deploy TV UI

```bash
cd ~/tv-ui

# Set brain URL
echo "VITE_BRAIN_URL=ws://192.168.1.100:8765/tv" > .env

# Build
npm run build

# The built files are in dist/
```

### Step 3.7: Auto-Start TV UI in Kiosk Mode

```bash
# Create startup script
cat > ~/start-tv.sh << 'EOF'
#!/bin/bash

# Start PulseAudio
pulseaudio --start

# Start Chromium in kiosk mode with Cage (Wayland compositor)
cage -- chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-session-crashed-bubble \
    --disable-features=TranslateUI \
    --enable-features=VaapiVideoDecoder \
    --enable-gpu-rasterization \
    --ignore-gpu-blocklist \
    --user-data-dir=/home/tv/.config/chromium-tv \
    file:///home/tv/tv-ui/dist/index.html
EOF

chmod +x ~/start-tv.sh
```

### Step 3.8: Enable Auto-Login and Auto-Start

```bash
# Auto-login
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d/
sudo tee /etc/systemd/system/getty@tty1.service.d/override.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin tv --noclear %I \$TERM
EOF

# Auto-start TV UI
echo '[ -z "$DISPLAY" ] && [ $(tty) = /dev/tty1 ] && ~/start-tv.sh' >> ~/.profile

# Reboot to test
sudo reboot
```

---

# PHASE 4: Integration & Testing (Day 6-7)

## 4.1: End-to-End Test Checklist

```markdown
### Connection Tests
- [ ] Phone connects to ThinkStation WebSocket
- [ ] Dell 5070 connects to ThinkStation WebSocket
- [ ] Both connections survive reconnection
- [ ] Status indicators update correctly

### Voice Tests
- [ ] "Open Netflix" → Netflix launches
- [ ] "Pause" → Playback pauses
- [ ] "Turn up the volume" → Volume increases
- [ ] "Go back" → Navigation goes back
- [ ] "Play Stranger Things" → Content search works

### Navigation Tests
- [ ] D-pad buttons work from phone
- [ ] Focus moves correctly on TV UI
- [ ] Select/OK triggers actions
- [ ] Back/Home buttons work

### State Sync Tests
- [ ] TV state reflects in phone status
- [ ] Commands update TV state
- [ ] State persists across reconnections
```

## 4.2: Debugging Commands

```bash
# Monitor ThinkStation logs
journalctl -u tv-brain -f

# Test WebSocket connection
websocat ws://localhost:8765/voice

# Monitor Dell 5070 logs  
journalctl -u tv-ui -f

# Check network connectivity
ping 192.168.1.100  # ThinkStation
ping 192.168.1.101  # Dell 5070
```

## 4.3: Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Mic not working on iOS | Need HTTPS | Use self-signed cert + wss:// |
| Whisper slow | Using large model | Use `base.en` model |
| TV commands lag | Network latency | Use wired ethernet |
| DRM content black | Missing Widevine | Reinstall from Chrome |
| Focus doesn't move | Spatial nav not init | Check `init()` called |

---

# Quick Reference

## IP Addresses
```
ThinkStation: 192.168.1.100
Dell 5070:    192.168.1.101
iPhone:       (DHCP)
```

## Ports
```
8765  - WebSocket server (voice + TV)
8443  - HTTPS web server (phone UI)
```

## WebSocket Endpoints
```
wss://192.168.1.100:8765/voice  - Phone voice remote
ws://192.168.1.100:8765/tv      - Dell 5070 TV platform
```

## Start Commands
```bash
# ThinkStation
cd ~/tv-brain && source venv/bin/activate && python src/main.py

# Dell 5070 (auto-starts)
~/start-tv.sh
```

## Voice Command Examples
```
"Open Netflix"
"Play The Office on Peacock"
"Pause"
"Skip forward 30 seconds"
"Turn up the volume"
"Go back"
"Search for comedy movies"
"Go home"
```
