# JARVIS - Android AI Assistant

A production-grade Android AI Agent that operates your phone intelligently with human-like capabilities. Built for Android 15+ devices with 3GB RAM and ARM64 architecture.

## Overview

JARVIS is a modular AI assistant that:
- Observes, thinks, plans, learns, and executes tasks autonomously
- Supports both voice and typing input modes
- Provides command preview, editing, and live execution control
- Integrates with installed Android apps for multi-source learning
- Maintains privacy-aware data handling
- Syncs long-term knowledge to cloud (Mega)
- Operates efficiently within mobile resource constraints

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     JARVIS AI Assistant                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────┐ │
│  │   Python Brain   │    │  Android Bridge  │    │  Termux │ │
│  │  (Core Logic)    │◄──►│     APK         │◄──►│  Host   │ │
│  └─────────────────┘    └─────────────────┘    └─────────┘ │
│         ▲                   ▲                   ▲           │
│         │                   │                   │           │
│  ┌──────┴──────┐    ┌──────┴──────┐    ┌──────┴──────┐    │
│  │  Multi-Source  │    │ Accessibility   │    │  Voice   │    │
│  │  Learning      │    │   Service       │    │  Input   │    │
│  └──────────────┘    └──────────────┘    └────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    Memory & Knowledge                      ││
│  │  ┌──────────┐  ┌──────────┐  ┌─────────────────────────┐ ││
│  │  │ Local    │  │ Cloud    │  │  Task Execution Engine    │ ││
│  │  │ Memory   │  │ Sync     │  │  (Command Preview/Execute)│ ││
│  │  └──────────┘  └──────────┘  └─────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Features

### Input Methods
- **Voice Input**: Real-time voice command recognition
- **Typing Input**: Text-based command entry
- **Wake Word**: "Jarvis" wake word detection

### Core Capabilities
- **Task Automation**: Autonomous task execution with preview
- **Multi-Source Learning**: Integrates with installed apps (ChatGPT, DeepSeek, Chrome, YouTube, Grok, etc.)
- **Decision Engine**: Confidence-based decision making
- **OCR & Screenshot**: Text extraction from images and screen
- **Accessibility Integration**: Full device control capabilities

### Privacy & Data
- **Sensitive Data Handling**: Special processing for private information
- **Cloud Sync**: Mega cloud storage for long-term knowledge
- **Version Control**: Git-based source code management
- **Auto-Cleanup**: Temporary data removal after sync

### Resource Efficiency
- **Lightweight Design**: Optimized for 3GB RAM devices
- **Modular Architecture**: Components can be loaded/unloaded as needed
- **Background Processing**: Non-blocking task execution
- **Battery Optimization**: Minimal power consumption

## Project Structure

```
Assistant/
├── brain/                  # Python-based AI Brain
│   ├── core/              # Core decision engine
│   ├── modules/           # Feature modules
│   ├── utils/             # Utility functions
│   ├── learning/          # Multi-source learning system
│   ├── memory/            # Knowledge storage
│   └── tasks/             # Task execution pipeline
│
├── bridge/                # Android Bridge APK
│   └── app/               # Android application
│       └── src/           # Java source code
│           └── main/      # Main application code
│               ├── java/  # Java classes
│               └── res/   # Resources
│
├── configs/               # Configuration files
├── scripts/               # Setup and utility scripts
├── tests/                 # Testing framework
└── docs/                  # Documentation
```

## Development Environment

### Requirements
- **Device**: Android 15, 3GB RAM, 36GB storage, ARM64
- **Host Environment**: Termux on Android
- **Dependencies**: 
  - Termux (for Python execution)
  - Shizuku (for advanced Android APIs)
  - Rish (for accessibility services)
  - Accessibility Service (for device control)

### Setup

1. **Termux Setup**:
   ```bash
   pkg update && pkg upgrade
   pkg install python git openjdk-17
   pip install fastapi uvicorn pydantic requests pillow pytesseract
   ```

2. **Clone Repository**:
   ```bash
   git clone https://github.com/ahmadalmas650/Assistant.git
   cd Assistant
   ```

3. **Build Bridge APK**:
   ```bash
   # Will be implemented in bridge/ directory
   ```

## Usage

### Starting JARVIS
```bash
# In Termux
cd Assistant
python brain/main.py
```

### Voice Commands
- "Jarvis, upload video to YouTube"
- "Jarvis, edit this photo in Kinemaster"
- "Jarvis, what's the weather today?"

### Text Commands
```
> Upload the selected video to YouTube
Preview: [Video: my_video.mp4]
1. Check for missing metadata
2. Edit in Kinemaster if needed
3. Upload to YouTube
4. Verify upload success

Execute? (y/n/edit): y
```

## Example Workflow: Video Upload

1. **Command Received**: "Upload video to YouTube"
2. **Analysis**: 
   - Identify video file (user selection or latest)
   - Check for missing elements (title, description, thumbnail, editing)
3. **Preview**: Show execution plan
4. **Execution**:
   - Open Kinemaster for editing (if needed)
   - Generate thumbnail (if missing)
   - Create title/description
   - Upload via YouTube app
   - Verify upload success
5. **Learning**: Store workflow for future optimization

## API Keys

> **Note**: API keys should be stored securely in environment variables or secure storage. In production, never commit API keys to version control.

For development, you can temporarily add API keys to your `.env` file:
- **Groq API**: Set `GROQ_API_KEY` in `.env`
- **SiliconFlow API**: Set `SILICONFLOW_API_KEY` in `.env`

See [configs/.env.example](configs/.env.example) for the template.

## Technical Specifications

### Resource Limits
- **Memory**: Max 2GB usage during peak operations
- **Storage**: Temporary files auto-cleaned after cloud sync
- **CPU**: Optimized for ARM64, single-core efficient
- **Network**: Minimal data usage, caching enabled

### Performance Targets
- **Command Processing**: < 2 seconds for simple commands
- **Task Execution**: Background processing with notifications
- **Learning**: Real-time multi-source integration
- **Startup Time**: < 5 seconds

## Privacy Policy

- No data is sent to external servers without explicit user consent
- Sensitive information is encrypted before cloud storage
- Local temporary data is automatically cleaned
- User has full control over data sharing preferences

## License

MIT License - Feel free to use, modify, and distribute.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Support

For issues and questions, please open a GitHub issue.

---

**Built with ❤️ for Android by ahmadalmas650**

*Inspired by JARVIS from Iron Man*
