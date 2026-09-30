#!/bin/bash

# JARVIS Start Script
# This script starts the JARVIS AI Assistant

set -e

# Configuration
PROJECT_DIR="/data/data/com.termux/files/home/Assistant"
LOG_FILE="$PROJECT_DIR/logs/jarvis.log"
PID_FILE="$PROJECT_DIR/temp/jarvis.pid"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1" >> "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [SUCCESS] $1" >> "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1" >> "$LOG_FILE"
}

# Create directories if they don't exist
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/temp"
mkdir -p "$PROJECT_DIR/data"

# Create log file if it doesn't exist
touch "$LOG_FILE"

log_info "Starting JARVIS AI Assistant..."
log_info "Project directory: $PROJECT_DIR"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        log_error "JARVIS is already running (PID: $PID)"
        echo "To stop JARVIS, run: bash $PROJECT_DIR/scripts/stop_jarvis.sh"
        exit 1
    else
        # Remove stale PID file
        rm -f "$PID_FILE"
    fi
fi

# Check Python
if ! command -v python &> /dev/null; then
    log_error "Python is not installed"
    echo "Please install Python first: pkg install python"
    exit 1
fi

log_info "Python version: $(python --version 2>&1)"

# Check if we're in the right directory
cd "$PROJECT_DIR"

# Check if brain exists
if [ ! -f "brain/main.py" ]; then
    log_error "JARVIS brain not found in $PROJECT_DIR"
    echo "Please ensure you're in the correct directory"
    exit 1
fi

# Check for .env file
if [ -f ".env" ]; then
    log_info "Loading environment variables from .env"
else
    log_warning ".env file not found, using defaults"
fi

# Start the brain
log_info "Starting JARVIS Brain..."

# Save PID
python brain/main.py &
PID=$!
echo "$PID" > "$PID_FILE"

log_success "JARVIS started successfully (PID: $PID)"
log_info "Listening for commands..."
log_info "Press Ctrl+C to stop"

# Wait for the process to finish
wait "$PID"

# Cleanup
rm -f "$PID_FILE"
log_info "JARVIS stopped"

exit 0
