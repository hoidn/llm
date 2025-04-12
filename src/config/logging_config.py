"""Logging configuration for the application."""
import logging
import sys
import os
from typing import Optional

def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Configure logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, logs to stdout.
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure basic logging
    config = {
        'level': numeric_level,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    }
    
    # Add file handler if log_file is specified
    if log_file:
        # Ensure directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        config['filename'] = log_file
    else:
        # Log to stdout if no file specified
        config['stream'] = sys.stdout
    
    # Apply configuration
    logging.basicConfig(**config)
    
    # Set specific levels for noisy libraries if needed
    # logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    # Log startup message
    logging.info("Logging initialized at %s level", level.upper())

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name, typically __name__ from the calling module
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
