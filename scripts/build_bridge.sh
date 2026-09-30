#!/bin/bash

# JARVIS Bridge APK Build Script
# This script builds the Android Bridge APK

set -e

# Configuration
PROJECT_DIR="/data/data/com.termux/files/home/Assistant"
BRIDGE_DIR="$PROJECT_DIR/bridge"
BUILD_LOG="$PROJECT_DIR/logs/bridge_build.log"
OUTPUT_APK="$BRIDGE_DIR/app/build/outputs/apk/debug/app-debug.apk"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1" >> "$BUILD_LOG"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [SUCCESS] $1" >> "$BUILD_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1" >> "$BUILD_LOG"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [WARNING] $1" >> "$BUILD_LOG"
}

# Create directories
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$BRIDGE_DIR/app/build/outputs/apk/debug"

# Create build log
echo "JARVIS Bridge Build Log" > "$BUILD_LOG"
echo "Started: $(date)" >> "$BUILD_LOG"
echo "=========================" >> "$BUILD_LOG"

log_info "Starting JARVIS Bridge APK build..."

# Check if we're in Termux
if [ ! -d "$PREFIX" ]; then
    log_error "Not running in Termux environment"
    echo "Please run this script in Termux on your Android device"
    exit 1
fi

# Check Java
log_info "Checking Java installation..."
if ! command -v java &> /dev/null; then
    log_error "Java is not installed"
    echo "Installing OpenJDK 17..."
    pkg install -y openjdk-17 >> "$BUILD_LOG" 2>&1
    if ! command -v java &> /dev/null; then
        log_error "Failed to install Java"
        exit 1
    fi
fi

JAVA_VERSION=$(java -version 2>&1 | head -n 1 | cut -d'"' -f 2)
log_success "Java version: $JAVA_VERSION"

# Set JAVA_HOME
export JAVA_HOME="$PREFIX/lib/jvm/openjdk-17"
export PATH="$JAVA_HOME/bin:$PATH"

# Check Gradle
log_info "Checking Gradle installation..."
if ! command -v gradle &> /dev/null; then
    log_info "Gradle not found, installing..."
    
    # Install Gradle
    GRADLE_VERSION="8.1.1"
    GRADLE_DIR="$PREFIX/opt/gradle"
    GRADLE_ZIP="gradle-$GRADLE_VERSION-all.zip"
    GRADLE_URL="https://services.gradle.org/distributions/$GRADLE_ZIP"
    
    mkdir -p "$GRADLE_DIR"
    cd "$GRADLE_DIR"
    
    if [ ! -f "$GRADLE_ZIP" ]; then
        log_info "Downloading Gradle $GRADLE_VERSION..."
        wget "$GRADLE_URL" -O "$GRADLE_ZIP" >> "$BUILD_LOG" 2>&1
        if [ ! -f "$GRADLE_ZIP" ]; then
            log_error "Failed to download Gradle"
            exit 1
        fi
    fi
    
    log_info "Extracting Gradle..."
    unzip -q "$GRADLE_ZIP" -d "$GRADLE_DIR" >> "$BUILD_LOG" 2>&1
    
    # Add to PATH
    GRADLE_BIN="$GRADLE_DIR/gradle-$GRADLE_VERSION/bin"
    export PATH="$GRADLE_BIN:$PATH"
    
    if ! command -v gradle &> /dev/null; then
        log_error "Gradle installation failed"
        exit 1
    fi
    
    log_success "Gradle installed"
else
    log_info "Gradle is already installed"
fi

# Check Android SDK
log_info "Checking Android SDK..."
if [ ! -d "$PREFIX/android-sdk" ]; then
    log_error "Android SDK not found"
    log_info "Android SDK is required to build the APK"
    log_info "Please install Android SDK first"
    exit 1
fi

# Set ANDROID_HOME
export ANDROID_HOME="$PREFIX/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"

# Check for required SDK packages
log_info "Checking Android SDK packages..."

REQUIRED_PACKAGES=(
    "platform-tools"
    "platforms;android-34"
    "build-tools;34.0.0"
)

for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if [ ! -d "$ANDROID_HOME/$pkg" ]; then
        log_info "Installing SDK package: $pkg..."
        # Note: In Termux, you need to use sdkmanager or install manually
        # This is a placeholder - actual installation may vary
        log_warning "SDK package $pkg not found. You may need to install it manually."
    fi
done

# Set up environment for Gradle
log_info "Setting up Gradle environment..."

# Create gradle.properties if it doesn't exist
if [ ! -f "$BRIDGE_DIR/gradle.properties" ]; then
    cat > "$BRIDGE_DIR/gradle.properties" << 'EOF'
# Project-wide Gradle settings.
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
org.gradle.daemon=true
android.useAndroidX=true
android.enableJetifier=true
org.gradle.configuration-cache=true
org.gradle.caching=true
EOF
    log_info "Created gradle.properties"
fi

# Build the APK
log_info "Building JARVIS Bridge APK..."

cd "$BRIDGE_DIR"

# Clean previous build
log_info "Cleaning previous build..."
./gradlew clean >> "$BUILD_LOG" 2>&1

# Build debug APK
log_info "Building debug APK..."
./gradlew assembleDebug --stacktrace >> "$BUILD_LOG" 2>&1

# Check if APK was built
if [ -f "$OUTPUT_APK" ]; then
    log_success "APK built successfully!"
    log_info "APK location: $OUTPUT_APK"
    
    # Get APK size
    APK_SIZE=$(du -h "$OUTPUT_APK" | cut -f 1)
    log_info "APK size: $APK_SIZE"
    
    # Ask to install
    read -p "Do you want to install the APK now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Installing APK..."
        
        # Check for adb
        if command -v adb &> /dev/null; then
            adb install -r "$OUTPUT_APK"
            if [ $? -eq 0 ]; then
                log_success "APK installed successfully!"
            else
                log_error "Failed to install APK"
                log_info "You can manually install it using:"
                log_info "  adb install -r $OUTPUT_APK"
            fi
        else
            log_info "ADB not found. APK is ready for manual installation."
            log_info "APK location: $OUTPUT_APK"
        fi
    fi
else
    log_error "APK build failed"
    log_info "Check the build log for details: $BUILD_LOG"
    exit 1
fi

log_info "Build completed successfully"
echo ""
log_info "Build log saved to: $BUILD_LOG"
exit 0
