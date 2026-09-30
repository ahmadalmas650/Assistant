#!/bin/bash

# JARVIS Stop Script
# This script stops the JARVIS AI Assistant

# Configuration
PROJECT_DIR="/data/data/com.termux/files/home/Assistant"
PID_FILE="$PROJECT_DIR/temp/jarvis.pid"
LOG_FILE="$PROJECT_DIR/logs/jarvis.log"

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

log_info "Stopping JARVIS AI Assistant..."

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    log_error "PID file not found. JARVIS may not be running."
    exit 1
fi

# Read PID
PID=$(cat "$PID_FILE")

# Check if process is running
if ps -p "$PID" > /dev/null 2>&1; then
    log_info "Found JARVIS process (PID: $PID)"
    
    # Try to stop gracefully
    log_info "Sending stop signal..."
    kill "$PID" 2>/dev/null
    
    # Wait for it to stop
    TIMEOUT=10
    COUNT=0
    while ps -p "$PID" > /dev/null 2>&1 && [ "$COUNT" -lt "$TIMEOUT" ]; do
        sleep 1
        COUNT=$((COUNT + 1))
    done
    
    if ps -p "$PID" > /dev/null 2>&1; then
        log_error "JARVIS did not stop gracefully, forcing..."
        kill -9 "$PID" 2>/dev/null
        sleep 1
    fi
    
    # Remove PID file
    rm -f "$PID_FILE"
    
    log_success "JARVIS stopped successfully"
else
    log_error "JARVIS process not found (PID: $PID)"
    # Remove stale PID file
    rm -f "$PID_FILE"
    exit 1
fi

log_info "JARVIS has been stopped"
exit 0
