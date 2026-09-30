"""
Learning Module
"""

from .multi_source_learner import MultiSourceLearner
from .knowledge_merger import KnowledgeMerger
from .information_comparator import InformationComparator
from .learning_manager import LearningManager

__all__ = [
    'MultiSourceLearner',
    'KnowledgeMerger',
    'InformationComparator',
    'LearningManager'
]
