"""
JARVIS AI Brain Module
Core intelligence engine for Android AI Assistant
"""

from .core import (
    BrainEngine,
    DecisionMaker,
    ConfidenceEngine,
    TaskPlanner,
    ExecutionController
)

from .modules import (
    InputProcessor,
    OutputGenerator,
    CommandParser,
    WakeWordDetector
)

from .learning import (
    MultiSourceLearner,
    KnowledgeMerger,
    InformationComparator,
    LearningManager
)

from .memory import (
    MemoryManager,
    LocalMemory,
    CloudMemory,
    KnowledgeBase
)

from .tasks import (
    TaskManager,
    PreviewSystem,
    LiveControlSystem
)

from .utils import (
    Logger,
    ResourceMonitor,
    ErrorHandler,
    PrivacyGuard,
    CloudSync
)

__version__ = "1.0.0"
__author__ = "ahmadalmas650"
__license__ = "MIT"

# Initialize core components
def initialize_brain():
    """Initialize the complete brain system"""
    from .core.brain_engine import BrainEngine
    return BrainEngine()

# Quick access to main components
brain = None

async def get_brain():
    """Get or create brain instance"""
    global brain
    if brain is None:
        brain = initialize_brain()
    return brain
