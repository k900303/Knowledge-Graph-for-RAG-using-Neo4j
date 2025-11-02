"""
PEERS RAG Modular Prompt System

This package provides a modular, scalable prompt architecture that:
- Composes prompts dynamically based on query needs
- Avoids prompt bloat by loading only relevant extensions
- Makes it easy to add new use cases without affecting existing ones
- Provides clear debugging and logging capabilities
"""

from PEERS_RAG_prompts.prompt_builder import ModularPromptBuilder
from PEERS_RAG_prompts.query_analyzer import QueryAnalyzer

__all__ = ['ModularPromptBuilder', 'QueryAnalyzer']

