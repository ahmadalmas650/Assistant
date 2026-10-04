# Screen Vision (Live Accessibility Only)

## Design decision

The assistant reads the screen exclusively through the Android
accessibility node tree. There is no screenshot pipeline and no OCR.

| Aspect | Value |
|---|---|
| Method | Live accessibility nodes (get_all_nodes with refresh) |
| Speed | ~0.1 s |
| Confidence | 0.99 (direct from the system API) |
| RAM | ~10 MB |
| Failure mode | Honest error string; the brain reports the real technical reason and never invents one |

## Python side: brain/modules/ocr_engine.py

Public API:

- extract_text_from_screen() -> OCRResult - all visible text, deduplicated, in reading order
- extract_live_text() -> str - quick string form
- extract_elements_async() -> List[str] - unique text elements
- find_text(needle) -> node or None - first node matching visible text (case-insensitive)
- find_all_text(needle) -> List of nodes - all matching nodes
- collect_nodes(refresh=True) - raw node list from the bridge
- OCRResult.to_dict() - JSON-ready payload

The engine probes the accessibility controller at runtime for whichever API
it exposes (get_all_nodes, get_screen_nodes, get_visible_nodes, dump_nodes,
or a nodes property), so it works with any bridge revision.

## Bridge protocol (fast path: localhost JSON-RPC 2.0)

com.assistant.bridge.service.LocalJsonRpcServer is a dependency-free,
localhost-only TCP server:

- Binds to 127.0.0.1 only - never reachable from the network.
- No external Java libraries, so no gradle dependency changes are needed.
- One JSON-RPC 2.0 object per line so the Python brain in Termux can use
  plain sockets.

Wire format:

    request:  {"jsonrpc":"2.0","id":1,"method":"ping","params":{}}
    response: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}
    error:    {"jsonrpc":"2.0","id":1,"error":{"code":-32000,"message":"..."}}

Suggested method surface (implemented by the foreground service handler):
ping, get_screen_text, get_all_nodes, click_node, input_text, launch_app,
notification_info.

## Building the APK inside Termux (3 GB RAM device)

    pkg update && pkg upgrade
    pkg install openjdk-17 git
    bash scripts/setup_termux.sh
    bash scripts/build_bridge.sh

Low-RAM build notes: org.gradle.jvmargs=-Xmx1024m, parallel builds off,
caching on, single ABI (arm64-v8a).

## API keys policy

Real API keys are never committed. configs/api_keys.local.example.json is
the template; the real configs/api_keys.local.json stays on the phone and
must be listed in .gitignore. The assistant is designed to work with no LLM
API at all: learning happens through installed apps via accessibility.
