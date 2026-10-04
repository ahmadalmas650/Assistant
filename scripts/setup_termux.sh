#!/bin/bash

# JARVIS Android AI Assistant - Termux Setup Script
# This script sets up the Termux environment for JARVIS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TERMUX_HOME="/data/data/com.termux/files/home"
PROJECT_DIR="$TERMUX_HOME/Assistant"
LOG_FILE="$TERMUX_HOME/Assistant_setup.log"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
    echo "[INFO] $1" >> "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    echo "[SUCCESS] $1" >> "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    echo "[WARNING] $1" >> "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    echo "[ERROR] $1" >> "$LOG_FILE"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Create log file
echo "JARVIS Termux Setup Log" > "$LOG_FILE"
echo "Started: $(date)" >> "$LOG_FILE"
echo "=========================" >> "$LOG_FILE"

# Check if running in Termux
if [ ! -d "$TERMUX_HOME" ]; then
    log_error "Not running in Termux environment"
    echo "Please run this script in Termux on your Android device"
    exit 1
fi

log_info "Starting JARVIS Termux setup..."

# Step 1: Update and upgrade packages
log_info "Updating package lists..."
pkg update -y >> "$LOG_FILE" 2>&1
log_success "Package lists updated"

log_info "Upgrading installed packages..."
pkg upgrade -y >> "$LOG_FILE" 2>&1
log_success "Packages upgraded"

# Step 2: Install required packages
REQUIRED_PACKAGES=(
    "python"
    "git"
    "openjdk-17"
    "nodejs"
    "ffmpeg"
    "imagemagick"
    "tesseract"
    "wget"
    "curl"
    "nano"
    "tmux"
    "htop"
)

log_info "Installing required packages..."
for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if check_command "$pkg"; then
        log_info "$pkg is already installed"
    else
        log_info "Installing $pkg..."
        pkg install -y "$pkg" >> "$LOG_FILE" 2>&1
        if check_command "$pkg"; then
            log_success "$pkg installed"
        else
            log_error "Failed to install $pkg"
            exit 1
        fi
    fi
done

# Step 3: Install Python packages
log_info "Installing Python packages..."

PYTHON_PACKAGES=(
    "cryptography"
    "psutil"
    "pytest"
    "pytest-asyncio"
)

for pip_pkg in "${PYTHON_PACKAGES[@]}"; do
    if python -c "import $pip_pkg" &> /dev/null; then
        log_info "$pip_pkg is already installed"
    else
        log_info "Installing $pip_pkg..."
        pip install "$pip_pkg" >> "$LOG_FILE" 2>&1
        if python -c "import $pip_pkg" &> /dev/null; then
            log_success "$pip_pkg installed"
        else
            log_error "Failed to install $pip_pkg"
            exit 1
        fi
    fi
done

# Step 4: Clone or update the JARVIS project
log_info "Setting up JARVIS project..."

if [ -d "$PROJECT_DIR" ]; then
    log_info "JARVIS directory exists, updating..."
    cd "$PROJECT_DIR"
    git pull >> "$LOG_FILE" 2>&1
    log_success "JARVIS project updated"
else
    log_info "Cloning JARVIS repository..."
    git clone https://github.com/ahmadalmas650/Assistant.git "$PROJECT_DIR" >> "$LOG_FILE" 2>&1
    cd "$PROJECT_DIR"
    log_success "JARVIS project cloned"
fi

# Step 5: Install project dependencies
log_info "Installing project dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt >> "$LOG_FILE" 2>&1
    log_success "Project dependencies installed"
else
    log_warning "No requirements.txt found"
fi

# Step 6: Setup environment variables
log_info "Setting up environment variables..."

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    cp "configs/.env.example" ".env"
    log_info "Created .env file from example"
fi

# Set JAVA_HOME
if [ -d "$PREFIX/lib/jvm/openjdk-17" ]; then
    echo "export JAVA_HOME=$PREFIX/lib/jvm/openjdk-17" >> "$TERMUX_HOME/.bashrc"
    echo "export PATH=\"$JAVA_HOME/bin:\"$PATH"" >> "$TERMUX_HOME/.bashrc"
    log_success "JAVA_HOME configured"
fi

# Step 7: Setup Termux API (if available)
log_info "Checking for Termux:API..."
if check_command "termux-api"; then
    log_info "Termux:API is available"
else
    log_info "Termux:API not found, installing..."
    pkg install -y termux-api >> "$LOG_FILE" 2>&1
    if check_command "termux-api"; then
        log_success "Termux:API installed"
    else
        log_warning "Termux:API not available (optional)"
    fi
fi

# Step 8: Setup Shizuku (if available)
log_info "Checking for Shizuku..."
if [ -d "$TERMUX_HOME/../shizuku" ]; then
    log_info "Shizuku files found"
else
    log_info "Shizuku not found (optional for advanced features)"
    log_warning "Some features may require Shizuku for full functionality"
fi

# Step 9: Create necessary directories
log_info "Creating necessary directories..."

mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/temp"
mkdir -p "$PROJECT_DIR/configs"

log_success "Directories created"

# Step 10: Setup Python server script
log_info "Setting up Python server script..."

cat > "$PROJECT_DIR/start_jarvis.sh" << 'EOF'
#!/bin/bash

# Start JARVIS Python server
cd /data/data/com.termux/files/home/Assistant

echo "Starting JARVIS..."
echo "=================="

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "Python is not installed. Please install Python first."
    exit 1
fi

# Check if requirements are installed
if [ -f "requirements.txt" ]; then
    echo "Checking dependencies..."
    pip install -r requirements.txt
fi

# Start the brain
echo "Starting JARVIS Brain..."
python brain/main.py

EOF

chmod +x "$PROJECT_DIR/start_jarvis.sh"
log_success "Python server script created"

# Step 11: Final verification
log_info "Verifying setup..."

# Check Python
python --version >> "$LOG_FILE" 2>&1
log_success "Python version: $(python --version 2>&1)"

# Check Java
java -version >> "$LOG_FILE" 2>&1
log_success "Java version: $(java -version 2>&1)"

# Check Git
git --version >> "$LOG_FILE" 2>&1
log_success "Git version: $(git --version 2>&1)"

# Check project structure
if [ -f "$PROJECT_DIR/brain/main.py" ]; then
    log_success "JARVIS brain found"
else
    log_error "JARVIS brain not found"
    exit 1
fi

# Complete
echo ""
log_success "JARVIS Termux setup completed successfully!"
echo ""
log_info "To start JARVIS, run:"
log_info "  cd $PROJECT_DIR"
log_info "  bash start_jarvis.sh"
echo ""
log_info "Or simply:"
log_info "  python $PROJECT_DIR/brain/main.py"
echo ""
log_info "Setup log saved to: $LOG_FILE"
echo ""

echo "=========================" >> "$LOG_FILE"
echo "Setup completed: $(date)" >> "$LOG_FILE"

exit 0
