# Voice-Controlled TV Platform: Complete Technical Blueprint

## Project Codename: "Corelia TV" (or whatever you want to call it)

---

# TABLE OF CONTENTS

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Hardware Requirements & Roles](#2-hardware-requirements--roles)
3. [Phase 0: Pi Zero W Prototype (Today)](#3-phase-0-pi-zero-w-prototype-today)
4. [Phase 1: ThinkStation Backend Setup](#4-phase-1-thinkstation-backend-setup)
5. [Phase 2: Dell 5070 TV Platform](#5-phase-2-dell-5070-tv-platform)
6. [Phase 3: Custom TV UI Development](#6-phase-3-custom-tv-ui-development)
7. [Phase 4: Voice Pipeline Integration](#7-phase-4-voice-pipeline-integration)
8. [Phase 5: Content Discovery & Recommendations](#8-phase-5-content-discovery--recommendations)
9. [Phase 6: Production Hardening](#9-phase-6-production-hardening)
10. [API Specifications](#10-api-specifications)
11. [Database Schema](#11-database-schema)
12. [File Structure](#12-file-structure)
13. [Development Workflow](#13-development-workflow)
14. [Bill of Materials](#14-bill-of-materials)

---

# 1. SYSTEM ARCHITECTURE OVERVIEW

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    NETWORK (WiFi/Ethernet)                               │
└─────────────────────────────────────────────────────────────────────────────────────────┘
        │                                    │                                    │
        ▼                                    ▼                                    ▼
┌───────────────────┐              ┌───────────────────┐              ┌───────────────────┐
│   PI ZERO W       │              │   THINKSTATION    │              │   DELL 5070       │
│   "Voice Bridge"  │              │   "Brain"         │              │   "TV Platform"   │
│                   │              │                   │              │                   │
│ • Wake word       │    Audio     │ • Whisper STT     │   Commands   │ • Custom TV UI    │
│ • Mic array       │ ──────────►  │ • Claude API      │ ──────────►  │ • Streaming apps  │
│ • IR blaster      │              │ • Orchestrator    │              │ • Media playback  │
│ • CEC control     │  ◄────────── │ • State manager   │  ◄────────── │ • Input handler   │
│ • TTS speaker     │    Speech    │ • Content DB      │    State     │ • CEC receiver    │
│                   │              │ • Recommendations │              │                   │
└───────────────────┘              └───────────────────┘              └───────────────────┘
        │                                                                      │
        │                         HDMI + CEC                                   │
        └──────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                               ┌───────────────────┐
                               │       TV          │
                               │   (Any HDMI TV)   │
                               └───────────────────┘
```

## Data Flow for Voice Commands

```
User speaks "Find me a good action movie on Netflix"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. PI ZERO W: Wake Word Detection                               │
│    Porcupine detects "Hey TV" → starts recording                │
└─────────────────────────────────────────────────────────────────┘
                    │ Audio stream (WebSocket)
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. THINKSTATION: Speech-to-Text                                 │
│    faster-whisper transcribes → "Find me a good action movie    │
│    on Netflix"                                                  │
└─────────────────────────────────────────────────────────────────┘
                    │ Text
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. THINKSTATION: Claude Intent Processing                       │
│    Claude analyzes with tools → {                               │
│      "action": "search_content",                                │
│      "genre": "action",                                         │
│      "service": "netflix",                                      │
│      "type": "movie"                                            │
│    }                                                            │
└─────────────────────────────────────────────────────────────────┘
                    │ Structured intent
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. THINKSTATION: Content Discovery                              │
│    Query TMDB → Filter by Netflix availability →                │
│    Claude selects best matches → Returns recommendations        │
└─────────────────────────────────────────────────────────────────┘
                    │ Content list + actions
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. DELL 5070: UI Update                                         │
│    Display recommendation cards → Speak "I found 5 action       │
│    movies on Netflix. The top pick is..."                       │
└─────────────────────────────────────────────────────────────────┘
                    │ TTS audio (WebSocket)
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. PI ZERO W: Audio Output                                      │
│    Plays TTS response through speaker                           │
└─────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Primary Role | Secondary Role |
|-----------|-------------|----------------|
| **Pi Zero W** | Voice I/O (mic + speaker) | IR/CEC fallback control |
| **ThinkStation** | AI processing (Whisper + Claude) | State management, content DB |
| **Dell 5070** | TV UI + streaming playback | Primary CEC control |

---

# 2. HARDWARE REQUIREMENTS & ROLES

## Pi Zero W - "Voice Bridge"

**Purpose**: Always-listening voice input + audio output + legacy TV control

| Component | Product | Price | Notes |
|-----------|---------|-------|-------|
| Pi Zero W | You have it | $0 | 512MB RAM, WiFi built-in |
| Micro SD | 16GB+ Class 10 | $8 | For OS |
| USB Sound Card | Plugable USB Audio | $12 | Better than onboard |
| USB Microphone | ReSpeaker USB Mic Array | $69 | Or cheaper USB mic to start |
| Mini Speaker | 3W USB/3.5mm speaker | $10 | For TTS output |
| IR LED + transistor | Generic | $5 | For IR blaster |
| USB OTG Hub | Micro USB hub | $8 | To connect multiple USB devices |
| Power Supply | 5V 2.5A | $10 | Official Pi supply |

**Alternative Mic (Budget)**: $15 USB conference mic works fine for prototyping

## ThinkStation - "Brain"

**Purpose**: Heavy AI processing, orchestration, database

You already have this:
- Intel Core Ultra 9 285 (24 cores)
- 64GB DDR5 RAM
- 1TB NVMe SSD

**Software Requirements**:
- Docker + Docker Compose
- Python 3.11+
- Node.js 20+
- PostgreSQL or SQLite
- faster-whisper
- Anthropic Python SDK

## Dell Wyse 5070 - "TV Platform"

**Purpose**: Custom TV UI, streaming playback, display output

| Component | Specification | Notes |
|-----------|--------------|-------|
| Model | Dell Wyse 5070 Pentium J5005 | $50-70 on eBay |
| RAM | 8GB DDR4 minimum | Upgrade if only 4GB |
| Storage | 128GB M.2 SATA SSD | Add if only has eMMC |
| CEC Adapter | Pulse-Eight USB-CEC | $35 - Required for remote control |
| DP to HDMI | Active adapter | $15 - If TV lacks DisplayPort |

## Network Requirements

- All devices on same subnet
- Static IPs or DHCP reservations recommended
- Low latency WiFi or Ethernet preferred

**Suggested IP Scheme**:
```
ThinkStation: 192.168.1.100
Dell 5070:    192.168.1.101
Pi Zero W:    192.168.1.102
```

---

# 3. PHASE 0: PI ZERO W PROTOTYPE (TODAY)

## Goal: Working voice control of your existing Roku TV

This lets you start building immediately while waiting for the Dell 5070.

## 3.1 Flash Raspberry Pi OS Lite

```bash
# On your computer, use Raspberry Pi Imager
# Select: Raspberry Pi OS Lite (64-bit) - No desktop
# Configure WiFi and SSH in imager settings before flashing
```

**headless setup** (in boot partition after flashing):
```bash
# Create empty file to enable SSH
touch /Volumes/boot/ssh

# Create wpa_supplicant.conf for WiFi
cat > /Volumes/boot/wpa_supplicant.conf << EOF
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="YOUR_WIFI_SSID"
    psk="YOUR_WIFI_PASSWORD"
}
EOF
```

## 3.2 Initial Pi Setup

```bash
# SSH into Pi
ssh pi@raspberrypi.local
# Default password: raspberry

# Update system
sudo apt update && sudo apt upgrade -y

# Set hostname
sudo hostnamectl set-hostname voice-bridge

# Install essentials
sudo apt install -y \
    python3-pip \
    python3-venv \
    git \
    alsa-utils \
    portaudio19-dev \
    libffi-dev \
    libssl-dev

# Create project directory
mkdir -p ~/voice-bridge
cd ~/voice-bridge

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate
```

## 3.3 Install Porcupine Wake Word Engine

```bash
pip install pvporcupine pvrecorder
```

**Get free access key**: https://console.picovoice.ai/ (sign up, get key)

## 3.4 Wake Word Detection Script

Create `~/voice-bridge/wake_word.py`:

```python
#!/usr/bin/env python3
"""
Wake word detection for Voice Bridge
Listens for "Hey TV" and streams audio to ThinkStation
"""

import pvporcupine
import pvrecorder
import struct
import asyncio
import websockets
import json
import wave
import io
import os
from datetime import datetime

# Configuration
PORCUPINE_ACCESS_KEY = os.environ.get('PORCUPINE_KEY', 'YOUR_KEY_HERE')
THINKSTATION_URL = os.environ.get('BRAIN_URL', 'ws://192.168.1.100:8765')
WAKE_WORD = "jarvis"  # Built-in options: jarvis, alexa, computer, hey google, etc.
SAMPLE_RATE = 16000
RECORD_SECONDS_AFTER_WAKE = 5  # How long to record after wake word

class VoiceBridge:
    def __init__(self):
        self.porcupine = None
        self.recorder = None
        self.running = False
        
    async def start(self):
        """Initialize and run the voice bridge"""
        print("🎤 Initializing Voice Bridge...")
        
        # Initialize Porcupine
        self.porcupine = pvporcupine.create(
            access_key=PORCUPINE_ACCESS_KEY,
            keywords=[WAKE_WORD]
        )
        
        # Initialize recorder
        self.recorder = pvrecorder.PvRecorder(
            device_index=-1,  # Default device
            frame_length=self.porcupine.frame_length
        )
        
        print(f"✅ Listening for wake word: '{WAKE_WORD}'")
        print(f"📡 Will stream to: {THINKSTATION_URL}")
        
        self.recorder.start()
        self.running = True
        
        try:
            await self.listen_loop()
        finally:
            self.cleanup()
    
    async def listen_loop(self):
        """Main listening loop"""
        while self.running:
            # Get audio frame
            pcm = self.recorder.read()
            
            # Check for wake word
            keyword_index = self.porcupine.process(pcm)
            
            if keyword_index >= 0:
                print(f"🔔 Wake word detected! Recording...")
                await self.handle_wake_word()
    
    async def handle_wake_word(self):
        """Record audio after wake word and send to ThinkStation"""
        # Record audio
        frames = []
        num_frames = int(SAMPLE_RATE / self.porcupine.frame_length * RECORD_SECONDS_AFTER_WAKE)
        
        for _ in range(num_frames):
            pcm = self.recorder.read()
            frames.extend(pcm)
        
        print(f"📤 Sending {len(frames)} samples to ThinkStation...")
        
        # Convert to WAV bytes
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(struct.pack(f'{len(frames)}h', *frames))
        
        wav_bytes = wav_buffer.getvalue()
        
        # Send to ThinkStation
        try:
            async with websockets.connect(THINKSTATION_URL) as ws:
                await ws.send(json.dumps({
                    "type": "audio",
                    "timestamp": datetime.now().isoformat(),
                    "sample_rate": SAMPLE_RATE,
                    "format": "wav"
                }))
                await ws.send(wav_bytes)
                
                # Wait for response
                response = await asyncio.wait_for(ws.recv(), timeout=30)
                result = json.loads(response)
                
                print(f"📥 Received: {result}")
                
                # Handle response (TTS, execute command, etc.)
                await self.handle_response(result)
                
        except Exception as e:
            print(f"❌ Error communicating with ThinkStation: {e}")
    
    async def handle_response(self, result):
        """Handle response from ThinkStation"""
        if result.get('tts_audio'):
            # Play TTS response
            # TODO: Implement audio playback
            pass
        
        if result.get('ir_command'):
            # Send IR command
            await self.send_ir_command(result['ir_command'])
        
        if result.get('cec_command'):
            # Send CEC command
            await self.send_cec_command(result['cec_command'])
    
    async def send_ir_command(self, command):
        """Send IR command via GPIO"""
        # TODO: Implement IR blaster
        print(f"📡 IR Command: {command}")
    
    async def send_cec_command(self, command):
        """Send CEC command"""
        # TODO: Implement CEC control
        print(f"📺 CEC Command: {command}")
    
    def cleanup(self):
        """Clean up resources"""
        if self.recorder:
            self.recorder.stop()
            self.recorder.delete()
        if self.porcupine:
            self.porcupine.delete()

async def main():
    bridge = VoiceBridge()
    await bridge.start()

if __name__ == "__main__":
    asyncio.run(main())
```

## 3.5 IR Blaster Setup (Control Existing Roku)

**Hardware Wiring**:
```
Pi Zero W GPIO 18 → 330Ω resistor → IR LED anode
IR LED cathode → NPN transistor collector
Transistor base → 1kΩ resistor → GPIO 17
Transistor emitter → GND
```

**Install LIRC**:
```bash
sudo apt install -y lirc

# Configure /etc/lirc/lirc_options.conf
sudo nano /etc/lirc/lirc_options.conf
# Set: driver = default
# Set: device = /dev/lirc0

# Add to /boot/config.txt
sudo nano /boot/config.txt
# Add: dtoverlay=gpio-ir-tx,gpio_pin=18
```

**Roku IR Codes** (create `/etc/lirc/lircd.conf.d/roku.lircd.conf`):
```
begin remote
  name  roku
  flags RAW_CODES
  eps   30
  aeps  100

  begin raw_codes
    name power
      9000 4500 560 560 560 560 560 1690 560 560 560 560 560 560 560 560 560 560 560 1690 560 1690 560 560 560 1690 560 1690 560 1690 560 1690 560 1690 560 560 560 1690 560 560 560 560 560 1690 560 560 560 560 560 560 560 1690 560 560 560 1690 560 1690 560 560 560 1690 560 1690 560 1690 560
    
    name up
      9000 4500 560 560 560 560 560 1690 560 560 560 560 560 560 560 560 560 560 560 1690 560 1690 560 560 560 1690 560 1690 560 1690 560 1690 560 1690 560 560 560 560 560 560 560 1690 560 1690 560 560 560 560 560 560 560 1690 560 1690 560 1690 560 560 560 560 560 1690 560 1690 560 1690 560
    
    name down
      9000 4500 560 560 560 560 560 1690 560 560 560 560 560 560 560 560 560 560 560 1690 560 1690 560 560 560 1690 560 1690 560 1690 560 1690 560 1690 560 1690 560 560 560 560 560 1690 560 1690 560 560 560 560 560 560 560 560 560 1690 560 1690 560 560 560 560 560 1690 560 1690 560 1690 560
    
    name left
      9000 4500 560 560 560 560 560 1690 560 560 560 560 560 560 560 560 560 560 560 1690 560 1690 560 560 560 1690 560 1690 560 1690 560 1690 560 1690 560 560 560 1690 560 560 560 1690 560 1690 560 560 560 560 560 560 560 1690 560 560 560 1690 560 560 560 560 560 1690 560 1690 560 1690 560
    
    name right
      9000 4500 560 560 560 560 560 1690 560 560 560 560 560 560 560 560 560 560 560 1690 560 1690 560 560 560 1690 560 1690 560 1690 560 1690 560 1690 560 1690 560 1690 560 560 560 1690 560 1690 560 560 560 560 560 560 560 560 560 560 560 1690 560 560 560 560 560 1690 560 1690 560 1690 560
    
    name select
      9000 4500 560 560 560 560 560 1690 560 560 560 560 560 560 560 560 560 560 560 1690 560 1690 560 560 560 1690 560 1690 560 1690 560 1690 560 1690 560 1690 560 560 560 1690 560 1690 560 1690 560 560 560 560 560 560 560 560 560 1690 560 560 560 560 560 560 560 1690 560 1690 560 1690 560
    
    name back
      9000 4500 560 560 560 560 560 1690 560 560 560 560 560 560 560 560 560 560 560 1690 560 1690 560 560 560 1690 560 1690 560 1690 560 1690 560 1690 560 560 560 560 560 1690 560 1690 560 1690 560 560 560 560 560 560 560 1690 560 1690 560 560 560 560 560 560 560 1690 560 1690 560 1690 560
    
    name home
      9000 4500 560 560 560 560 560 1690 560 560 560 560 560 560 560 560 560 560 560 1690 560 1690 560 560 560 1690 560 1690 560 1690 560 1690 560 1690 560 560 560 1690 560 1690 560 560 560 560 560 560 560 560 560 560 560 1690 560 560 560 560 560 1690 560 1690 560 1690 560 1690 560 1690 560

  end raw_codes
end remote
```

**Send IR Commands**:
```bash
# Test IR
irsend SEND_ONCE roku power
irsend SEND_ONCE roku up
irsend SEND_ONCE roku select
```

## 3.6 Systemd Service for Auto-Start

Create `/etc/systemd/system/voice-bridge.service`:

```ini
[Unit]
Description=Voice Bridge Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/voice-bridge
Environment=PORCUPINE_KEY=your_key_here
Environment=BRAIN_URL=ws://192.168.1.100:8765
ExecStart=/home/pi/voice-bridge/venv/bin/python wake_word.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable voice-bridge
sudo systemctl start voice-bridge
sudo systemctl status voice-bridge
```

---

# 4. PHASE 1: THINKSTATION BACKEND SETUP

## Goal: Central AI brain handling speech recognition and Claude processing

## 4.1 Project Structure

```
/home/you/tv-brain/
├── docker-compose.yml
├── .env
├── brain/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── whisper_service.py
│   ├── claude_service.py
│   ├── orchestrator.py
│   ├── state_manager.py
│   ├── content_discovery.py
│   └── tools/
│       ├── __init__.py
│       ├── tv_control.py
│       ├── content_search.py
│       └── playback.py
├── database/
│   └── init.sql
└── config/
    └── settings.yaml
```

## 4.2 Docker Compose Setup

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  brain:
    build: ./brain
    ports:
      - "8765:8765"  # WebSocket for voice input
      - "8080:8080"  # REST API
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - TMDB_API_KEY=${TMDB_API_KEY}
      - WATCHMODE_API_KEY=${WATCHMODE_API_KEY}
      - DATABASE_URL=postgresql://brain:brain@db:5432/tvbrain
      - DELL_5070_URL=ws://192.168.1.101:9000
    volumes:
      - ./models:/app/models
      - ./config:/app/config
    depends_on:
      - db
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=brain
      - POSTGRES_PASSWORD=brain
      - POSTGRES_DB=tvbrain
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

volumes:
  pgdata:
```

## 4.3 Brain Service Implementation

Create `brain/requirements.txt`:

```
anthropic>=0.18.0
faster-whisper>=0.10.0
websockets>=12.0
fastapi>=0.109.0
uvicorn>=0.27.0
python-dotenv>=1.0.0
httpx>=0.26.0
asyncpg>=0.29.0
sqlalchemy>=2.0.0
pydantic>=2.5.0
numpy>=1.26.0
pyyaml>=6.0.0
```

Create `brain/main.py`:

```python
#!/usr/bin/env python3
"""
TV Brain - Central orchestration service
Handles voice processing, Claude AI, and TV control coordination
"""

import asyncio
import json
import logging
from typing import Optional
import websockets
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from whisper_service import WhisperService
from claude_service import ClaudeService
from orchestrator import Orchestrator
from state_manager import StateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize services
whisper = WhisperService()
claude = ClaudeService()
state = StateManager()
orchestrator = Orchestrator(whisper, claude, state)

# FastAPI app for REST endpoints
app = FastAPI(title="TV Brain API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connected clients
voice_bridges = set()
tv_platforms = set()


# ============ WebSocket Handlers ============

async def handle_voice_bridge(websocket):
    """Handle connection from Pi Zero W voice bridge"""
    voice_bridges.add(websocket)
    logger.info(f"Voice bridge connected: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            if isinstance(message, str):
                # JSON metadata
                data = json.loads(message)
                if data.get('type') == 'audio':
                    # Next message will be audio bytes
                    audio_data = await websocket.recv()
                    
                    # Process audio
                    result = await orchestrator.process_voice_command(audio_data)
                    
                    # Send response
                    await websocket.send(json.dumps(result))
            else:
                # Raw audio bytes (legacy mode)
                result = await orchestrator.process_voice_command(message)
                await websocket.send(json.dumps(result))
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("Voice bridge disconnected")
    finally:
        voice_bridges.discard(websocket)


async def handle_tv_platform(websocket):
    """Handle connection from Dell 5070 TV platform"""
    tv_platforms.add(websocket)
    logger.info(f"TV platform connected: {websocket.remote_address}")
    
    # Register with state manager
    await state.register_tv(websocket)
    
    try:
        async for message in websocket:
            data = json.loads(message)
            
            if data.get('type') == 'state_update':
                # TV is reporting its state
                await state.update_tv_state(data['state'])
            
            elif data.get('type') == 'event':
                # User interaction on TV (remote button press, etc.)
                await orchestrator.handle_tv_event(data['event'])
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("TV platform disconnected")
    finally:
        tv_platforms.discard(websocket)
        await state.unregister_tv()


async def websocket_server():
    """Run WebSocket servers for voice bridge and TV platform"""
    
    async def router(websocket, path):
        if path == "/voice":
            await handle_voice_bridge(websocket)
        elif path == "/tv":
            await handle_tv_platform(websocket)
        else:
            await websocket.close(1003, "Unknown path")
    
    async with websockets.serve(router, "0.0.0.0", 8765):
        logger.info("WebSocket server running on ws://0.0.0.0:8765")
        await asyncio.Future()  # Run forever


# ============ REST API Endpoints ============

@app.get("/health")
async def health_check():
    return {"status": "healthy", "services": {
        "whisper": whisper.is_ready(),
        "claude": claude.is_ready(),
        "tv_connected": len(tv_platforms) > 0
    }}

@app.get("/state")
async def get_state():
    return await state.get_full_state()

@app.post("/command")
async def send_command(command: dict):
    """Send a command to the TV (for testing)"""
    result = await orchestrator.execute_command(command)
    return result

@app.get("/content/search")
async def search_content(query: str, service: Optional[str] = None):
    """Search for content"""
    from content_discovery import ContentDiscovery
    discovery = ContentDiscovery()
    return await discovery.search(query, service)


# ============ Main Entry Point ============

async def main():
    """Run both WebSocket and REST servers"""
    
    # Initialize services
    await whisper.initialize()
    await claude.initialize()
    await state.initialize()
    
    # Run servers concurrently
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    
    await asyncio.gather(
        websocket_server(),
        server.serve()
    )


if __name__ == "__main__":
    asyncio.run(main())
```

## 4.4 Whisper Service

Create `brain/whisper_service.py`:

```python
"""
Speech-to-Text service using faster-whisper
"""

import io
import logging
from faster_whisper import WhisperModel
import numpy as np

logger = logging.getLogger(__name__)


class WhisperService:
    def __init__(self, model_size: str = "distil-large-v3"):
        self.model_size = model_size
        self.model = None
        
    async def initialize(self):
        """Load the Whisper model"""
        logger.info(f"Loading Whisper model: {self.model_size}")
        
        # Use GPU if available, else CPU with int8 quantization
        self.model = WhisperModel(
            self.model_size,
            device="cuda",  # or "cpu"
            compute_type="float16"  # or "int8" for CPU
        )
        
        logger.info("Whisper model loaded successfully")
    
    def is_ready(self) -> bool:
        return self.model is not None
    
    async def transcribe(self, audio_bytes: bytes) -> dict:
        """
        Transcribe audio bytes to text
        
        Args:
            audio_bytes: WAV audio data
            
        Returns:
            dict with 'text', 'confidence', 'language'
        """
        if not self.model:
            raise RuntimeError("Whisper model not initialized")
        
        # Transcribe
        segments, info = self.model.transcribe(
            io.BytesIO(audio_bytes),
            language="en",
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500
            )
        )
        
        # Combine segments
        text = " ".join([segment.text.strip() for segment in segments])
        
        # Calculate average confidence
        all_segments = list(segments)
        if all_segments:
            avg_confidence = sum(s.avg_logprob for s in all_segments) / len(all_segments)
            # Convert log probability to rough confidence score
            confidence = min(1.0, max(0.0, (avg_confidence + 1) / 1))
        else:
            confidence = 0.0
        
        result = {
            "text": text,
            "confidence": confidence,
            "language": info.language,
            "duration": info.duration
        }
        
        logger.info(f"Transcribed: '{text}' (confidence: {confidence:.2f})")
        
        return result
```

## 4.5 Claude Service with TV Tools

Create `brain/claude_service.py`:

```python
"""
Claude AI service for natural language understanding and TV control
"""

import json
import logging
from typing import Optional
import anthropic

logger = logging.getLogger(__name__)


# Tool definitions for Claude
TV_TOOLS = [
    {
        "name": "navigate",
        "description": "Navigate the TV interface. Use for directional commands, going back, going home.",
        "input_schema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "left", "right", "select", "back", "home"],
                    "description": "Navigation direction or action"
                },
                "repeat": {
                    "type": "integer",
                    "description": "Number of times to repeat the action",
                    "default": 1
                }
            },
            "required": ["direction"]
        }
    },
    {
        "name": "playback_control",
        "description": "Control media playback. Use for play, pause, stop, skip, rewind, fast forward.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["play", "pause", "stop", "skip_forward", "skip_backward", "rewind", "fast_forward"],
                    "description": "Playback action"
                },
                "seconds": {
                    "type": "integer",
                    "description": "Seconds to skip (for skip actions)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "volume_control",
        "description": "Control TV volume. Use for volume up, down, mute, unmute, or setting specific level.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["up", "down", "mute", "unmute", "set"],
                    "description": "Volume action"
                },
                "level": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Volume level (0-100) for 'set' action"
                },
                "steps": {
                    "type": "integer",
                    "description": "Number of steps for up/down",
                    "default": 1
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "power_control",
        "description": "Control TV power state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["on", "off", "toggle"],
                    "description": "Power action"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "launch_app",
        "description": "Launch a streaming app or service on the TV.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app": {
                    "type": "string",
                    "description": "App name: netflix, hulu, disney_plus, hbo_max, prime_video, youtube, spotify, etc."
                }
            },
            "required": ["app"]
        }
    },
    {
        "name": "search_content",
        "description": "Search for movies, TV shows, or other content. Use when user wants to find something to watch.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query or description (e.g., 'action movies', 'comedies from the 90s', 'Tom Hanks movies')"
                },
                "type": {
                    "type": "string",
                    "enum": ["movie", "series", "any"],
                    "description": "Content type filter",
                    "default": "any"
                },
                "service": {
                    "type": "string",
                    "description": "Limit to specific streaming service"
                },
                "genre": {
                    "type": "string",
                    "description": "Genre filter"
                },
                "year_min": {
                    "type": "integer",
                    "description": "Minimum release year"
                },
                "year_max": {
                    "type": "integer",
                    "description": "Maximum release year"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "play_content",
        "description": "Play specific content directly. Use when user names a specific movie, show, or episode.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the content"
                },
                "type": {
                    "type": "string",
                    "enum": ["movie", "series", "episode"],
                    "description": "Type of content"
                },
                "season": {
                    "type": "integer",
                    "description": "Season number (for series)"
                },
                "episode": {
                    "type": "integer",
                    "description": "Episode number (for series)"
                },
                "service": {
                    "type": "string",
                    "description": "Preferred streaming service"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "get_recommendations",
        "description": "Get personalized content recommendations. Use for 'what should I watch', 'recommend something', etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mood": {
                    "type": "string",
                    "description": "User's mood or what they're in the mood for (e.g., 'something funny', 'edge of my seat thriller')"
                },
                "similar_to": {
                    "type": "string",
                    "description": "Title to find similar content to"
                },
                "exclude_watched": {
                    "type": "boolean",
                    "description": "Exclude content user has already watched",
                    "default": True
                }
            }
        }
    },
    {
        "name": "type_text",
        "description": "Type text into the current text field (for search boxes, login forms, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to type"
                }
            },
            "required": ["text"]
        }
    }
]


class ClaudeService:
    def __init__(self):
        self.client = None
        self.conversation_history = []
        
    async def initialize(self):
        """Initialize the Claude client"""
        self.client = anthropic.Anthropic()
        logger.info("Claude service initialized")
    
    def is_ready(self) -> bool:
        return self.client is not None
    
    async def process_command(
        self,
        text: str,
        tv_state: dict,
        user_preferences: Optional[dict] = None
    ) -> dict:
        """
        Process a voice command through Claude
        
        Args:
            text: Transcribed voice command
            tv_state: Current state of the TV (app, screen, playing, etc.)
            user_preferences: User preferences and watch history
            
        Returns:
            dict with 'tools' (list of tool calls) and 'response' (spoken response)
        """
        
        # Build system prompt with context
        system_prompt = f"""You are an intelligent TV voice assistant. Your job is to understand natural language commands and control the TV.

CURRENT TV STATE:
- Power: {tv_state.get('power', 'unknown')}
- Current App: {tv_state.get('app', 'Home Screen')}
- Current Screen: {tv_state.get('screen', 'unknown')}
- Now Playing: {tv_state.get('now_playing', 'Nothing')}
- Volume: {tv_state.get('volume', 'unknown')}

USER PREFERENCES:
- Subscribed Services: {user_preferences.get('services', ['netflix', 'hulu']) if user_preferences else ['netflix', 'hulu']}
- Favorite Genres: {user_preferences.get('genres', []) if user_preferences else []}

INSTRUCTIONS:
1. Parse the user's intent from their natural language command
2. Use the appropriate tool(s) to fulfill their request
3. For ambiguous requests, make reasonable assumptions rather than asking clarifying questions
4. If the user says "that" or refers to something, check conversation history for context
5. Always provide a brief, friendly spoken response

IMPORTANT: For simple commands (pause, play, volume up), respond immediately without unnecessary words.
For content requests, be helpful and conversational.
"""

        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": text
        })
        
        # Keep only last 10 exchanges for context
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        
        # Call Claude
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            tools=TV_TOOLS,
            messages=self.conversation_history
        )
        
        # Extract tool calls and text response
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
        
        result = {
            "tools": tool_calls,
            "response": text_response,
            "stop_reason": response.stop_reason
        }
        
        logger.info(f"Claude response: {len(tool_calls)} tools, response: '{text_response[:100]}...'")
        
        return result
    
    async def get_recommendation_reasoning(
        self,
        candidates: list,
        user_request: str,
        user_preferences: dict
    ) -> dict:
        """
        Use Claude to select and explain content recommendations
        """
        prompt = f"""Based on the user's request: "{user_request}"

And their preferences:
- Favorite genres: {user_preferences.get('genres', [])}
- Recently watched: {user_preferences.get('recently_watched', [])}

Here are the available options:
{json.dumps(candidates, indent=2)}

Select the best 3-5 options and explain why each would be good for this user.
Respond with JSON:
{{
    "recommendations": [
        {{
            "title": "...",
            "service": "...",
            "reason": "One sentence explaining why this is a good pick"
        }}
    ],
    "spoken_response": "A natural, conversational summary to speak to the user (2-3 sentences max)"
}}
"""
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse JSON from response
        try:
            return json.loads(response.content[0].text)
        except json.JSONDecodeError:
            # If Claude didn't return valid JSON, extract what we can
            return {
                "recommendations": candidates[:5],
                "spoken_response": "I found some options for you. Take a look!"
            }
```

## 4.6 Orchestrator

Create `brain/orchestrator.py`:

```python
"""
Orchestrator - Coordinates voice processing, AI, and TV control
"""

import json
import logging
from typing import Optional

from whisper_service import WhisperService
from claude_service import ClaudeService
from state_manager import StateManager
from content_discovery import ContentDiscovery

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        whisper: WhisperService,
        claude: ClaudeService,
        state: StateManager
    ):
        self.whisper = whisper
        self.claude = claude
        self.state = state
        self.content = ContentDiscovery()
        
    async def process_voice_command(self, audio_bytes: bytes) -> dict:
        """
        Process a voice command from audio to action
        
        Returns dict with:
        - tts_response: Text to speak back
        - commands: List of commands to execute on TV
        - ir_command: IR command for Pi Zero (if applicable)
        - cec_command: CEC command for Pi Zero (if applicable)
        """
        
        # 1. Transcribe audio
        transcription = await self.whisper.transcribe(audio_bytes)
        text = transcription['text']
        
        if not text or transcription['confidence'] < 0.3:
            return {
                "tts_response": "Sorry, I didn't catch that. Could you repeat?",
                "commands": []
            }
        
        logger.info(f"Processing command: '{text}'")
        
        # 2. Get current TV state
        tv_state = await self.state.get_tv_state()
        user_prefs = await self.state.get_user_preferences()
        
        # 3. Process through Claude
        claude_result = await self.claude.process_command(
            text,
            tv_state,
            user_prefs
        )
        
        # 4. Execute tools and build response
        commands = []
        tts_response = claude_result['response']
        
        for tool_call in claude_result['tools']:
            tool_name = tool_call['name']
            tool_input = tool_call['input']
            
            logger.info(f"Executing tool: {tool_name} with {tool_input}")
            
            if tool_name == 'navigate':
                commands.append({
                    "type": "navigate",
                    "direction": tool_input['direction'],
                    "repeat": tool_input.get('repeat', 1)
                })
                
            elif tool_name == 'playback_control':
                commands.append({
                    "type": "playback",
                    "action": tool_input['action'],
                    "seconds": tool_input.get('seconds')
                })
                
            elif tool_name == 'volume_control':
                commands.append({
                    "type": "volume",
                    "action": tool_input['action'],
                    "level": tool_input.get('level'),
                    "steps": tool_input.get('steps', 1)
                })
                
            elif tool_name == 'power_control':
                commands.append({
                    "type": "power",
                    "action": tool_input['action']
                })
                
            elif tool_name == 'launch_app':
                commands.append({
                    "type": "launch_app",
                    "app": tool_input['app']
                })
                
            elif tool_name == 'search_content':
                # Search for content
                results = await self.content.search(
                    query=tool_input['query'],
                    content_type=tool_input.get('type', 'any'),
                    service=tool_input.get('service'),
                    genre=tool_input.get('genre')
                )
                
                if results:
                    # Get Claude to pick best matches
                    recommendations = await self.claude.get_recommendation_reasoning(
                        results[:20],
                        text,
                        user_prefs
                    )
                    
                    commands.append({
                        "type": "show_results",
                        "results": recommendations['recommendations']
                    })
                    tts_response = recommendations['spoken_response']
                else:
                    tts_response = f"I couldn't find anything matching '{tool_input['query']}'"
                    
            elif tool_name == 'play_content':
                # Find and play specific content
                content = await self.content.find_specific(
                    title=tool_input['title'],
                    content_type=tool_input.get('type'),
                    service=tool_input.get('service')
                )
                
                if content:
                    commands.append({
                        "type": "play",
                        "content": content
                    })
                    tts_response = f"Playing {content['title']} on {content['service']}"
                else:
                    tts_response = f"I couldn't find '{tool_input['title']}' on your streaming services"
                    
            elif tool_name == 'type_text':
                commands.append({
                    "type": "type_text",
                    "text": tool_input['text']
                })
                
            elif tool_name == 'get_recommendations':
                # Get personalized recommendations
                results = await self.content.get_recommendations(
                    mood=tool_input.get('mood'),
                    similar_to=tool_input.get('similar_to'),
                    user_prefs=user_prefs
                )
                
                if results:
                    recommendations = await self.claude.get_recommendation_reasoning(
                        results[:20],
                        text,
                        user_prefs
                    )
                    
                    commands.append({
                        "type": "show_results",
                        "results": recommendations['recommendations']
                    })
                    tts_response = recommendations['spoken_response']
        
        # 5. Send commands to TV
        if commands:
            await self.state.send_commands_to_tv(commands)
        
        return {
            "tts_response": tts_response,
            "commands": commands,
            "transcription": text
        }
    
    async def execute_command(self, command: dict) -> dict:
        """Execute a single command (for REST API testing)"""
        await self.state.send_commands_to_tv([command])
        return {"status": "sent", "command": command}
    
    async def handle_tv_event(self, event: dict):
        """Handle events from the TV (remote button press, etc.)"""
        event_type = event.get('type')
        
        if event_type == 'voice_button':
            # User pressed voice button on remote
            # Signal Pi Zero to start listening
            pass
        
        elif event_type == 'content_selected':
            # User selected content on screen
            await self.state.update_watch_history(event['content'])
```

## 4.7 Content Discovery Service

Create `brain/content_discovery.py`:

```python
"""
Content discovery using TMDB and Watchmode APIs
"""

import os
import logging
from typing import Optional, List
import httpx

logger = logging.getLogger(__name__)

TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
TMDB_BASE_URL = "https://api.themoviedb.org/3"

WATCHMODE_API_KEY = os.environ.get('WATCHMODE_API_KEY')
WATCHMODE_BASE_URL = "https://api.watchmode.com/v1"

# App IDs for streaming services (varies by platform)
STREAMING_SERVICES = {
    "netflix": {"tmdb_id": 8, "name": "Netflix"},
    "prime_video": {"tmdb_id": 9, "name": "Amazon Prime Video"},
    "disney_plus": {"tmdb_id": 337, "name": "Disney+"},
    "hulu": {"tmdb_id": 15, "name": "Hulu"},
    "hbo_max": {"tmdb_id": 384, "name": "Max"},
    "apple_tv": {"tmdb_id": 350, "name": "Apple TV+"},
    "paramount": {"tmdb_id": 531, "name": "Paramount+"},
    "peacock": {"tmdb_id": 386, "name": "Peacock"},
}

GENRE_MAP = {
    "action": 28,
    "comedy": 35,
    "drama": 18,
    "horror": 27,
    "thriller": 53,
    "sci-fi": 878,
    "romance": 10749,
    "documentary": 99,
    "animation": 16,
    "family": 10751,
    "fantasy": 14,
    "crime": 80,
    "mystery": 9648,
}


class ContentDiscovery:
    def __init__(self):
        self.http = httpx.AsyncClient(timeout=30.0)
        
    async def search(
        self,
        query: str,
        content_type: str = "any",
        service: Optional[str] = None,
        genre: Optional[str] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None
    ) -> List[dict]:
        """
        Search for content across streaming services
        """
        results = []
        
        # Search TMDB
        if content_type in ["movie", "any"]:
            movies = await self._search_tmdb_movies(query, genre, year_min, year_max)
            results.extend(movies)
            
        if content_type in ["series", "any"]:
            shows = await self._search_tmdb_shows(query, genre, year_min, year_max)
            results.extend(shows)
        
        # Filter by streaming service if specified
        if service:
            results = await self._filter_by_service(results, service)
        else:
            # Get availability for all results
            results = await self._add_availability(results)
        
        # Sort by popularity
        results.sort(key=lambda x: x.get('popularity', 0), reverse=True)
        
        return results[:50]
    
    async def _search_tmdb_movies(
        self,
        query: str,
        genre: Optional[str],
        year_min: Optional[int],
        year_max: Optional[int]
    ) -> List[dict]:
        """Search TMDB for movies"""
        params = {
            "api_key": TMDB_API_KEY,
            "query": query,
            "include_adult": False
        }
        
        response = await self.http.get(
            f"{TMDB_BASE_URL}/search/movie",
            params=params
        )
        
        if response.status_code != 200:
            logger.error(f"TMDB search failed: {response.status_code}")
            return []
        
        data = response.json()
        
        results = []
        for movie in data.get('results', []):
            # Filter by year if specified
            release_year = int(movie.get('release_date', '0000')[:4] or 0)
            if year_min and release_year < year_min:
                continue
            if year_max and release_year > year_max:
                continue
            
            results.append({
                "id": movie['id'],
                "title": movie['title'],
                "type": "movie",
                "year": release_year,
                "overview": movie.get('overview', ''),
                "rating": movie.get('vote_average', 0),
                "popularity": movie.get('popularity', 0),
                "poster": f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie.get('poster_path') else None,
                "tmdb_id": movie['id']
            })
        
        return results
    
    async def _search_tmdb_shows(
        self,
        query: str,
        genre: Optional[str],
        year_min: Optional[int],
        year_max: Optional[int]
    ) -> List[dict]:
        """Search TMDB for TV shows"""
        params = {
            "api_key": TMDB_API_KEY,
            "query": query
        }
        
        response = await self.http.get(
            f"{TMDB_BASE_URL}/search/tv",
            params=params
        )
        
        if response.status_code != 200:
            logger.error(f"TMDB search failed: {response.status_code}")
            return []
        
        data = response.json()
        
        results = []
        for show in data.get('results', []):
            first_air_year = int(show.get('first_air_date', '0000')[:4] or 0)
            if year_min and first_air_year < year_min:
                continue
            if year_max and first_air_year > year_max:
                continue
            
            results.append({
                "id": show['id'],
                "title": show['name'],
                "type": "series",
                "year": first_air_year,
                "overview": show.get('overview', ''),
                "rating": show.get('vote_average', 0),
                "popularity": show.get('popularity', 0),
                "poster": f"https://image.tmdb.org/t/p/w500{show['poster_path']}" if show.get('poster_path') else None,
                "tmdb_id": show['id']
            })
        
        return results
    
    async def _add_availability(self, results: List[dict]) -> List[dict]:
        """Add streaming availability to results using TMDB watch providers"""
        for item in results[:20]:  # Limit API calls
            content_type = "movie" if item['type'] == "movie" else "tv"
            
            response = await self.http.get(
                f"{TMDB_BASE_URL}/{content_type}/{item['tmdb_id']}/watch/providers",
                params={"api_key": TMDB_API_KEY}
            )
            
            if response.status_code == 200:
                data = response.json()
                us_providers = data.get('results', {}).get('US', {})
                
                # Get flatrate (subscription) providers
                flatrate = us_providers.get('flatrate', [])
                item['services'] = [p['provider_name'] for p in flatrate]
                
                # Get deep link if available
                item['watch_link'] = us_providers.get('link')
        
        return results
    
    async def _filter_by_service(
        self,
        results: List[dict],
        service: str
    ) -> List[dict]:
        """Filter results to only show content on a specific service"""
        # First add availability
        results = await self._add_availability(results)
        
        # Filter
        service_name = STREAMING_SERVICES.get(service, {}).get('name', service)
        
        return [
            r for r in results
            if any(service_name.lower() in s.lower() for s in r.get('services', []))
        ]
    
    async def find_specific(
        self,
        title: str,
        content_type: Optional[str] = None,
        service: Optional[str] = None
    ) -> Optional[dict]:
        """Find a specific title"""
        results = await self.search(
            query=title,
            content_type=content_type or "any",
            service=service
        )
        
        if results:
            # Return best match
            return results[0]
        
        return None
    
    async def get_recommendations(
        self,
        mood: Optional[str] = None,
        similar_to: Optional[str] = None,
        user_prefs: Optional[dict] = None
    ) -> List[dict]:
        """Get content recommendations"""
        
        if similar_to:
            # Find similar content
            base = await self.find_specific(similar_to)
            if base:
                content_type = "movie" if base['type'] == "movie" else "tv"
                response = await self.http.get(
                    f"{TMDB_BASE_URL}/{content_type}/{base['tmdb_id']}/recommendations",
                    params={"api_key": TMDB_API_KEY}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Process similar to search results
                    return await self._add_availability([
                        {
                            "id": r['id'],
                            "title": r.get('title') or r.get('name'),
                            "type": base['type'],
                            "year": int((r.get('release_date') or r.get('first_air_date') or '0000')[:4]),
                            "overview": r.get('overview', ''),
                            "rating": r.get('vote_average', 0),
                            "popularity": r.get('popularity', 0),
                            "poster": f"https://image.tmdb.org/t/p/w500{r['poster_path']}" if r.get('poster_path') else None,
                            "tmdb_id": r['id']
                        }
                        for r in data.get('results', [])[:20]
                    ])
        
        # Discover based on mood/genre
        if mood:
            # Map mood to genre
            mood_genre_map = {
                "funny": "comedy",
                "scary": "horror",
                "exciting": "action",
                "romantic": "romance",
                "thought-provoking": "drama",
                "thrilling": "thriller",
                "adventurous": "fantasy"
            }
            genre = mood_genre_map.get(mood.lower())
            if genre:
                return await self._discover_by_genre(genre, user_prefs)
        
        # Default: popular content
        return await self._discover_popular(user_prefs)
    
    async def _discover_by_genre(
        self,
        genre: str,
        user_prefs: Optional[dict] = None
    ) -> List[dict]:
        """Discover content by genre"""
        genre_id = GENRE_MAP.get(genre)
        if not genre_id:
            return []
        
        params = {
            "api_key": TMDB_API_KEY,
            "with_genres": genre_id,
            "sort_by": "popularity.desc",
            "vote_count.gte": 100
        }
        
        # Add streaming service filter if user has preferences
        if user_prefs and user_prefs.get('services'):
            provider_ids = [
                STREAMING_SERVICES[s]['tmdb_id']
                for s in user_prefs['services']
                if s in STREAMING_SERVICES
            ]
            if provider_ids:
                params['with_watch_providers'] = '|'.join(map(str, provider_ids))
                params['watch_region'] = 'US'
        
        response = await self.http.get(
            f"{TMDB_BASE_URL}/discover/movie",
            params=params
        )
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        
        return await self._add_availability([
            {
                "id": m['id'],
                "title": m['title'],
                "type": "movie",
                "year": int(m.get('release_date', '0000')[:4] or 0),
                "overview": m.get('overview', ''),
                "rating": m.get('vote_average', 0),
                "popularity": m.get('popularity', 0),
                "poster": f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else None,
                "tmdb_id": m['id']
            }
            for m in data.get('results', [])[:20]
        ])
    
    async def _discover_popular(
        self,
        user_prefs: Optional[dict] = None
    ) -> List[dict]:
        """Get popular content"""
        response = await self.http.get(
            f"{TMDB_BASE_URL}/trending/all/week",
            params={"api_key": TMDB_API_KEY}
        )
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        
        return await self._add_availability([
            {
                "id": r['id'],
                "title": r.get('title') or r.get('name'),
                "type": "movie" if r.get('media_type') == 'movie' else "series",
                "year": int((r.get('release_date') or r.get('first_air_date') or '0000')[:4]),
                "overview": r.get('overview', ''),
                "rating": r.get('vote_average', 0),
                "popularity": r.get('popularity', 0),
                "poster": f"https://image.tmdb.org/t/p/w500{r['poster_path']}" if r.get('poster_path') else None,
                "tmdb_id": r['id']
            }
            for r in data.get('results', [])[:20]
        ])
```

---

# 5. PHASE 2: DELL 5070 TV PLATFORM

## Goal: Custom Linux-based TV interface with streaming capability

## 5.1 Initial OS Setup

```bash
# Download Ubuntu Server 24.04 LTS (minimal)
# Flash to USB drive and boot Dell 5070

# During installation:
# - Minimal installation
# - Install OpenSSH server
# - Username: tv
# - Hostname: tv-platform

# After installation, SSH in:
ssh tv@192.168.1.101

# Update system
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y \
    git \
    curl \
    wget \
    build-essential \
    python3-pip \
    python3-venv \
    chromium-browser \
    chromium-codecs-ffmpeg-extra \
    vainfo \
    intel-media-va-driver \
    libva-drm2 \
    mesa-va-drivers \
    pulseaudio \
    alsa-utils \
    xorg \
    cage \
    libcec6 \
    cec-utils \
    nodejs \
    npm
```

## 5.2 Install Widevine for DRM Streaming

```bash
# For Chromium DRM support, need to install Widevine CDM
# This enables Netflix, Disney+, etc. (at 720p-1080p max)

# Create directory for CDM
mkdir -p ~/.local/lib/chromium

# Download and extract Widevine
# (Google Chrome version includes it, we can borrow it)
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
dpkg-deb -x google-chrome-stable_current_amd64.deb chrome-extracted
cp -r chrome-extracted/opt/google/chrome/WidevineCdm ~/.local/lib/chromium/
rm -rf chrome-extracted google-chrome-stable_current_amd64.deb

# Verify Widevine installation
ls ~/.local/lib/chromium/WidevineCdm/
```

## 5.3 CEC Setup for TV Remote Control

```bash
# Install Pulse-Eight USB-CEC adapter support
sudo apt install -y libcec6 cec-utils python3-cec

# Test CEC connection
cec-client -l  # List adapters
echo 'scan' | cec-client -s -d 1  # Scan CEC bus

# Create CEC input handler script
mkdir -p ~/tv-platform
```

Create `~/tv-platform/cec_handler.py`:

```python
#!/usr/bin/env python3
"""
CEC remote control handler
Converts CEC button presses to WebSocket messages
"""

import cec
import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CEC button code to action mapping
BUTTON_MAP = {
    0x00: "select",      # Select
    0x01: "up",          # Up
    0x02: "down",        # Down
    0x03: "left",        # Left
    0x04: "right",       # Right
    0x09: "menu",        # Menu
    0x0D: "back",        # Back/Exit
    0x44: "play",        # Play
    0x45: "pause",       # Pause
    0x46: "stop",        # Stop
    0x48: "rewind",      # Rewind
    0x49: "fast_forward", # Fast Forward
    0x41: "volume_up",   # Volume Up
    0x42: "volume_down", # Volume Down
    0x43: "mute",        # Mute
}


class CECHandler:
    def __init__(self, brain_url: str = "ws://192.168.1.100:8765/tv"):
        self.brain_url = brain_url
        self.websocket = None
        self.cec_adapter = None
        
    def cec_callback(self, event, data):
        """Handle CEC events"""
        if event == cec.EVENT_KEYPRESS:
            key_code = data['key']
            duration = data.get('duration', 0)
            
            action = BUTTON_MAP.get(key_code)
            if action:
                logger.info(f"Button press: {action} (code: {key_code})")
                asyncio.create_task(self.send_button_event(action))
                
    async def send_button_event(self, action: str):
        """Send button event to brain"""
        if self.websocket:
            try:
                await self.websocket.send(json.dumps({
                    "type": "remote_button",
                    "action": action
                }))
            except Exception as e:
                logger.error(f"Failed to send button event: {e}")
    
    async def connect_brain(self):
        """Maintain connection to brain service"""
        while True:
            try:
                async with websockets.connect(self.brain_url) as ws:
                    self.websocket = ws
                    logger.info(f"Connected to brain at {self.brain_url}")
                    
                    async for message in ws:
                        # Handle commands from brain
                        data = json.loads(message)
                        await self.handle_brain_command(data)
                        
            except Exception as e:
                logger.error(f"Brain connection error: {e}")
                await asyncio.sleep(5)  # Reconnect after delay
    
    async def handle_brain_command(self, data: dict):
        """Handle command from brain service"""
        command_type = data.get('type')
        
        if command_type == 'cec':
            # Send CEC command to TV
            action = data.get('action')
            if action == 'power_on':
                self.cec_adapter.PowerOnDevices()
            elif action == 'power_off':
                self.cec_adapter.StandbyDevices()
            elif action == 'volume_up':
                self.cec_adapter.VolumeUp()
            elif action == 'volume_down':
                self.cec_adapter.VolumeDown()
            elif action == 'mute':
                self.cec_adapter.AudioToggleMute()
    
    async def start(self):
        """Initialize CEC and start handling"""
        # Initialize CEC
        cec.init()
        self.cec_adapter = cec.Device(cec.CECDEVICE_TV)
        
        # Set callback
        cec.set_cec_callback(self.cec_callback)
        
        # Become active source
        cec.set_active_source()
        
        logger.info("CEC handler started")
        
        # Connect to brain
        await self.connect_brain()


async def main():
    handler = CECHandler()
    await handler.start()


if __name__ == "__main__":
    asyncio.run(main())
```

## 5.4 Cage Wayland Kiosk Setup

```bash
# Create startup script
cat > ~/tv-platform/start-tv.sh << 'EOF'
#!/bin/bash

# Start PulseAudio
pulseaudio --start

# Start CEC handler in background
python3 ~/tv-platform/cec_handler.py &

# Start TV UI in Cage (Wayland kiosk)
cage -- chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --enable-features=VaapiVideoDecoder \
    --ignore-gpu-blocklist \
    --enable-gpu-rasterization \
    --enable-zero-copy \
    --user-data-dir=/home/tv/.config/chromium-tv \
    http://localhost:3000

EOF
chmod +x ~/tv-platform/start-tv.sh
```

## 5.5 Auto-Login and Auto-Start

```bash
# Enable auto-login
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d/
sudo cat > /etc/systemd/system/getty@tty1.service.d/override.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin tv --noclear %I \$TERM
EOF

# Add to .profile for auto-start
echo '[ -z "$DISPLAY" ] && [ $(tty) = /dev/tty1 ] && ~/tv-platform/start-tv.sh' >> ~/.profile
```

---

# 6. PHASE 3: CUSTOM TV UI DEVELOPMENT

## Goal: Build React-based 10-foot TV interface

## 6.1 Project Setup

```bash
# On your development machine (or Dell 5070)
mkdir -p ~/tv-ui
cd ~/tv-ui

# Initialize React project with Vite
npm create vite@latest . -- --template react-ts
npm install

# Install TV-specific dependencies
npm install @norigin/spatial-navigation
npm install framer-motion
npm install axios
npm install zustand  # State management
```

## 6.2 Project Structure

```
tv-ui/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── index.css
│   ├── components/
│   │   ├── Layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── VoiceIndicator.tsx
│   │   ├── Content/
│   │   │   ├── ContentRow.tsx
│   │   │   ├── ContentCard.tsx
│   │   │   ├── ContentDetails.tsx
│   │   │   └── SearchResults.tsx
│   │   ├── Apps/
│   │   │   ├── AppGrid.tsx
│   │   │   ├── AppLauncher.tsx
│   │   │   └── StreamingApp.tsx
│   │   └── Common/
│   │       ├── FocusableButton.tsx
│   │       └── LoadingSpinner.tsx
│   ├── hooks/
│   │   ├── useVoiceConnection.ts
│   │   ├── useTVState.ts
│   │   └── useContent.ts
│   ├── services/
│   │   ├── api.ts
│   │   ├── websocket.ts
│   │   └── cec.ts
│   ├── store/
│   │   └── index.ts
│   └── styles/
│       └── tv-theme.css
├── package.json
├── vite.config.ts
└── tsconfig.json
```

## 6.3 Main App with Spatial Navigation

Create `src/App.tsx`:

```tsx
import { useEffect, useCallback } from 'react';
import {
  init,
  useFocusable,
  FocusContext,
} from '@norigin/spatial-navigation';
import { Sidebar } from './components/Layout/Sidebar';
import { ContentRow } from './components/Content/ContentRow';
import { VoiceIndicator } from './components/Layout/VoiceIndicator';
import { useVoiceConnection } from './hooks/useVoiceConnection';
import { useTVState } from './hooks/useTVState';
import './styles/tv-theme.css';

// Initialize spatial navigation
init({
  debug: false,
  visualDebug: false,
});

function App() {
  const { ref, focusKey, focusSelf } = useFocusable();
  const { isListening, lastCommand } = useVoiceConnection();
  const { 
    continueWatching, 
    recommendations, 
    trendingNow,
    selectedCategory 
  } = useTVState();

  useEffect(() => {
    focusSelf();
  }, [focusSelf]);

  // Handle keyboard/remote input
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Map keyboard to spatial navigation
      // Arrow keys are handled automatically
      
      if (e.key === 'Enter') {
        // Select current focused item
      } else if (e.key === 'Escape' || e.key === 'Backspace') {
        // Go back
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <FocusContext.Provider value={focusKey}>
      <div ref={ref} className="tv-app">
        {/* Voice listening indicator */}
        <VoiceIndicator isListening={isListening} lastCommand={lastCommand} />
        
        {/* Sidebar navigation */}
        <Sidebar />
        
        {/* Main content area */}
        <main className="main-content">
          {/* Continue Watching row */}
          {continueWatching.length > 0 && (
            <ContentRow 
              title="Continue Watching" 
              items={continueWatching}
              focusKey="continue-watching"
            />
          )}
          
          {/* For You recommendations */}
          <ContentRow 
            title="Recommended For You" 
            items={recommendations}
            focusKey="recommendations"
          />
          
          {/* Trending */}
          <ContentRow 
            title="Trending Now" 
            items={trendingNow}
            focusKey="trending"
          />
        </main>
      </div>
    </FocusContext.Provider>
  );
}

export default App;
```

## 6.4 Content Row Component

Create `src/components/Content/ContentRow.tsx`:

```tsx
import { useFocusable, FocusContext } from '@norigin/spatial-navigation';
import { motion } from 'framer-motion';
import { ContentCard } from './ContentCard';

interface ContentItem {
  id: string;
  title: string;
  poster: string;
  type: 'movie' | 'series';
  year: number;
  rating: number;
  services: string[];
}

interface ContentRowProps {
  title: string;
  items: ContentItem[];
  focusKey: string;
}

export function ContentRow({ title, items, focusKey }: ContentRowProps) {
  const { ref, focusKey: rowFocusKey } = useFocusable({
    focusKey,
    saveLastFocusedChild: true,
    trackChildren: true,
  });

  return (
    <FocusContext.Provider value={rowFocusKey}>
      <div className="content-row">
        <h2 className="row-title">{title}</h2>
        
        <motion.div 
          ref={ref} 
          className="row-items"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          {items.map((item, index) => (
            <ContentCard
              key={item.id}
              item={item}
              index={index}
            />
          ))}
        </motion.div>
      </div>
    </FocusContext.Provider>
  );
}
```

## 6.5 Focusable Content Card

Create `src/components/Content/ContentCard.tsx`:

```tsx
import { useCallback } from 'react';
import { useFocusable } from '@norigin/spatial-navigation';
import { motion } from 'framer-motion';

interface ContentItem {
  id: string;
  title: string;
  poster: string;
  type: 'movie' | 'series';
  year: number;
  rating: number;
  services: string[];
}

interface ContentCardProps {
  item: ContentItem;
  index: number;
}

export function ContentCard({ item, index }: ContentCardProps) {
  const handleSelect = useCallback(() => {
    console.log('Selected:', item.title);
    // Navigate to content details or start playback
  }, [item]);

  const { ref, focused } = useFocusable({
    onEnterPress: handleSelect,
  });

  return (
    <motion.div
      ref={ref}
      className={`content-card ${focused ? 'focused' : ''}`}
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ 
        opacity: 1, 
        scale: focused ? 1.1 : 1,
        zIndex: focused ? 10 : 1
      }}
      transition={{ duration: 0.2 }}
      whileHover={{ scale: 1.05 }}
    >
      <div className="card-poster">
        <img src={item.poster} alt={item.title} />
        
        {/* Service badges */}
        <div className="service-badges">
          {item.services.slice(0, 2).map(service => (
            <span key={service} className={`badge ${service.toLowerCase()}`}>
              {service}
            </span>
          ))}
        </div>
      </div>
      
      <div className="card-info">
        <h3 className="card-title">{item.title}</h3>
        <div className="card-meta">
          <span className="year">{item.year}</span>
          <span className="rating">★ {item.rating.toFixed(1)}</span>
        </div>
      </div>
      
      {/* Focus ring */}
      {focused && <div className="focus-ring" />}
    </motion.div>
  );
}
```

## 6.6 Voice Connection Hook

Create `src/hooks/useVoiceConnection.ts`:

```tsx
import { useState, useEffect, useCallback } from 'react';
import { useStore } from '../store';

const BRAIN_WS_URL = import.meta.env.VITE_BRAIN_WS_URL || 'ws://192.168.1.100:8765/tv';

export function useVoiceConnection() {
  const [isConnected, setIsConnected] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [lastCommand, setLastCommand] = useState<string | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);
  
  const { 
    setSearchResults, 
    navigateTo,
    updateVolume,
    setPlaybackState 
  } = useStore();

  const connect = useCallback(() => {
    const socket = new WebSocket(BRAIN_WS_URL);
    
    socket.onopen = () => {
      console.log('Connected to Brain');
      setIsConnected(true);
      
      // Send initial state
      socket.send(JSON.stringify({
        type: 'state_update',
        state: {
          app: 'home',
          screen: 'main',
          power: 'on'
        }
      }));
    };
    
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleBrainMessage(data);
    };
    
    socket.onclose = () => {
      console.log('Disconnected from Brain');
      setIsConnected(false);
      // Reconnect after delay
      setTimeout(connect, 5000);
    };
    
    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    setWs(socket);
  }, []);

  const handleBrainMessage = useCallback((data: any) => {
    const { type, ...payload } = data;
    
    switch (type) {
      case 'voice_active':
        setIsListening(payload.active);
        break;
        
      case 'transcription':
        setLastCommand(payload.text);
        break;
        
      case 'command':
        executeCommand(payload);
        break;
        
      case 'show_results':
        setSearchResults(payload.results);
        navigateTo('search_results');
        break;
        
      case 'tts_start':
        // Show speaking indicator
        break;
        
      case 'tts_end':
        // Hide speaking indicator
        setLastCommand(null);
        break;
    }
  }, [setSearchResults, navigateTo]);

  const executeCommand = useCallback((command: any) => {
    switch (command.type) {
      case 'navigate':
        // Trigger spatial navigation programmatically
        const keyMap: Record<string, string> = {
          up: 'ArrowUp',
          down: 'ArrowDown',
          left: 'ArrowLeft',
          right: 'ArrowRight',
          select: 'Enter',
          back: 'Escape'
        };
        
        const key = keyMap[command.direction];
        if (key) {
          for (let i = 0; i < (command.repeat || 1); i++) {
            window.dispatchEvent(new KeyboardEvent('keydown', { key }));
          }
        }
        break;
        
      case 'launch_app':
        navigateTo('app', { app: command.app });
        break;
        
      case 'play':
        navigateTo('player', { content: command.content });
        break;
        
      case 'playback':
        setPlaybackState(command.action);
        break;
        
      case 'volume':
        updateVolume(command.action, command.level, command.steps);
        break;
        
      case 'type_text':
        // Type into focused text field
        const input = document.activeElement as HTMLInputElement;
        if (input && input.tagName === 'INPUT') {
          input.value = command.text;
          input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        break;
    }
  }, [navigateTo, setPlaybackState, updateVolume]);

  const sendState = useCallback((state: any) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'state_update',
        state
      }));
    }
  }, [ws]);

  useEffect(() => {
    connect();
    return () => {
      ws?.close();
    };
  }, [connect]);

  return {
    isConnected,
    isListening,
    lastCommand,
    sendState
  };
}
```

## 6.7 TV Theme CSS

Create `src/styles/tv-theme.css`:

```css
/* TV-optimized theme */

:root {
  /* Colors */
  --bg-primary: #0a0a0a;
  --bg-secondary: #1a1a1a;
  --bg-card: #252525;
  --text-primary: #ffffff;
  --text-secondary: #aaaaaa;
  --accent: #e50914; /* Netflix red - change to your brand */
  --focus-ring: #ffffff;
  
  /* Spacing */
  --spacing-xs: 8px;
  --spacing-sm: 16px;
  --spacing-md: 24px;
  --spacing-lg: 32px;
  --spacing-xl: 48px;
  
  /* Typography - large for TV viewing distance */
  --font-size-xs: 18px;
  --font-size-sm: 22px;
  --font-size-md: 28px;
  --font-size-lg: 36px;
  --font-size-xl: 48px;
  --font-size-xxl: 64px;
  
  /* Card sizes */
  --card-width: 200px;
  --card-height: 300px;
  --card-gap: 20px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  overflow: hidden;
  cursor: none; /* Hide cursor on TV */
}

.tv-app {
  display: flex;
  width: 100vw;
  height: 100vh;
}

/* Sidebar */
.sidebar {
  width: 80px;
  height: 100vh;
  background: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-md) 0;
  transition: width 0.3s ease;
}

.sidebar.expanded {
  width: 280px;
}

.sidebar-item {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  margin-bottom: var(--spacing-sm);
  transition: all 0.2s ease;
}

.sidebar-item.focused {
  background: var(--accent);
  transform: scale(1.1);
}

/* Main content */
.main-content {
  flex: 1;
  padding: var(--spacing-lg);
  overflow-y: auto;
  overflow-x: hidden;
}

/* Content rows */
.content-row {
  margin-bottom: var(--spacing-xl);
}

.row-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  margin-bottom: var(--spacing-md);
  padding-left: var(--spacing-sm);
}

.row-items {
  display: flex;
  gap: var(--card-gap);
  overflow-x: auto;
  padding: var(--spacing-sm);
  scroll-behavior: smooth;
}

.row-items::-webkit-scrollbar {
  display: none;
}

/* Content cards */
.content-card {
  flex-shrink: 0;
  width: var(--card-width);
  border-radius: 12px;
  overflow: hidden;
  background: var(--bg-card);
  transition: all 0.2s ease;
  position: relative;
}

.content-card.focused {
  box-shadow: 0 0 0 4px var(--focus-ring);
}

.card-poster {
  width: 100%;
  height: var(--card-height);
  position: relative;
}

.card-poster img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.service-badges {
  position: absolute;
  bottom: var(--spacing-xs);
  left: var(--spacing-xs);
  display: flex;
  gap: 4px;
}

.badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(0, 0, 0, 0.7);
}

.badge.netflix { background: #e50914; }
.badge.hulu { background: #1ce783; color: black; }
.badge.disney { background: #113ccf; }
.badge.prime { background: #00a8e1; }
.badge.hbo { background: #b103fc; }

.card-info {
  padding: var(--spacing-sm);
}

.card-title {
  font-size: var(--font-size-sm);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-meta {
  display: flex;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-xs);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

/* Focus ring animation */
.focus-ring {
  position: absolute;
  inset: -4px;
  border: 4px solid var(--focus-ring);
  border-radius: 16px;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Voice indicator */
.voice-indicator {
  position: fixed;
  top: var(--spacing-lg);
  right: var(--spacing-lg);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: rgba(0, 0, 0, 0.8);
  border-radius: 50px;
  z-index: 1000;
  opacity: 0;
  transform: translateY(-20px);
  transition: all 0.3s ease;
}

.voice-indicator.active {
  opacity: 1;
  transform: translateY(0);
}

.voice-indicator.listening {
  background: var(--accent);
}

.voice-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--text-primary);
}

.voice-indicator.listening .voice-dot {
  animation: voice-pulse 0.5s infinite;
}

@keyframes voice-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.3); }
}

.voice-text {
  font-size: var(--font-size-sm);
}
```

---

# 7. PHASE 4: VOICE PIPELINE INTEGRATION

## Full voice pipeline connecting all components

## 7.1 Voice Indicator Component

Create `src/components/Layout/VoiceIndicator.tsx`:

```tsx
import { motion, AnimatePresence } from 'framer-motion';

interface VoiceIndicatorProps {
  isListening: boolean;
  lastCommand: string | null;
}

export function VoiceIndicator({ isListening, lastCommand }: VoiceIndicatorProps) {
  return (
    <AnimatePresence>
      {(isListening || lastCommand) && (
        <motion.div
          className={`voice-indicator ${isListening ? 'listening' : ''} active`}
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
        >
          <div className="voice-dot" />
          <span className="voice-text">
            {isListening 
              ? 'Listening...' 
              : lastCommand || ''
            }
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

## 7.2 TTS Integration on Pi Zero W

Add to `~/voice-bridge/tts_service.py`:

```python
#!/usr/bin/env python3
"""
Text-to-Speech service using Piper
"""

import subprocess
import tempfile
import os

# Download Piper model
# wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz
# wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx

PIPER_PATH = "/home/pi/piper/piper"
MODEL_PATH = "/home/pi/piper/models/en_US-lessac-medium.onnx"


def speak(text: str):
    """Speak text using Piper TTS"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        temp_file = f.name
    
    try:
        # Generate speech
        subprocess.run([
            PIPER_PATH,
            "--model", MODEL_PATH,
            "--output_file", temp_file
        ], input=text.encode(), check=True)
        
        # Play audio
        subprocess.run(["aplay", temp_file], check=True)
        
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)


if __name__ == "__main__":
    speak("Hello! I'm your TV assistant. How can I help you today?")
```

---

# 8. PHASE 5: CONTENT DISCOVERY & RECOMMENDATIONS

## Already covered in Phase 1 (content_discovery.py)

Additional enhancement - user preferences storage:

## 8.1 State Manager with User Preferences

Create `brain/state_manager.py`:

```python
"""
State manager for TV platform
Handles TV state, user preferences, and watch history
"""

import json
import logging
from typing import Optional, Dict, List
from datetime import datetime
import asyncpg

logger = logging.getLogger(__name__)


class StateManager:
    def __init__(self):
        self.db_pool = None
        self.tv_websocket = None
        self.current_tv_state = {
            "power": "off",
            "app": None,
            "screen": "home",
            "volume": 50,
            "now_playing": None
        }
        
    async def initialize(self):
        """Initialize database connection"""
        self.db_pool = await asyncpg.create_pool(
            "postgresql://brain:brain@db:5432/tvbrain"
        )
        logger.info("State manager initialized")
    
    async def register_tv(self, websocket):
        """Register TV platform connection"""
        self.tv_websocket = websocket
        self.current_tv_state["power"] = "on"
        logger.info("TV platform registered")
    
    async def unregister_tv(self):
        """Unregister TV platform"""
        self.tv_websocket = None
        self.current_tv_state["power"] = "off"
    
    async def update_tv_state(self, state: dict):
        """Update current TV state"""
        self.current_tv_state.update(state)
        logger.debug(f"TV state updated: {self.current_tv_state}")
    
    async def get_tv_state(self) -> dict:
        """Get current TV state"""
        return self.current_tv_state.copy()
    
    async def send_commands_to_tv(self, commands: List[dict]):
        """Send commands to TV platform"""
        if not self.tv_websocket:
            logger.warning("No TV connected, cannot send commands")
            return
        
        for command in commands:
            await self.tv_websocket.send(json.dumps({
                "type": "command",
                **command
            }))
            logger.info(f"Sent command to TV: {command['type']}")
    
    async def get_user_preferences(self, user_id: str = "default") -> dict:
        """Get user preferences"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_preferences WHERE user_id = $1",
                user_id
            )
            
            if row:
                return {
                    "services": row['subscribed_services'] or [],
                    "genres": row['favorite_genres'] or [],
                    "recently_watched": await self.get_watch_history(user_id, limit=20)
                }
            
            return {
                "services": ["netflix", "hulu", "disney_plus"],
                "genres": [],
                "recently_watched": []
            }
    
    async def update_user_preferences(self, user_id: str, preferences: dict):
        """Update user preferences"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO user_preferences (user_id, subscribed_services, favorite_genres, updated_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE SET
                    subscribed_services = $2,
                    favorite_genres = $3,
                    updated_at = $4
            """, user_id, preferences.get('services'), preferences.get('genres'), datetime.utcnow())
    
    async def update_watch_history(self, content: dict, user_id: str = "default"):
        """Add content to watch history"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO watch_history (user_id, content_id, title, content_type, watched_at, progress)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, user_id, content['id'], content['title'], content['type'], datetime.utcnow(), content.get('progress', 0))
    
    async def get_watch_history(self, user_id: str = "default", limit: int = 50) -> List[dict]:
        """Get user's watch history"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT content_id, title, content_type, watched_at, progress
                FROM watch_history
                WHERE user_id = $1
                ORDER BY watched_at DESC
                LIMIT $2
            """, user_id, limit)
            
            return [dict(row) for row in rows]
    
    async def get_full_state(self) -> dict:
        """Get complete system state"""
        return {
            "tv": self.current_tv_state,
            "connected": self.tv_websocket is not None,
            "preferences": await self.get_user_preferences()
        }
```

---

# 9. PHASE 6: PRODUCTION HARDENING

## 9.1 OTA Update System

```bash
# On Dell 5070, install RAUC for A/B updates
sudo apt install rauc

# Create update bundle structure
mkdir -p ~/rauc-bundle/{rootfs,config}
```

## 9.2 Systemd Services

Create `/etc/systemd/system/tv-ui.service`:

```ini
[Unit]
Description=TV UI Application
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=tv
Environment=DISPLAY=:0
WorkingDirectory=/home/tv/tv-platform
ExecStart=/usr/bin/cage -- chromium-browser --kiosk http://localhost:3000
Restart=always
RestartSec=5

[Install]
WantedBy=graphical.target
```

## 9.3 Monitoring & Health Checks

Add to brain service:

```python
# health_check.py
import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)

SERVICES = {
    "brain_api": "http://localhost:8080/health",
    "tv_ui": "http://192.168.1.101:3000",
}

async def check_health():
    """Check health of all services"""
    results = {}
    
    async with aiohttp.ClientSession() as session:
        for name, url in SERVICES.items():
            try:
                async with session.get(url, timeout=5) as resp:
                    results[name] = resp.status == 200
            except Exception as e:
                results[name] = False
                logger.error(f"{name} health check failed: {e}")
    
    return results
```

---

# 10. API SPECIFICATIONS

## Brain WebSocket API

### Voice Bridge → Brain (ws://brain:8765/voice)

```json
// Audio submission
{
  "type": "audio",
  "timestamp": "2024-01-15T10:30:00Z",
  "sample_rate": 16000,
  "format": "wav"
}
// Followed by binary audio data

// Response
{
  "tts_response": "Playing Stranger Things on Netflix",
  "commands": [
    {"type": "launch_app", "app": "netflix"},
    {"type": "play", "content": {...}}
  ],
  "transcription": "play stranger things"
}
```

### TV Platform ↔ Brain (ws://brain:8765/tv)

```json
// State update (TV → Brain)
{
  "type": "state_update",
  "state": {
    "app": "netflix",
    "screen": "browse",
    "now_playing": null,
    "volume": 45
  }
}

// Command (Brain → TV)
{
  "type": "command",
  "action": "navigate",
  "direction": "right",
  "repeat": 3
}

// Remote button (TV → Brain)
{
  "type": "remote_button",
  "action": "select"
}
```

## Brain REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/state` | GET | Full system state |
| `/command` | POST | Send command to TV |
| `/content/search` | GET | Search content |
| `/preferences` | GET/PUT | User preferences |

---

# 11. DATABASE SCHEMA

```sql
-- database/init.sql

CREATE TABLE user_preferences (
    user_id VARCHAR(50) PRIMARY KEY,
    subscribed_services TEXT[],
    favorite_genres TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE watch_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    content_id VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content_type VARCHAR(20) NOT NULL,
    watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    progress INTEGER DEFAULT 0,
    completed BOOLEAN DEFAULT FALSE
);

CREATE TABLE content_cache (
    tmdb_id INTEGER PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content_type VARCHAR(20) NOT NULL,
    data JSONB NOT NULL,
    services TEXT[],
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_watch_history_user ON watch_history(user_id, watched_at DESC);
CREATE INDEX idx_content_cache_services ON content_cache USING GIN(services);

-- Insert default user
INSERT INTO user_preferences (user_id, subscribed_services, favorite_genres)
VALUES ('default', ARRAY['netflix', 'hulu', 'disney_plus'], ARRAY[]::TEXT[]);
```

---

# 12. FILE STRUCTURE

## Complete Project Layout

```
voice-tv-platform/
├── README.md
├── docker-compose.yml
├── .env.example
│
├── pi-zero-w/                    # Voice bridge code
│   ├── requirements.txt
│   ├── wake_word.py
│   ├── ir_control.py
│   ├── cec_control.py
│   ├── tts_service.py
│   ├── audio_stream.py
│   └── systemd/
│       └── voice-bridge.service
│
├── brain/                        # ThinkStation backend
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── whisper_service.py
│   ├── claude_service.py
│   ├── orchestrator.py
│   ├── state_manager.py
│   ├── content_discovery.py
│   └── tools/
│       ├── __init__.py
│       ├── tv_control.py
│       └── content_search.py
│
├── tv-ui/                        # Dell 5070 React app
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── components/
│       ├── hooks/
│       ├── services/
│       ├── store/
│       └── styles/
│
├── tv-platform/                  # Dell 5070 system config
│   ├── start-tv.sh
│   ├── cec_handler.py
│   └── systemd/
│       ├── tv-ui.service
│       └── cec-handler.service
│
├── database/
│   └── init.sql
│
└── config/
    └── settings.yaml
```

---

# 13. DEVELOPMENT WORKFLOW

## Daily Development Cycle

```bash
# 1. Start brain services (on ThinkStation or in Docker)
cd brain && docker-compose up -d

# 2. Start TV UI in dev mode (hot reload)
cd tv-ui && npm run dev
# Access at http://localhost:3000

# 3. Test with keyboard
# Arrow keys = D-pad navigation
# Enter = Select
# Escape = Back

# 4. Test voice commands
# SSH to Pi Zero and check logs
ssh pi@voice-bridge
journalctl -u voice-bridge -f

# 5. Deploy to Dell 5070
cd tv-ui && npm run build
scp -r dist/* tv@192.168.1.101:~/tv-platform/ui/
```

## Testing Voice Commands

```bash
# Test Whisper transcription
curl -X POST http://localhost:8080/test/transcribe \
  -F "audio=@test_audio.wav"

# Test Claude processing
curl -X POST http://localhost:8080/test/process \
  -H "Content-Type: application/json" \
  -d '{"text": "find me a good comedy movie"}'

# Send test command to TV
curl -X POST http://localhost:8080/command \
  -H "Content-Type: application/json" \
  -d '{"type": "navigate", "direction": "right"}'
```

---

# 14. BILL OF MATERIALS

## Total Cost Breakdown

| Item | Purpose | Price | Status |
|------|---------|-------|--------|
| **Pi Zero W** | Voice bridge | $15 | You have it |
| USB Audio Adapter | Better mic input | $12 | Need |
| USB Microphone | Voice capture | $15-69 | Need |
| Mini Speaker | TTS output | $10 | Need |
| IR LED + transistor | IR blaster | $5 | Optional |
| Micro USB Hub | Connect USB devices | $8 | Need |
| **Dell Wyse 5070** | TV platform | $50-70 | Ordering |
| 128GB M.2 SSD | Storage upgrade | $15 | Recommended |
| Pulse-Eight USB-CEC | Remote control | $35 | Highly recommended |
| DP to HDMI Adapter | TV connection | $15 | If needed |

### Minimum Viable Setup: ~$150-180
- Pi Zero W (have)
- Cheap USB mic ($15)
- Dell 5070 with 8GB RAM ($60)
- DP to HDMI adapter ($15)
- USB-CEC adapter ($35)

### Recommended Setup: ~$250-300
- Above plus:
- ReSpeaker USB Mic Array ($69)
- 128GB M.2 SSD ($15)
- Quality mini speaker ($20)

---

# QUICK START CHECKLIST

## Today (Pi Zero W arrives):
- [ ] Flash Raspberry Pi OS Lite
- [ ] Configure WiFi and SSH
- [ ] Install Porcupine
- [ ] Test wake word detection
- [ ] Set up IR blaster (if controlling existing TV)

## This Week (Dell 5070 arrives):
- [ ] Install Ubuntu Server
- [ ] Configure Widevine
- [ ] Install CEC adapter
- [ ] Set up Cage kiosk
- [ ] Deploy TV UI

## Backend Setup:
- [ ] Clone project to ThinkStation
- [ ] Configure .env with API keys
- [ ] Run docker-compose up
- [ ] Test voice pipeline end-to-end

## First Voice Command Target:
"Hey TV, play Stranger Things"

---

# NEXT STEPS

1. **Today**: Get Pi Zero W running with wake word detection
2. **This week**: Set up ThinkStation backend with Docker
3. **When 5070 arrives**: Install OS and UI
4. **First milestone**: Basic voice control working
5. **Second milestone**: Content search and recommendations
6. **Third milestone**: Polish UI and add features

Good luck! 🎉
