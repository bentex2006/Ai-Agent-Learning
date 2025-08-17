import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from config import settings


def setup_logger(name: str = "mcp_agent", level: Optional[str] = None) -> logging.Logger:
    """
    Set up a logger with console and file handlers.
    
    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger instance
    """
    
    # Determine log level
    log_level = level or settings.log_level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if storage path is available)
    try:
        log_dir = Path(settings.memory_storage_path) / "logs"
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file
        
        # More detailed format for file
        file_formatter = logging.Formatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
    except Exception as e:
        # If file logging fails, continue with console only
        logger.warning(f"Could not setup file logging: {e}")
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name, defaults to calling module name
        
    Returns:
        Logger instance
    """
    
    if name is None:
        # Get the calling module name
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back:
            module = inspect.getmodule(frame.f_back)
            if module:
                name = module.__name__
            else:
                name = "mcp_agent"
        else:
            name = "mcp_agent"
    
    # Return existing logger or create new one
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # Logger doesn't exist, set it up
        return setup_logger(name)
    
    return logger


class AgentLogger:
    """
    Specialized logger for agent operations with context tracking.
    """
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.logger = get_logger(f"agent.{agent_name}")
        self.context = {}
    
    def set_context(self, **kwargs):
        """Set context information for logging"""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Clear context information"""
        self.context.clear()
    
    def _format_message(self, message: str) -> str:
        """Format message with context"""
        if self.context:
            context_str = " | ".join([f"{k}={v}" for k, v in self.context.items()])
            return f"[{context_str}] {message}"
        return message
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        if kwargs:
            self.set_context(**kwargs)
        self.logger.debug(self._format_message(message))
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        if kwargs:
            self.set_context(**kwargs)
        self.logger.info(self._format_message(message))
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        if kwargs:
            self.set_context(**kwargs)
        self.logger.warning(self._format_message(message))
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        if kwargs:
            self.set_context(**kwargs)
        self.logger.error(self._format_message(message))
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        if kwargs:
            self.set_context(**kwargs)
        self.logger.critical(self._format_message(message))
    
    def log_agent_action(self, action: str, details: Optional[dict] = None, success: bool = True):
        """Log agent action with structured information"""
        level = "info" if success else "warning"
        message = f"Agent action: {action}"
        
        context = {"action": action, "success": success}
        if details:
            context.update(details)
        
        self.set_context(**context)
        getattr(self.logger, level)(self._format_message(message))
    
    def log_tool_usage(self, tool_name: str, operation: str, result: dict):
        """Log tool usage"""
        success = "error" not in result
        message = f"Tool usage: {tool_name}.{operation}"
        
        self.set_context(
            tool=tool_name,
            operation=operation,
            success=success,
            result_size=len(str(result))
        )
        
        level = "info" if success else "warning"
        getattr(self.logger, level)(self._format_message(message))
    
    def log_llm_call(self, model: str, tokens_used: Optional[int] = None, response_time: Optional[float] = None):
        """Log LLM API call"""
        message = f"LLM call: {model}"
        
        context = {"model": model}
        if tokens_used:
            context["tokens"] = tokens_used
        if response_time:
            context["response_time"] = f"{response_time:.2f}s"
        
        self.set_context(**context)
        self.logger.info(self._format_message(message))
    
    def log_error_with_context(self, error: Exception, context_info: Optional[dict] = None):
        """Log error with additional context"""
        message = f"Error: {type(error).__name__}: {str(error)}"
        
        error_context = {
            "error_type": type(error).__name__,
            "agent": self.agent_name
        }
        
        if context_info:
            error_context.update(context_info)
        
        self.set_context(**error_context)
        self.logger.error(self._format_message(message))


class PerformanceLogger:
    """
    Logger for performance monitoring and metrics.
    """
    
    def __init__(self):
        self.logger = get_logger("performance")
        self.metrics = {}
    
    def start_timer(self, operation: str):
        """Start timing an operation"""
        import time
        self.metrics[operation] = {"start_time": time.time()}
    
    def end_timer(self, operation: str, additional_info: Optional[dict] = None):
        """End timing an operation and log the result"""
        import time
        
        if operation not in self.metrics:
            self.logger.warning(f"Timer for operation '{operation}' was not started")
            return
        
        end_time = time.time()
        duration = end_time - self.metrics[operation]["start_time"]
        
        log_data = {
            "operation": operation,
            "duration": f"{duration:.3f}s"
        }
        
        if additional_info:
            log_data.update(additional_info)
        
        # Format log message
        log_msg = f"Performance: {operation} completed in {duration:.3f}s"
        if additional_info:
            log_msg += f" | {' | '.join([f'{k}={v}' for k, v in additional_info.items()])}"
        
        # Log at different levels based on duration
        if duration > 10:  # > 10 seconds
            self.logger.warning(log_msg)
        elif duration > 5:  # > 5 seconds
            self.logger.info(log_msg)
        else:
            self.logger.debug(log_msg)
        
        # Clean up
        del self.metrics[operation]
    
    def log_metric(self, metric_name: str, value: float, unit: Optional[str] = None):
        """Log a performance metric"""
        message = f"Metric: {metric_name} = {value}"
        if unit:
            message += f" {unit}"
        
        self.logger.info(message)
    
    def log_memory_usage(self):
        """Log current memory usage"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            self.log_metric("memory_rss", memory_info.rss / 1024 / 1024, "MB")
            self.log_metric("memory_vms", memory_info.vms / 1024 / 1024, "MB")
            
        except ImportError:
            self.logger.debug("psutil not available for memory monitoring")
        except Exception as e:
            self.logger.warning(f"Could not log memory usage: {e}")


# Global performance logger instance
performance_logger = PerformanceLogger()


def log_performance(operation_name: str):
    """
    Decorator for logging performance of functions.
    
    Usage:
        @log_performance("my_operation")
        def my_function():
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            performance_logger.start_timer(operation_name)
            try:
                result = func(*args, **kwargs)
                performance_logger.end_timer(operation_name, {"success": True})
                return result
            except Exception as e:
                performance_logger.end_timer(operation_name, {"success": False, "error": str(e)})
                raise
        return wrapper
    return decorator


async def alog_performance(operation_name: str):
    """
    Async decorator for logging performance of async functions.
    
    Usage:
        @alog_performance("my_async_operation")
        async def my_async_function():
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            performance_logger.start_timer(operation_name)
            try:
                result = await func(*args, **kwargs)
                performance_logger.end_timer(operation_name, {"success": True})
                return result
            except Exception as e:
                performance_logger.end_timer(operation_name, {"success": False, "error": str(e)})
                raise
        return wrapper
    return decorator
