"""
TAB (Twin-Agent Bridge) - Secure orchestration system for multi-agent conversations.

This package provides a comprehensive framework for orchestrating secure conversations
between AI agents like Claude Code and Codex CLI, with full observability, policy
enforcement, and audit logging.
"""

__version__ = "1.0.0"
__author__ = "TAB Development Team"
__email__ = "dev@tab.example.com"

# Core components
from .models import *
from .services import *
from .lib import *

__all__ = [
    "models",
    "services",
    "lib",
    "cli"
]