from .web_search import WebSearchTool
from .file_ops import FileOperationsTool
from .code_exec import CodeExecutionTool

# Tool registry
_TOOL_REGISTRY = {
    "web_search": WebSearchTool(),
    "file_ops": FileOperationsTool(),
    "code_exec": CodeExecutionTool()
}


def get_tool_by_name(tool_name: str):
    """Get a tool instance by name"""
    return _TOOL_REGISTRY.get(tool_name)


def get_available_tools():
    """Get list of all available tools"""
    return list(_TOOL_REGISTRY.keys())


def register_tool(name: str, tool_instance):
    """Register a new tool"""
    _TOOL_REGISTRY[name] = tool_instance


__all__ = [
    "WebSearchTool",
    "FileOperationsTool", 
    "CodeExecutionTool",
    "get_tool_by_name",
    "get_available_tools",
    "register_tool"
]
