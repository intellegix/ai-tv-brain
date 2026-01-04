# Voice TV Remote - Phone-Based Architecture

## Simplified System

```
┌──────────────┐         ┌───────────────────┐         ┌─────────────┐
│   iPHONE     │  WiFi   │   THINKSTATION    │  WiFi   │  DELL 5070  │
│   Safari     │ ──────► │                   │ ──────► │             │
│              │  Audio  │  • Whisper STT    │Commands │  • TV UI    │
│  • Push-to-  │         │  • Claude API     │         │  • Streaming│
│    talk mic  │ ◄────── │  • Command router │ ◄────── │  • Playback │
│  • D-pad     │   TTS   │                   │  State  │             │
└──────────────┘         └───────────────────┘         └─────────────┘
```

**No Pi Zero needed.** Your phone is the remote.

---

## Quick Start

### 1. Start the Server (ThinkStation)

```bash
cd voice-remote

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY="your-key-here"

# Run the server
python server.py
```

Server starts at `ws://YOUR_IP:8765`

### 2. Open Remote on iPhone

1. Find your ThinkStation's IP: `hostname -I` or check router
2. On iPhone Safari, go to: `http://YOUR_THINKSTATION_IP:8080`
3. Or host the `index.html` file on any web server

**For local testing without a web server:**
```bash
# On ThinkStation, serve the HTML file
python3 -m http.server 8080

# Then on iPhone Safari: http://YOUR_IP:8080/index.html
```

### 3. Configure the Remote

1. Tap ⚙️ settings icon
2. Enter WebSocket URL: `ws://YOUR_THINKSTATION_IP:8765/voice`
3. Save & Connect

### 4. Use It

- **Push-to-talk**: Hold the mic button, speak, release
- **D-pad**: Tap arrows to navigate
- **Quick actions**: Back, Home, Pause buttons

---

## Example Voice Commands

| Say This | What Happens |
|----------|--------------|
| "Open Netflix" | Launches Netflix app |
| "Pause" | Pauses playback |
| "Turn up the volume" | Increases volume |
| "Play Stranger Things" | Searches and plays |
| "Go back" | Navigates back |
| "Search for action movies" | Opens search with query |

---

## Files

```
voice-remote/
├── index.html      # Phone web interface (Safari)
├── server.py       # ThinkStation backend
└── requirements.txt
```

---

## Add to Home Screen (iOS)

1. Open the remote URL in Safari
2. Tap Share → "Add to Home Screen"
3. Name it "TV Remote"
4. Now it launches like a native app (full screen, no browser chrome)

---

## Troubleshooting

**"Microphone access denied"**
- iOS requires HTTPS for microphone access on non-localhost URLs
- Solution: Use a self-signed cert or access via `localhost` with port forwarding

**Quick HTTPS setup:**
```bash
# Generate self-signed cert
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Run with HTTPS (modify server.py or use nginx)
```

**Connection keeps dropping**
- Check firewall allows port 8765
- Ensure devices are on same network

**Transcription is wrong**
- Speak clearly, closer to phone
- Try a larger Whisper model: `WHISPER_MODEL=small.en python server.py`

---

## Next Steps

1. **Get basic voice working** (ThinkStation + iPhone)
2. **Set up Dell 5070** with custom TV UI
3. **Connect 5070 to brain** via WebSocket
4. **Add content discovery** (TMDB integration)

The full blueprint (`voice-tv-platform-blueprint.md`) has complete code for the Dell 5070 TV UI.
