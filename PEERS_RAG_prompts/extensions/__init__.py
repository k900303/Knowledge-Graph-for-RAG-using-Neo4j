"""
Prompt Extensions

This module contains domain-specific prompt extensions that can be
dynamically loaded based on query requirements.
"""

from PEERS_RAG_prompts.extensions.parameter_query import PARAMETER_QUERY_EXTENSION
from PEERS_RAG_prompts.extensions.period_handling import PERIOD_HANDLING_EXTENSION
from PEERS_RAG_prompts.extensions.comparison_query import COMPARISON_QUERY_EXTENSION
from PEERS_RAG_prompts.extensions.multi_period import MULTI_PERIOD_EXTENSION

__all__ = [
    'PARAMETER_QUERY_EXTENSION',
    'PERIOD_HANDLING_EXTENSION',
    'COMPARISON_QUERY_EXTENSION',
    'MULTI_PERIOD_EXTENSION'
]

# Registry of all extensions (for easy addition of new ones)
EXTENSION_REGISTRY = {
    'parameter_query': PARAMETER_QUERY_EXTENSION,
    'period_handling': PERIOD_HANDLING_EXTENSION,
    'comparison_query': COMPARISON_QUERY_EXTENSION,
    'multi_period': MULTI_PERIOD_EXTENSION,
}

