"""
Modular Prompt Builder

Composes prompts dynamically based on query requirements.
Only loads extensions that are actually needed, keeping prompts small and efficient.
"""

from typing import List, Optional
from PEERS_RAG_prompts.base_prompt import BASE_PROMPT
from PEERS_RAG_prompts.extensions import EXTENSION_REGISTRY


class ModularPromptBuilder:
    """
    Builds prompts by composing base prompt with only needed extensions
    
    This approach:
    - Keeps prompts small (only load what's needed)
    - Prevents prompt bloat as new use cases are added
    - Makes it easy to add new extensions without affecting existing ones
    - Provides clear debugging information
    """
    
    def __init__(self, log_manager=None):
        """
        Initialize prompt builder
        
        Args:
            log_manager: Optional log manager for debugging
        """
        self.log_manager = log_manager
        self.base_prompt = BASE_PROMPT
    
    def build(self, extensions: List[str]) -> str:
        """
        Build prompt from base + specified extensions
        
        Args:
            extensions: List of extension keys to include
            
        Returns:
            Composed prompt string
        """
        prompt = self.base_prompt
        
        loaded_extensions = []
        
        for ext_key in extensions:
            if ext_key in EXTENSION_REGISTRY:
                extension_text = EXTENSION_REGISTRY[ext_key]
                prompt += "\n\n" + extension_text
                loaded_extensions.append(ext_key)
            else:
                # Warn about missing extension (for debugging)
                if self.log_manager:
                    self.log_manager.add_error_log(
                        f'Warning: Extension "{ext_key}" not found in registry. Skipping.'
                    )
        
        # Log what was loaded for debugging
        if self.log_manager and loaded_extensions:
            self.log_manager.add_info_log(
                f'Prompt Builder: Loaded extensions -> {", ".join(loaded_extensions)}'
            )
        elif self.log_manager:
            self.log_manager.add_info_log('Prompt Builder: Using base prompt only (no extensions)')
        
        return prompt
    
    def build_for_query_type(self, query_analysis: dict) -> str:
        """
        Build prompt based on query analysis dictionary
        
        Args:
            query_analysis: Dictionary from QueryAnalyzer.analyze()
            
        Returns:
            Composed prompt string
        """
        extensions = []
        
        if query_analysis.get('needs_parameters', False):
            extensions.append('parameter_query')
        
        if query_analysis.get('needs_periods', False):
            extensions.append('period_handling')
        
        if query_analysis.get('needs_comparison', False):
            extensions.append('comparison_query')
        
        if query_analysis.get('needs_multi_period', False) or query_analysis.get('needs_trend', False):
            extensions.append('multi_period')
        
        return self.build(extensions)
    
    def estimate_token_count(self, prompt: str) -> int:
        """
        Rough estimate of token count (for monitoring/debugging)
        
        Args:
            prompt: Prompt string
            
        Returns:
            Estimated token count (rough approximation: 1 token ≈ 4 characters)
        """
        return len(prompt) // 4
    
    def get_available_extensions(self) -> List[str]:
        """Get list of all available extension keys"""
        return list(EXTENSION_REGISTRY.keys())

