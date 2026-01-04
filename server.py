#!/usr/bin/env python3
"""
TV Brain Server - Simplified version for phone voice remote
Handles voice commands from web browser and controls Dell 5070 TV platform
"""

import asyncio
import json
import logging
import os
import io
import base64
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
import websockets
import httpx
import anthropic

# Groq API for cloud Whisper
GROQ_API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ Configuration ============
CONFIG = {
    "whisper_model": os.environ.get("WHISPER_MODEL", "base.en"),  # Options: tiny.en, base.en, small.en, medium.en, large-v3
    "whisper_device": os.environ.get("WHISPER_DEVICE", "cpu"),  # "cpu" or "cuda"
    "anthropic_model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
    "tv_platform_url": os.environ.get("TV_URL", "ws://192.168.1.101:9000"),
    "host": "0.0.0.0",
    "port": 8765
}

# ============ Claude TV Tools ============
TV_TOOLS = [
    {
        "name": "navigate",
        "description": "Navigate the TV interface with directional commands.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "left", "right", "select", "back", "home"],
                },
                "repeat": {"type": "integer", "default": 1}
            },
            "required": ["direction"]
        }
    },
    {
        "name": "playback_control",
        "description": "Control media playback (play, pause, stop, skip).",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["play", "pause", "stop", "skip_forward", "skip_backward", "rewind", "fast_forward"],
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "volume_control",
        "description": "Control TV volume.",
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
        "description": "Launch a streaming app (netflix, hulu, disney_plus, youtube, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "app": {"type": "string"}
            },
            "required": ["app"]
        }
    },
    {
        "name": "search_content",
        "description": "Search for movies or TV shows to watch.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "type": {"type": "string", "enum": ["movie", "series", "any"], "default": "any"},
                "service": {"type": "string"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "play_content",
        "description": "Play a specific movie or show by name.",
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
        "name": "type_text",
        "description": "Type text into the current text field (for search boxes).",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"}
            },
            "required": ["text"]
        }
    }
]

SYSTEM_PROMPT = """You are a TV voice assistant. Parse voice commands and control the TV.

Current TV state:
- Power: {power}
- App: {app}
- Volume: {volume}

Instructions:
1. Use tools to execute commands
2. Be brief in responses - this is spoken aloud
3. For simple commands (pause, volume up), just confirm briefly
4. For ambiguous requests, make reasonable assumptions

Examples:
- "Pause" → use playback_control with action=pause, respond "Paused"
- "Open Netflix" → use launch_app with app=netflix, respond "Opening Netflix"
- "Turn it up" → use volume_control with action=up, respond "Volume up"
"""


class TVBrain:
    def __init__(self):
        self.claude: Optional[anthropic.Anthropic] = None
        self.groq_api_key: Optional[str] = None
        self.tv_websocket = None
        self.phone_clients = set()
        self.tv_state = {
            "power": "on",
            "app": "home",
            "volume": 50,
            "now_playing": None
        }
        self.conversation_history = []

    async def initialize(self):
        """Initialize API clients"""
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        if not self.groq_api_key:
            logger.warning("GROQ_API_KEY not set - speech-to-text will not work")
        else:
            logger.info("Groq API key configured for cloud Whisper")

        self.claude = anthropic.Anthropic()
        logger.info("Claude client initialized")

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio to text using Groq's cloud Whisper API"""
        if not self.groq_api_key:
            logger.error("No Groq API key configured")
            return ""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    GROQ_API_URL,
                    headers={"Authorization": f"Bearer {self.groq_api_key}"},
                    files={"file": ("audio.webm", audio_bytes, "audio/webm")},
                    data={
                        "model": "whisper-large-v3",
                        "language": "en",
                        "response_format": "json"
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                text = result.get("text", "").strip()
                logger.info(f"Transcribed: '{text}'")
                return text
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    async def process_command(self, text: str) -> dict:
        """Process transcribed text through Claude"""
        if not text.strip():
            return {"tts_response": "I didn't catch that", "commands": []}

        # Build system prompt with current state
        system = SYSTEM_PROMPT.format(**self.tv_state)

        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": text})
        
        # Keep last 10 exchanges
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

        # Call Claude
        response = self.claude.messages.create(
            model=CONFIG["anthropic_model"],
            max_tokens=512,
            system=system,
            tools=TV_TOOLS,
            messages=self.conversation_history
        )

        # Extract tools and response
        tool_calls = []
        text_response = ""

        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append({
                    "name": block.name,
                    "input": block.input
                })
            elif block.type == "text":
                text_response = block.text

        # Add assistant response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": response.content
        })

        # Convert tool calls to commands
        commands = []
        for tool in tool_calls:
            cmd = {"type": tool["name"], **tool["input"]}
            commands.append(cmd)
            logger.info(f"Command: {cmd}")

        return {
            "tts_response": text_response or "Done",
            "commands": commands,
            "transcription": text
        }

    async def send_to_tv(self, commands: list):
        """Send commands to TV platform"""
        if self.tv_websocket:
            for cmd in commands:
                await self.tv_websocket.send(json.dumps({"type": "command", **cmd}))
        else:
            logger.warning("TV not connected, cannot send commands")

    async def handle_phone_client(self, websocket):
        """Handle WebSocket connection from phone"""
        self.phone_clients.add(websocket)
        client_addr = websocket.remote_address
        logger.info(f"Phone connected: {client_addr}")

        try:
            audio_metadata = None
            
            async for message in websocket:
                if isinstance(message, str):
                    # JSON message
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "audio":
                        # Next message will be audio bytes
                        audio_metadata = data
                        logger.info("Expecting audio data...")

                    elif msg_type == "navigate":
                        # Direct navigation from D-pad
                        cmd = {"type": "navigate", "direction": data["direction"]}
                        await self.send_to_tv([cmd])

                    elif msg_type == "playback":
                        cmd = {"type": "playback_control", **data}
                        await self.send_to_tv([cmd])

                else:
                    # Binary message - audio data
                    if audio_metadata:
                        logger.info(f"Received {len(message)} bytes of audio")
                        
                        # Transcribe
                        text = await self.transcribe(message)
                        
                        # Process through Claude
                        result = await self.process_command(text)
                        
                        # Send commands to TV
                        if result["commands"]:
                            await self.send_to_tv(result["commands"])
                        
                        # Send response back to phone
                        await websocket.send(json.dumps(result))
                        
                        audio_metadata = None

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Phone disconnected: {client_addr}")
        except Exception as e:
            logger.error(f"Error handling phone client: {e}")
        finally:
            self.phone_clients.discard(websocket)

    async def handle_tv_platform(self, websocket):
        """Handle WebSocket connection from Dell 5070 TV platform"""
        self.tv_websocket = websocket
        logger.info("TV platform connected")

        try:
            async for message in websocket:
                data = json.loads(message)
                
                if data.get("type") == "state_update":
                    self.tv_state.update(data.get("state", {}))
                    logger.debug(f"TV state updated: {self.tv_state}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("TV platform disconnected")
        finally:
            self.tv_websocket = None

    async def router(self, websocket, path):
        """Route WebSocket connections based on path"""
        logger.info(f"New connection: {path} from {websocket.remote_address}")
        
        if path == "/voice" or path == "/":
            await self.handle_phone_client(websocket)
        elif path == "/tv":
            await self.handle_tv_platform(websocket)
        else:
            logger.warning(f"Unknown path: {path}")
            await websocket.close(1003, "Unknown path")

    async def health_check(self, path, request_headers):
        """Handle HTTP health check requests from Render"""
        if path == "/health" or path == "/":
            return (200, [("Content-Type", "text/plain")], b"OK")
        return None  # Continue with WebSocket handshake

    async def run(self):
        """Start the WebSocket server"""
        await self.initialize()

        # Get port from environment (Render sets PORT)
        port = int(os.environ.get("PORT", CONFIG["port"]))

        logger.info(f"Starting server on {CONFIG['host']}:{port}")

        async with websockets.serve(
            self.router,
            CONFIG["host"],
            port,
            ping_interval=30,
            ping_timeout=10,
            process_request=self.health_check
        ):
            logger.info(f"Server running at ws://{CONFIG['host']}:{port}")
            logger.info("Endpoints:")
            logger.info("  /voice - Phone voice remote")
            logger.info("  /tv    - Dell 5070 TV platform")
            logger.info("  /health - HTTP health check")
            await asyncio.Future()  # Run forever


async def main():
    brain = TVBrain()
    await brain.run()


if __name__ == "__main__":
    asyncio.run(main())
