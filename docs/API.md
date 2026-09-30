# JARVIS API Documentation

## Overview

JARVIS provides multiple APIs for integration and control:

1. **Python API**: Direct Python integration
2. **HTTP API**: REST API for remote control
3. **WebSocket API**: Real-time communication
4. **Android Intent API**: Integration with Android apps
5. **Termux CLI**: Command-line interface

## Python API

### Main JARVIS Class

```python
from brain.main import JARVIS
from configs.config import Config

# Initialize JARVIS
config = Config()
jarvis = JARVIS(config)
await jarvis.initialize()

# Process a command
result = await jarvis.process_command("Jarvis, upload video to YouTube", "text")

# Execute a command directly (bypasses wake word)
result = await jarvis.execute_direct("upload video to YouTube")

# Get command preview
preview = await jarvis.get_preview("upload video")

# Stop current task
success = await jarvis.stop_current_task()

# Modify current task
success = await jarvis.modify_current_task("change parameter")

# Get status
status = await jarvis.get_status()

# Get capabilities
capabilities = await jarvis.get_capabilities()

# Learn from feedback
success = await jarvis.learn_from_feedback({"type": "correction", "data": {...}})

# Query knowledge
knowledge = await jarvis.get_knowledge("AI assistant")

# Sync with cloud
success = await jarvis.sync_with_cloud()

# Shutdown
await jarvis.shutdown()
```

### Brain Engine API

```python
from brain.core.brain_engine import BrainEngine, BrainConfig

# Create brain engine
config = BrainConfig(
    name="JARVIS",
    wake_word="jarvis",
    max_memory_usage=2.0,
    learning_enabled=True
)
brain = BrainEngine(config)
await brain.initialize()

# Process input
result = await brain.process_input("jarvis hello", "text")

# Execute command
result = await brain.execute_command("hello")

# Get preview
preview = await brain.get_preview("upload video")

# Stop current task
success = await brain.stop_current_task()

# Get status
status = await brain.get_status()

# Get capabilities
capabilities = await brain.get_capabilities()

# Learn from feedback
success = await brain.learn_from_feedback({...})

# Get knowledge
knowledge = await brain.get_knowledge("query")

# Sync with cloud
success = await brain.sync_with_cloud()

# Update configuration
brain.update_config(learning_enabled=False)

# Shutdown
await brain.shutdown()
```

### Module APIs

#### Input Processor

```python
from brain.modules.input_processor import InputProcessor

processor = InputProcessor(config, logger)

# Process text
result = await processor.process("Hello world", "text")

# Process voice
result = await processor.process(audio_bytes, "voice")

# Start/stop listening
await processor.start_listening()
await processor.stop_listening()

# Check wake word
has_wake_word, result = await processor.process_with_wake_word("jarvis hello", "text")

# Set language
processor.set_language("en")
```

#### Command Parser

```python
from brain.modules.command_parser import CommandParser

parser = CommandParser(config, logger)

# Parse command
result = await parser.parse("upload video to YouTube")

# Access parsed data
intent = result.intent  # IntentType.UPLOAD
entities = result.entities  # List of ExtractedEntity
tags = result.tags  # List of strings
is_valid = result.valid  # bool
```

#### Task Manager

```python
from brain.tasks.task_manager import TaskManager
from brain.core.task_planner import TaskPlan

manager = TaskManager(config, logger)
await manager.initialize()

# Create task
task = await manager.create_task(plan, priority=TaskPriority.HIGH)

# Queue task
await manager.queue_task(task_id)

# Start task
await manager.start_task(task_id)

# Execute task
success, result = await manager.execute_task(task_id, plan)

# Stop task
await manager.cancel_task(task_id)

# Get task info
task_info = await manager.get_task(task_id)

# Get all tasks
all_tasks = await manager.get_all_tasks()

# Get queue status
queue_status = await manager.get_queue_status()

# Cleanup
removed = await manager.cleanup_completed_tasks()
```

#### Preview System

```python
from brain.tasks.preview_system import PreviewSystem
from brain.core.task_planner import TaskPlan

preview_system = PreviewSystem(config, logger)

# Generate preview
preview_data = await preview_system.generate_preview(plan)

# Display preview
formatted_preview = await preview_system.display_preview(preview_data)

# Edit plan
from brain.tasks.live_control_system import EditAction, EditRequest
edit_request = EditRequest(
    action=EditAction.ADD_STEP,
    target="",
    value={"action": "new_step", "description": "New step"}
)
edit_result = await preview_system.edit_plan(plan, edit_request)

# Validate edit
is_valid, message = await preview_system.validate_edit(plan, edit_request)
```

#### Live Control System

```python
from brain.tasks.live_control_system import LiveControlSystem, ControlCommand

control_system = LiveControlSystem(config, logger)
await control_system.initialize()

# Start task with live control
await control_system.start_task(task_id, plan)

# Send control command
response = await control_system.send_command(ControlCommand.PAUSE)
response = await control_system.send_command(ControlCommand.RESUME)
response = await control_system.send_command(ControlCommand.STOP)
response = await control_system.send_command(ControlCommand.SKIP)

# Get current state
state = control_system.get_current_state()

# Get current progress
progress = control_system.get_current_progress()

# Set control mode
await control_system.set_control_mode(ControlMode.STEP_BY_STEP)

# Check if task is running
is_running = await control_system.is_task_running()
```

## HTTP API (FastAPI)

### Starting the HTTP Server

```python
from fastapi import FastAPI
from brain.main import JARVIS

app = FastAPI(title="JARVIS API")
jarvis = JARVIS()

@app.on_event("startup")
async def startup():
    await jarvis.initialize()

@app.on_event("shutdown")
async def shutdown():
    await jarvis.shutdown()

@app.post("/command")
async def process_command(request: dict):
    result = await jarvis.process_command(
        request.get("command", ""),
        request.get("input_type", "text")
    )
    return result

@app.post("/execute")
async def execute_command(request: dict):
    result = await jarvis.execute_direct(request.get("command", ""))
    return result

@app.get("/preview")
async def get_preview(command: str):
    result = await jarvis.get_preview(command)
    return result

@app.post("/stop")
async def stop_task():
    success = await jarvis.stop_current_task()
    return {"success": success}

@app.get("/status")
async def get_status():
    return await jarvis.get_status()

@app.get("/capabilities")
async def get_capabilities():
    return await jarvis.get_capabilities()

@app.post("/learn")
async def learn_from_feedback(feedback: dict):
    success = await jarvis.learn_from_feedback(feedback)
    return {"success": success}

@app.get("/knowledge")
async def query_knowledge(query: str):
    return await jarvis.get_knowledge(query)

@app.post("/sync")
async def sync_cloud():
    success = await jarvis.sync_with_cloud()
    return {"success": success}
```

### HTTP API Endpoints

| Method | Endpoint | Description | Parameters | Response |
|--------|----------|-------------|------------|----------|
| POST | `/command` | Process a command | `command`, `input_type` | Command result |
| POST | `/execute` | Execute command directly | `command` | Execution result |
| GET | `/preview` | Get command preview | `command` | Preview data |
| POST | `/stop` | Stop current task | - | Success status |
| GET | `/status` | Get current status | - | Status data |
| GET | `/capabilities` | Get capabilities | - | List of capabilities |
| POST | `/learn` | Learn from feedback | `feedback` | Success status |
| GET | `/knowledge` | Query knowledge | `query` | Knowledge data |
| POST | `/sync` | Sync with cloud | - | Success status |

### Example HTTP Requests

```bash
# Process a command
curl -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{"command": "Jarvis, upload video to YouTube", "input_type": "text"}'

# Get command preview
curl -X GET "http://localhost:8000/preview?command=upload%20video"

# Get status
curl -X GET http://localhost:8000/status

# Stop current task
curl -X POST http://localhost:8000/stop

# Get capabilities
curl -X GET http://localhost:8000/capabilities
```

## WebSocket API

### WebSocket Server

```python
from fastapi import FastAPI, WebSocket
from brain.main import JARVIS

app = FastAPI()
jarvis = JARVIS()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Send welcome message
    await websocket.send_json({
        "type": "welcome",
        "message": "Connected to JARVIS WebSocket",
        "capabilities": await jarvis.get_capabilities()
    })
    
    while True:
        data = await websocket.receive_json()
        
        # Handle different message types
        if data.get("type") == "command":
            result = await jarvis.process_command(
                data.get("command", ""),
                data.get("input_type", "text")
            )
            await websocket.send_json({
                "type": "command_result",
                "result": result
            })
        
        elif data.get("type") == "status":
            status = await jarvis.get_status()
            await websocket.send_json({
                "type": "status",
                "status": status
            })
        
        elif data.get("type") == "stop":
            success = await jarvis.stop_current_task()
            await websocket.send_json({
                "type": "stop_result",
                "success": success
            })
        
        elif data.get("type") == "subscribe":
            # Subscribe to events
            pass
```

### WebSocket Message Types

#### Client to Server

| Type | Description | Parameters |
|------|-------------|------------|
| `command` | Process a command | `command`, `input_type` |
| `execute` | Execute command directly | `command` |
| `preview` | Get command preview | `command` |
| `stop` | Stop current task | - |
| `status` | Get current status | - |
| `subscribe` | Subscribe to events | `events` (list) |
| `unsubscribe` | Unsubscribe from events | `events` (list) |
| `learn` | Learn from feedback | `feedback` |
| `knowledge` | Query knowledge | `query` |

#### Server to Client

| Type | Description | Data |
|------|-------------|------|
| `welcome` | Connection established | `capabilities` |
| `command_result` | Command processing result | `result` |
| `preview` | Command preview | `preview` |
| `status` | Current status | `status` |
| `stop_result` | Stop task result | `success` |
| `progress` | Task progress update | `progress`, `step`, `total` |
| `event` | Event notification | `event_type`, `data` |
| `error` | Error notification | `error`, `message` |

### Example WebSocket Usage

```javascript
// JavaScript client example
const socket = new WebSocket('ws://localhost:8000/ws');

socket.onopen = function(e) {
    console.log('Connected to JARVIS');
};

socket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
    
    if (data.type === 'welcome') {
        console.log('Capabilities:', data.capabilities);
    } else if (data.type === 'command_result') {
        console.log('Result:', data.result);
    } else if (data.type === 'progress') {
        console.log('Progress:', data.progress);
    }
};

// Send a command
socket.send(JSON.stringify({
    type: 'command',
    command: 'Jarvis, upload video to YouTube',
    input_type: 'text'
}));

// Get status
socket.send(JSON.stringify({
    type: 'status'
}));

// Stop current task
socket.send(JSON.stringify({
    type: 'stop'
}));
```

## Android Intent API

### Sending Commands via Intents

```java
// Send a command to JARVIS
Intent intent = new Intent("com.assistant.bridge.COMMAND");
intent.putExtra("command", "Jarvis, upload video to YouTube");
intent.putExtra("input_type", "text");
context.sendBroadcast(intent);

// Send a command with additional data
Intent intent = new Intent("com.assistant.bridge.COMMAND");
intent.putExtra("command", "upload");
intent.putExtra("data", "{"file": "/path/to/video.mp4"}");
context.sendBroadcast(intent);
```

### Receiving Responses

```java
// Register a broadcast receiver for responses
BroadcastReceiver receiver = new BroadcastReceiver() {
    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        if ("com.assistant.bridge.RESPONSE".equals(action)) {
            String requestId = intent.getStringExtra("request_id");
            String message = intent.getStringExtra("message");
            boolean success = intent.getBooleanExtra("success", false);
            
            // Handle response
            Log.d("JARVIS", "Response: " + message);
        }
    }
};

// Register the receiver
IntentFilter filter = new IntentFilter("com.assistant.bridge.RESPONSE");
context.registerReceiver(receiver, filter);
```

### Intent Actions

| Action | Description | Extras |
|--------|-------------|--------|
| `com.assistant.bridge.COMMAND` | Send a command | `command`, `input_type`, `data` |
| `com.assistant.bridge.ACTION` | Trigger an action | `action`, `data` |
| `com.assistant.bridge.RESPONSE` | Response from JARVIS | `request_id`, `message`, `success` |
| `com.assistant.bridge.ERROR` | Error notification | `request_id`, `error`, `message` |
| `com.assistant.bridge.LOG` | Log message | `level`, `message`, `tag` |

## Termux CLI

### Basic Commands

```bash
# Start JARVIS
python brain/main.py

# Start with custom config
python brain/main.py --config configs/custom_config.json

# Run tests
python tests/run_tests.py

# Run specific test
python tests/run_tests.py TestBrainEngine

# Run specific test method
python tests/run_tests.py TestBrainEngine test_initialization

# List all tests
python tests/run_tests.py --list
```

### Using Scripts

```bash
# Setup Termux environment
bash scripts/setup_termux.sh

# Start JARVIS
bash scripts/start_jarvis.sh

# Stop JARVIS
bash scripts/stop_jarvis.sh

# Build bridge APK
bash scripts/build_bridge.sh
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BRAIN_WAKE_WORD` | Wake word | `jarvis` |
| `BRAIN_MAX_MEMORY_GB` | Max memory usage | `2.0` |
| `BRAIN_MIN_CONFIDENCE` | Min confidence threshold | `0.7` |
| `BRAIN_LEARNING_ENABLED` | Enable learning | `true` |
| `BRAIN_CLOUD_SYNC_ENABLED` | Enable cloud sync | `true` |
| `BRAIN_PRIVACY_MODE` | Enable privacy mode | `true` |
| `BRAIN_DEBUG_MODE` | Enable debug mode | `false` |
| `LOG_LEVEL` | Log level | `INFO` |

## Error Handling

### Error Response Format

All APIs return errors in a consistent format:

```json
{
    "status": "error",
    "error": "Error message",
    "error_code": "ERROR_CODE",
    "details": {
        "message": "Detailed error message",
        "context": "Additional context"
    },
    "timestamp": "2024-01-01T12:00:00Z"
}
```

### Common Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `INVALID_COMMAND` | Command is invalid | 400 |
| `NO_WAKE_WORD` | Wake word not detected | 400 |
| `PRIVACY_VIOLATION` | Privacy policy violated | 403 |
| `RESOURCE_LIMIT` | Resource limit exceeded | 429 |
| `APP_NOT_FOUND` | Required app not found | 404 |
| `PERMISSION_DENIED` | Permission denied | 403 |
| `TIMEOUT` | Operation timed out | 408 |
| `INTERNAL_ERROR` | Internal server error | 500 |

## Rate Limiting

To prevent abuse, JARVIS implements rate limiting:

- **Command Rate Limit**: 10 commands per second
- **Task Rate Limit**: 3 concurrent tasks maximum
- **Network Rate Limit**: 10 requests per second per source
- **Learning Rate Limit**: 5 learning tasks per minute

## Authentication

For HTTP and WebSocket APIs, authentication can be enabled:

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer

app = FastAPI()
security = HTTPBearer()

@app.get("/secure")
async def secure_endpoint(token: str = Depends(security)):
    # Validate token
    if token != "valid_token":
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"message": "Access granted"}
```

## Versioning

JARVIS uses semantic versioning for its APIs:

- **Major Version**: Breaking changes
- **Minor Version**: Backward-compatible new features
- **Patch Version**: Backward-compatible bug fixes

API version is included in responses:

```json
{
    "api_version": "1.0.0",
    "jarvis_version": "1.0.0",
    "status": "success",
    "data": {...}
}
```

## Webhooks

JARVIS can send webhook notifications for important events:

```python
import httpx

async def send_webhook(url: str, event: str, data: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json={
                "event": event,
                "data": data,
                "timestamp": time.time(),
                "version": "1.0.0"
            },
            timeout=10.0
        )
        return response.status_code == 200
```

### Webhook Events

| Event | Description | Data |
|-------|-------------|------|
| `command_processed` | Command was processed | `command`, `result`, `processing_time` |
| `task_started` | Task execution started | `task_id`, `plan_id`, `intent` |
| `task_completed` | Task completed successfully | `task_id`, `result`, `execution_time` |
| `task_failed` | Task failed | `task_id`, `error`, `execution_time` |
| `learning_update` | Learning occurred | `source`, `knowledge`, `confidence` |
| `error` | Error occurred | `error`, `message`, `context` |
| `status_change` | System status changed | `old_status`, `new_status` |

## Best Practices

### 1. Command Design

- Use clear, natural language commands
- Include necessary context in commands
- Use wake word for hands-free operation
- Keep commands concise but descriptive

### 2. Error Handling

- Always check for errors in responses
- Handle different error types appropriately
- Provide user-friendly error messages
- Log errors for debugging

### 3. Performance

- Use async/await for I/O operations
- Batch similar operations together
- Cache frequent queries
- Limit concurrent operations

### 4. Security

- Validate all inputs
- Sanitize outputs
- Use HTTPS for remote connections
- Encrypt sensitive data
- Implement proper authentication

### 5. Testing

- Test all API endpoints
- Test error conditions
- Test edge cases
- Test performance under load

## Examples

### Complete Python Example

```python
import asyncio
from brain.main import JARVIS
from configs.config import Config

async def main():
    # Initialize JARVIS
    config = Config()
    jarvis = JARVIS(config)
    await jarvis.initialize()
    
    # Process a command
    result = await jarvis.process_command("Jarvis, upload video to YouTube", "text")
    print("Command result:", result)
    
    # Get preview
    preview = await jarvis.get_preview("upload video")
    print("Preview:", preview)
    
    # Execute command
    result = await jarvis.execute_direct("upload video")
    print("Execution result:", result)
    
    # Get status
    status = await jarvis.get_status()
    print("Status:", status)
    
    # Shutdown
    await jarvis.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

### Complete HTTP Client Example

```python
import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        # Process a command
        response = await client.post(
            "http://localhost:8000/command",
            json={
                "command": "Jarvis, upload video to YouTube",
                "input_type": "text"
            }
        )
        result = response.json()
        print("Command result:", result)
        
        # Get status
        response = await client.get("http://localhost:8000/status")
        status = response.json()
        print("Status:", status)
        
        # Get capabilities
        response = await client.get("http://localhost:8000/capabilities")
        capabilities = response.json()
        print("Capabilities:", capabilities)

if __name__ == "__main__":
    asyncio.run(main())
```

---

**JARVIS API Documentation**
