"""
Output Generator Module
Generates human-readable and machine-readable output
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto

from ..utils.logger import Logger
from ..utils.error_handler import ErrorHandler


class OutputFormat(Enum):
    """Output format types"""
    TEXT = auto()
    JSON = auto()
    HTML = auto()
    MARKDOWN = auto()
    VOICE = auto()
    NOTIFICATION = auto()


class OutputType(Enum):
    """Output content types"""
    RESPONSE = auto()
    PREVIEW = auto()
    RESULT = auto()
    ERROR = auto()
    WARNING = auto()
    INFO = auto()
    DEBUG = auto()
    QUESTION = auto()
    CONFIRMATION = auto()
    PROGRESS = auto()


@dataclass
class OutputMessage:
    """Structured output message"""
    content: str
    output_type: OutputType = OutputType.RESPONSE
    format: OutputFormat = OutputFormat.TEXT
    data: Optional[Any] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "output_type": self.output_type.name,
            "format": self.format.name,
            "data": self.data,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    def to_text(self) -> str:
        """Convert to plain text"""
        return self.content
    
    def to_json(self) -> str:
        """Convert to JSON"""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_markdown(self) -> str:
        """Convert to Markdown format"""
        type_prefix = {
            OutputType.RESPONSE: "",
            OutputType.PREVIEW: "**Preview:** ",
            OutputType.RESULT: "**Result:** ",
            OutputType.ERROR: "**Error:** ",
            OutputType.WARNING: "**Warning:** ",
            OutputType.INFO: "**Info:** ",
            OutputType.DEBUG: "`",
            OutputType.QUESTION: "**Question:** ",
            OutputType.CONFIRMATION: "**Confirmation:** ",
            OutputType.PROGRESS: "**Progress:** "
        }
        
        prefix = type_prefix.get(self.output_type, "")
        suffix = type_prefix.get(self.output_type, "")
        
        if self.output_type == OutputType.DEBUG:
            return f"`{self.content}`"
        else:
            return f"{prefix}{self.content}{suffix}"
    
    def to_html(self) -> str:
        """Convert to HTML format"""
        type_class = {
            OutputType.RESPONSE: "response",
            OutputType.PREVIEW: "preview",
            OutputType.RESULT: "result",
            OutputType.ERROR: "error",
            OutputType.WARNING: "warning",
            OutputType.INFO: "info",
            OutputType.DEBUG: "debug",
            OutputType.QUESTION: "question",
            OutputType.CONFIRMATION: "confirmation",
            OutputType.PROGRESS: "progress"
        }
        
        css_class = type_class.get(self.output_type, "response")
        return f'<div class="{css_class}">{self.content}</div>'


class OutputGenerator:
    """
    Generates various types of output for the assistant
    """
    
    def __init__(self, config, logger: Logger):
        self.config = config
        self.logger = logger
        self.error_handler = ErrorHandler(logger)
        
        # Templates
        self._templates = self._load_templates()
        
        # State
        self._last_output: Optional[OutputMessage] = None
        self._output_history: List[OutputMessage] = []
        self._max_history = 100
        self._speak_bridge = None
    
    def _load_templates(self) -> Dict:
        """Load output templates"""
        return {
            "greeting": "Hello! I'm JARVIS, your AI assistant. How can I help you today?",
            "ready": "I'm ready and waiting for your commands.",
            "sleeping": "Goodbye! I'm going to sleep now. Wake me up when you need me.",
            "error": "I encountered an error: {error}",
            "not_understood": "I'm sorry, I didn't understand that. Could you please rephrase?",
            "wake_word_help": "You can wake me up by saying '{wake_word}' followed by your command.",
            "capabilities": "I can help you with many tasks including:\n\n" +
                          "- Answering questions\n" +
                          "- Searching the web\n" +
                          "- Managing files\n" +
                          "- Taking screenshots\n" +
                          "- Extracting text from images\n" +
                          "- Uploading videos\n" +
                          "- Editing photos and videos\n" +
                          "- And much more!\n\n" +
                          "Just ask me what you need.",
            "privacy_notice": "Your privacy is important. I only process information you explicitly provide " +
                             "and never share your data without permission.",
            "learning_notice": "I'm learning from our interactions to better assist you in the future."
        }
    
    def generate(self, content: str, 
                output_type: OutputType = OutputType.RESPONSE,
                format: OutputFormat = OutputFormat.TEXT,
                data: Optional[Any] = None,
                metadata: Optional[Dict] = None) -> OutputMessage:
        """
        Generate an output message
        
        Args:
            content: The main content of the message
            output_type: Type of output
            format: Output format
            data: Additional data to include
            metadata: Additional metadata
            
        Returns:
            OutputMessage
        """
        message = OutputMessage(
            content=content,
            output_type=output_type,
            format=format,
            data=data,
            metadata=metadata or {}
        )
        
        # Add to history
        self._add_to_history(message)
        self._last_output = message
        
        # Log output
        self.logger.debug(f"Generated output: {output_type.name} - {content[:50]}...")
        
        return message
    
    def generate_response(self, text: str, data: Optional[Any] = None) -> OutputMessage:
        """Generate a response message"""
        return self.generate(text, OutputType.RESPONSE, OutputFormat.TEXT, data)
    
    def generate_preview(self, text: str, data: Optional[Any] = None) -> OutputMessage:
        """Generate a preview message"""
        return self.generate(text, OutputType.PREVIEW, OutputFormat.TEXT, data)
    
    def generate_result(self, text: str, data: Optional[Any] = None) -> OutputMessage:
        """Generate a result message"""
        return self.generate(text, OutputType.RESULT, OutputFormat.TEXT, data)
    
    def generate_error(self, text: str, error: Optional[str] = None) -> OutputMessage:
        """Generate an error message"""
        return self.generate(
            text, 
            OutputType.ERROR, 
            OutputFormat.TEXT, 
            {"error": error} if error else None
        )
    
    def generate_warning(self, text: str) -> OutputMessage:
        """Generate a warning message"""
        return self.generate(text, OutputType.WARNING)
    
    def generate_info(self, text: str) -> OutputMessage:
        """Generate an info message"""
        return self.generate(text, OutputType.INFO)
    
    def generate_question(self, text: str) -> OutputMessage:
        """Generate a question message"""
        return self.generate(text, OutputType.QUESTION)
    
    def generate_confirmation(self, text: str) -> OutputMessage:
        """Generate a confirmation message"""
        return self.generate(text, OutputType.CONFIRMATION)
    
    def generate_progress(self, text: str, progress: float = 0.0) -> OutputMessage:
        """Generate a progress message"""
        return self.generate(
            text, 
            OutputType.PROGRESS, 
            OutputFormat.TEXT,
            {"progress": progress}
        )
    
    def generate_from_template(self, template_name: str, 
                             replacements: Dict = None) -> Optional[OutputMessage]:
        """
        Generate output from a template
        
        Args:
            template_name: Name of the template
            replacements: Dictionary of replacements to make
            
        Returns:
            OutputMessage or None if template not found
        """
        if template_name not in self._templates:
            return None
        
        template = self._templates[template_name]
        
        if replacements:
            for key, value in replacements.items():
                template = template.replace(f"{{{key}}}", str(value))
        
        return self.generate(template, OutputType.RESPONSE)
    
    def format_command_preview(self, command: str, plan: Dict) -> str:
        """
        Format a command preview for user confirmation
        
        Args:
            command: The original command
            plan: The execution plan
            
        Returns:
            Formatted preview string
        """
        intent = plan.get("intent", "unknown")
        steps = plan.get("steps", [])
        complexity = plan.get("complexity", "low")
        missing = plan.get("missing_requirements", [])
        
        preview = f"**Command:** {command}\n\n"
        preview += f"**Intent:** {intent}\n\n"
        preview += f"**Complexity:** {complexity}\n\n"
        
        if missing:
            preview += f"**Missing Requirements:**\n"
            for req in missing:
                preview += f"  - {req}\n"
            preview += "\n"
        
        preview += "**Execution Plan:**\n"
        for i, step in enumerate(steps, 1):
            preview += f"  {i}. {step.get('description', step.get('action', 'Unknown'))}\n"
        
        preview += "\n**Execute this plan?** (yes/no/edit)"
        
        return preview
    
    def format_execution_result(self, result: Dict) -> str:
        """
        Format an execution result for display
        
        Args:
            result: The execution result
            
        Returns:
            Formatted result string
        """
        status = result.get("status", "unknown")
        final_output = result.get("final_output", {})
        processing_time = result.get("processing_time", 0)
        confidence = result.get("confidence", 0)
        
        output = f"**Status:** {status}\n\n"
        
        if processing_time:
            output += f"**Time:** {processing_time:.2f} seconds\n\n"
        
        if confidence:
            output += f"**Confidence:** {confidence*100:.1f}%\n\n"
        
        if final_output:
            if isinstance(final_output, dict):
                output += "**Output:**\n"
                for key, value in final_output.items():
                    output += f"  - {key}: {value}\n"
            else:
                output += f"**Output:** {final_output}\n"
        
        return output
    
    def format_task_progress(self, current_step: int, total_steps: int,
                           current_description: str = "") -> str:
        """
        Format task progress for display
        
        Args:
            current_step: Current step number
            total_steps: Total number of steps
            current_description: Description of current step
            
        Returns:
            Formatted progress string
        """
        progress = (current_step / total_steps) * 100 if total_steps > 0 else 0
        
        bar_length = 30
        filled = int(bar_length * current_step / total_steps)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        output = f"**Progress:** [{bar}] {progress:.1f}%\n"
        output += f"**Step {current_step} of {total_steps}:** {current_description}\n"
        
        return output
    
    def format_multi_source_result(self, results: Dict[str, Any]) -> str:
        """
        Format results from multiple sources
        
        Args:
            results: Dictionary of source -> result
            
        Returns:
            Formatted multi-source result string
        """
        output = "**Results from multiple sources:**\n\n"
        
        for source, data in results.items():
            output += f"**{source}:**\n"
            
            if isinstance(data, dict):
                for key, value in data.items():
                    output += f"  - {key}: {value}\n"
            else:
                output += f"  - {data}\n"
            
            output += "\n"
        
        return output
    
    def format_knowledge_merge(self, sources: List[str], 
                           merged_text: str, 
                           confidence: float) -> str:
        """
        Format merged knowledge from multiple sources
        
        Args:
            sources: List of source names
            merged_text: The merged text
            confidence: Confidence score
            
        Returns:
            Formatted knowledge merge string
        """
        output = f"**Knowledge Merged from {len(sources)} sources**\n\n"
        output += f"**Sources:** {', '.join(sources)}\n\n"
        output += f"**Confidence:** {confidence*100:.1f}%\n\n"
        output += "**Merged Information:**\n"
        output += merged_text
        
        return output
    
    def format_error_details(self, error: Exception) -> str:
        """
        Format error details for display
        
        Args:
            error: The exception
            
        Returns:
            Formatted error details string
        """
        import traceback
        
        output = f"**Error:** {str(error)}\n\n"
        output += f"**Type:** {type(error).__name__}\n\n"
        output += "**Traceback:**\n"
        output += "\n".join(traceback.format_exc().split('\n'))
        
        return output
    
    def format_decision_explanation(self, decision: Dict) -> str:
        """
        Format a decision explanation
        
        Args:
            decision: Decision data
            
        Returns:
            Formatted decision explanation string
        """
        action = decision.get("action", "unknown")
        confidence = decision.get("confidence", 0)
        reason = decision.get("reason", "")
        alternatives = decision.get("alternatives", [])
        required_info = decision.get("required_info", [])
        
        output = f"**Decision:** {action}\n\n"
        output += f"**Confidence:** {confidence*100:.1f}%\n\n"
        
        if reason:
            output += f"**Reason:** {reason}\n\n"
        
        if required_info:
            output += "**Required Information:**\n"
            for info in required_info:
                output += f"  - {info}\n"
            output += "\n"
        
        if alternatives:
            output += "**Alternatives:**\n"
            for alt in alternatives:
                output += f"  - {alt}\n"
        
        return output
    
    def format_learning_update(self, feedback: Dict) -> str:
        """
        Format a learning update
        
        Args:
            feedback: Learning feedback data
            
        Returns:
            Formatted learning update string
        """
        output = "**Learning Update**\n\n"
        
        for key, value in feedback.items():
            output += f"**{key.replace('_', ' ').title()}:** {value}\n"
        
        return output
    
    def format_resource_usage(self, usage: Dict) -> str:
        """
        Format resource usage information
        
        Args:
            usage: Resource usage data
            
        Returns:
            Formatted resource usage string
        """
        output = "**Resource Usage**\n\n"
        
        for key, value in usage.items():
            if isinstance(value, float):
                output += f"**{key.replace('_', ' ').title()}:** {value:.2f}\n"
            else:
                output += f"**{key.replace('_', ' ').title()}:** {value}\n"
        
        return output
    
    def format_notification(self, title: str, message: str, 
                          priority: str = "normal") -> str:
        """
        Format a notification message
        
        Args:
            title: Notification title
            message: Notification message
            priority: Priority level
            
        Returns:
            Formatted notification string
        """
        priority_icons = {
            "low": "ℹ️",
            "normal": "📢",
            "high": "⚠️",
            "critical": "🚨"
        }
        
        icon = priority_icons.get(priority, "📢")
        
        return f"{icon} **{title}**\n{message}"
    
    def format_voice_response(self, text: str) -> str:
        """
        Format text for voice output
        
        Args:
            text: Text to convert to voice
            
        Returns:
            Text formatted for voice output
        """
        # Remove markdown formatting
        voice_text = text
        voice_text = voice_text.replace("**", "")
        voice_text = voice_text.replace("*", "")
        voice_text = voice_text.replace("_", "")
        voice_text = voice_text.replace("`", "")
        voice_text = voice_text.replace("\n", " ")
        voice_text = voice_text.replace("  ", " ")
        
        # Add pauses for better voice output
        voice_text = voice_text.replace(".", ". Pause. ")
        voice_text = voice_text.replace("!", "! Pause. ")
        voice_text = voice_text.replace("?", "? Pause. ")
        
        return voice_text.strip()
    
    def generate_command_summary(self, command: str, result: Dict) -> str:
        """
        Generate a summary of a command execution
        
        Args:
            command: The original command
            result: The execution result
           
        Returns:

            Command summary string
        """
        status = result.get("status", "unknown")
        processing_time = result.get("processing_time", 0)
        confidence = result.get("confidence", 0)
        
        summary = f"**Command:** {command}\n"
        summary += f"**Status:** {status}\n"
        summary += f"**Time:** {processing_time:.2f}s\n"
        summary += f"**Confidence:** {confidence*100:.1f}%\n"
        
        if status == "success" and "result" in result:
            summary += "**Result:** Success\n"
        elif status == "error" and "error" in result:
            summary += f"**Error:** {result['error']}\n"
        
        return summary
    
    # History Methods
    
    def _add_to_history(self, message: OutputMessage):
        """Add message to history"""
        self._output_history.append(message)
        if len(self._output_history) > self._max_history:
            self._output_history = self._output_history[-self._max_history:]
    
    def get_history(self, count: int = 10) -> List[OutputMessage]:
        """Get recent output history"""
        return self._output_history[-count:]
    
    def get_last_output(self) -> Optional[OutputMessage]:
        """Get the last output message"""
        return self._last_output
    
    def clear_history(self):
        """Clear output history"""
        self._output_history = []
        self._last_output = None
    
    # Template Management
    
    def add_template(self, name: str, template: str) -> bool:
        """Add a new template"""
        if name in self._templates:
            return False
        
        self._templates[name] = template
        self.logger.info(f"Template added: {name}")
        return True
    
    def remove_template(self, name: str) -> bool:
        """Remove a template"""
        if name not in self._templates:
            return False
        
        del self._templates[name]
        self.logger.info(f"Template removed: {name}")
       return True
    

    def get_template(self, name: str) -> Optional[str]:
        """Get a template"""
        return self._templates.get(name)
    
    def get_all_templates(self) -> Dict[str, str]:
        """Get all templates"""
        return self._templates.copy()
    
    # Format Conversion
    
    def convert_format(self, message: OutputMessage, 
                      target_format: OutputFormat) -> str:
        """
        Convert a message to a specific format
        
        Args:
            message: The output message
            target_format: The target format
            
        Returns:
            Formatted string
        """
        if target_format == OutputFormat.TEXT:
            return message.to_text()
        elif target_format == OutputFormat.JSON:
            return message.to_json()
        elif target_format == OutputFormat.MARKDOWN:
            return message.to_markdown()
        elif target_format == OutputFormat.HTML:
            return message.to_html()
        elif target_format == OutputFormat.VOICE:
            return self.format_voice_response(message.content)
        elif target_format == OutputFormat.NOTIFICATION:
            return self.format_notification(
                message.output_type.name,
                message.content
            )
        else:
            return message.content
    
    # Streaming voice output (sentence-level TTS via the Bridge APK)
    
    def _get_bridge(self):
        """Lazily create the bridge client used for speaking."""
        if self._speak_bridge is None:
            from .bridge_client import BridgeClient
            bridge_cfg = getattr(self.config, 'bridge', None)
            self._speak_bridge = BridgeClient(
                host=getattr(bridge_cfg, 'host', '127.0.0.1'),
                port=getattr(bridge_cfg, 'port', 8080),
            )
        return self._speak_bridge
    
    async def speak(self, text: str, language: str = "ur-PK") -> Dict:
        """
        Speak text through the Bridge APK with sentence-level streaming:
        the APK queues the first sentence immediately and keeps appending
        the remaining sentences, so playback starts at once. Returns the
        bridge result dict with the language actually used.
        """
        if not text or not text.strip():
            return {"ok": False, "error": "empty text"}
        try:
            bridge = self._get_bridge()
            result = await bridge.tts_speak(text.strip(), language)
            if isinstance(result, dict) and result.get("ok"):
                self.logger.info(
                    f"Streaming TTS started (language={result.get('language')}, "
                    f"queued={result.get('queued')})")
            return result if isinstance(result, dict) else {"ok": False, "error": "invalid bridge result"}
        except Exception as e:
            self.error_handler.handle_error(e, "speak")
            return {"ok": False, "error": str(e)}
    
    async def speak_wait(self, text: str, language: str = "ur-PK",
                        timeout_s: float = 120.0) -> bool:
        """Speak and wait until the APK finishes playing."""
        result = await self.speak(text, language)
        if not result.get("ok"):
            return False
        bridge = self._get_bridge()
        deadline = time.time() + float(timeout_s)
        while time.time() < deadline:
            try:
                status = await bridge.tts_status()
                if isinstance(status, dict) and status.get("done"):
                    return True
            except Exception:
                return False
            await asyncio.sleep(0.3)
        return False
    
    async def stop_speaking(self) -> bool:
        """Stop the current TTS playback."""
        try:
            if self._speak_bridge is not None:
                await self._speak_bridge.tts_stop()
                return True
        except Exception as e:
            self.error_handler.handle_error(e, "stop_speaking")
        return False
    
    # Cleanup
    
    async def cleanup(self):
        """Clean up resources"""
        if self._speak_bridge is not None:
            try:
                await self._speak_bridge.close()
            except Exception:
                pass
            self._speak_bridge = None
        self._output_history = []
        self._last_output = None
        self.logger.info("Output Generator cleaned up")

