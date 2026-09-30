# JARVIS Development Guide

## Overview

This guide provides comprehensive instructions for developing, testing, and deploying the JARVIS Android AI Assistant.

## Prerequisites

### Device Requirements
- **Android Version**: 15 (API Level 34)
- **Minimum RAM**: 3GB
- **Minimum Storage**: 10GB free space
- **Architecture**: ARM64

### Software Requirements
- **Termux**: For Python execution and development environment
- **Shizuku**: For advanced Android API access (optional but recommended)
- **Rish**: For accessibility services (optional)
- **Git**: For version control

## Setup Instructions

### 1. Install Termux

Download and install Termux from:
- [F-Droid](https://f-droid.org/en/packages/com.termux/) (recommended)
- Or from GitHub releases

### 2. Setup Termux Environment

Run the following commands in Termux:

```bash
# Update and upgrade packages
pkg update -y && pkg upgrade -y

# Install required packages
pkg install -y python git openjdk-17 nodejs ffmpeg imagemagick tesseract wget curl nano tmux htop

# Install Python dependencies
pip install fastapi uvicorn pydantic requests numpy pillow opencv-python-headless pytesseract pydub speechrecognition pyttsx3 python-multipart python-dotenv loguru psutil
```

### 3. Clone the Repository

```bash
# Clone the JARVIS repository
git clone https://github.com/ahmadalmas650/Assistant.git
cd Assistant

# Checkout the latest version
git pull origin main
```

### 4. Setup Configuration

```bash
# Copy example environment file
cp configs/.env.example .env

# Edit the .env file to configure JARVIS
nano .env
```

### 5. Install Project Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt
```

### 6. Setup Shizuku (Optional but Recommended)

1. Download and install Shizuku from [GitHub](https://github.com/RikkaApps/Shizuku)
2. Start Shizuku and enable ADB pairing
3. In Termux, run:
   ```bash
   shizuku start
   shizuku check
   ```

### 7. Enable Accessibility Service

1. Open Android Settings
2. Go to Accessibility
3. Enable "JARVIS Accessibility Service"
4. Grant all requested permissions

### 8. Build the Bridge APK (Optional)

```bash
# Navigate to bridge directory
cd bridge

# Build the APK (requires Android SDK)
bash ../scripts/build_bridge.sh

# Install the APK
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Running JARVIS

### Start JARVIS

```bash
# From the project root directory
python brain/main.py
```

Or use the start script:

```bash
bash scripts/start_jarvis.sh
```

### Stop JARVIS

```bash
bash scripts/stop_jarvis.sh
```

### Interactive Mode

Once started, JARVIS will enter interactive mode where you can type commands directly.

```
> Jarvis, upload video to YouTube
> Upload this photo
> Take a screenshot
> exit
```

## Development Workflow

### 1. Making Changes

1. Create a new feature branch:
   ```bash
   git checkout -b feature/new-feature
   ```

2. Make your changes to the code

3. Test your changes:
   ```bash
   python tests/run_tests.py
   ```

### 2. Testing

Run all tests:
```bash
python tests/run_tests.py
```

Run specific test class:
```bash
python tests/run_tests.py TestBrainEngine
```

Run specific test method:
```bash
python tests/run_tests.py TestBrainEngine test_initialization
```

List all available tests:
```bash
python tests/run_tests.py --list
```

### 3. Code Quality

- Follow PEP 8 style guide for Python code
- Use type hints for all function parameters and return values
- Add docstrings to all classes and public methods
- Keep functions small and focused
- Use async/await for I/O operations

### 4. Commit Changes

```bash
# Add changes
git add .

# Commit with descriptive message
git commit -m "Add new feature: description of changes"

# Push to remote
git push origin feature/new-feature
```

### 5. Create Pull Request

1. Go to GitHub repository
2. Create a new Pull Request from your feature branch
3. Fill in the PR description with details of your changes
4. Wait for review and address any feedback
5. Once approved, the PR will be merged

## Project Structure

```
Assistant/
├── brain/                          # Python AI Brain
│   ├── core/                      # Core components
│   │   ├── brain_engine.py        # Main brain engine
│   │   ├── decision_maker.py      # Decision making
│   │   ├── confidence_engine.py   # Confidence calculation
│   │   ├── task_planner.py        # Task planning
│   │   └── execution_controller.py # Task execution
│   ├── modules/                   # Feature modules
│   │   ├── input_processor.py     # Input processing
│   │   ├── command_parser.py      # Command parsing
│   │   ├── wake_word_detector.py  # Wake word detection
│   │   ├── accessibility_controller.py # Accessibility
│   │   ├── screenshot_manager.py  # Screenshot
│   │   ├── ocr_engine.py          # OCR
│   │   ├── app_integrator.py      # App integration
│   │   └── output_generator.py    # Output generation
│   ├── learning/                  # Learning system
│   │   ├── multi_source_learner.py # Multi-source learning
│   │   ├── knowledge_merger.py    # Knowledge merging
│   │   ├── information_comparator.py # Information comparison
│   │   └── learning_manager.py    # Learning management
│   ├── memory/                    # Memory system
│   │   ├── memory_manager.py      # Memory management
│   │   ├── local_memory.py        # Local storage
│   │   ├── cloud_memory.py        # Cloud storage
│   │   └── knowledge_base.py      # Knowledge base
│   ├── tasks/                    # Task management
│   │   ├── task_manager.py       # Task management
│   │   ├── task_executor.py       # Task execution
│   │   ├── preview_system.py      # Command preview
│   │   └── live_control_system.py # Live control
│   ├── utils/                    # Utilities
│   │   ├── logger.py             # Logging
│   │   ├── error_handler.py      # Error handling
│   │   ├── resource_monitor.py   # Resource monitoring
│   │   ├── privacy_guard.py      # Privacy protection
│   │   └── cloud_sync.py         # Cloud sync
│   └── main.py                  # Main entry point
├── bridge/                       # Android Bridge APK
│   ├── app/                      # Android application
│   │   ├── src/                 # Source code
│   │   │   └── main/            # Main application
│   │   │       ├── java/        # Java source
│   │   │       └── res/         # Resources
│   │   └── build.gradle         # Build configuration
│   ├── build.gradle              # Project build
│   ├── settings.gradle           # Settings
│   └── gradle.properties         # Gradle properties
├── configs/                     # Configuration files
│   ├── config.json              # Main configuration
│   ├── termux_config.json       # Termux configuration
│   ├── api_keys.json            # API keys (template)
│   └── .env.example             # Environment example
├── scripts/                     # Setup and utility scripts
│   ├── setup_termux.sh          # Termux setup
│   ├── start_jarvis.sh          # Start JARVIS
│   ├── stop_jarvis.sh           # Stop JARVIS
│   └── build_bridge.sh          # Build bridge APK
├── tests/                       # Test suite
│   ├── __init__.py              # Test initialization
│   ├── run_tests.py             # Test runner
│   ├── test_brain_engine.py     # Brain engine tests
│   ├── test_input_processor.py  # Input processor tests
│   └── test_command_parser.py   # Command parser tests
├── docs/                        # Documentation
│   ├── README.md                # Main README
│   ├── DEVELOPMENT.md           # Development guide
│   ├── ARCHITECTURE.md          # Architecture overview
│   └── API.md                   # API documentation
└── requirements.txt             # Python dependencies
```

## Key Components

### Brain Engine

The brain engine is the core intelligence of JARVIS. It:
- Processes input commands (voice and text)
- Parses and understands commands
- Makes decisions based on confidence levels
- Plans and executes tasks
- Learns from user interactions
- Manages memory and knowledge

### Android Bridge

The Android Bridge APK provides:
- Accessibility service for device control
- Integration with installed apps
- Screenshot and OCR capabilities
- Background service for persistent connection
- Broadcast receiver for Termux integration

### Input System

Supports:
- Voice input with wake word detection
- Text input
- Multi-language support
- Real-time processing

### Task System

Features:
- Task planning and execution
- Command preview before execution
- Live control during execution
- Background processing
- Retry and error handling

### Learning System

Capabilities:
- Multi-source learning (ChatGPT, DeepSeek, YouTube, Grok, etc.)
- Knowledge merging and comparison
- Confidence-based decision making
- Continuous improvement

### Memory System

Includes:
- Short-term and long-term memory
- Local storage
- Cloud sync (Mega)
- Knowledge base
- Automatic cleanup

## API Documentation

See [API.md](API.md) for detailed API documentation.

## Architecture Overview

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture information.

## Troubleshooting

### Common Issues

1. **Python not found**: Ensure Python is installed in Termux
   ```bash
   pkg install python
   ```

2. **Missing dependencies**: Install required packages
   ```bash
   pip install -r requirements.txt
   ```

3. **Accessibility service not working**: Enable the service in Android settings

4. **Shizuku not connecting**: Ensure Shizuku is started and ADB pairing is enabled

5. **Bridge APK build failed**: Ensure Android SDK is installed and configured

### Debug Mode

Enable debug mode in `.env` file:
```
BRAIN_DEBUG_MODE=true
LOG_LEVEL=DEBUG
```

### Log Files

JARVIS creates log files in:
- `/data/data/com.termux/files/home/Assistant/logs/`

View logs:
```bash
cat logs/jarvis.log
```

## Performance Optimization

### Memory Management

- Limit maximum memory usage in config
- Enable automatic cleanup of temporary data
- Monitor resource usage with the resource monitor

### CPU Optimization

- Limit maximum CPU usage
- Use background processing for long tasks
- Optimize task execution order

### Battery Optimization

- Enable battery optimization in config
- Use low power mode when possible
- Minimize background processing when not needed

## Security Guidelines

### API Keys

- Never commit API keys to version control
- Use environment variables for sensitive data
- Rotate API keys regularly

### Privacy

- Enable privacy mode in config
- Use data masking for sensitive information
- Always request user consent for sensitive operations

### Data Storage

- Encrypt sensitive data
- Use secure storage for credentials
- Clean up temporary data regularly

## Contributing

See the main [README.md](../README.md) for contributing guidelines.

## License

This project is licensed under the MIT License. See [LICENSE](../LICENSE) for details.

---

**Built with ❤️ for Android by ahmadalmas650**
