import asyncio
import json
import os
import sys
import tempfile
import subprocess
import signal
from pathlib import Path
from typing import Dict, Any, List, Optional
import shlex
from datetime import datetime, timedelta

from config import settings


class CodeExecutionTool:
    """Tool for safe code execution with sandboxing and timeouts"""
    
    def __init__(self):
        self.name = "code_exec"
        self.description = "Execute code safely with timeouts and sandboxing"
        self.keywords = ["execute", "run", "code", "script", "test", "compile"]
        
        # Execution settings
        self.safe_mode = settings.safe_mode
        self.timeout = 30  # seconds
        self.max_output_size = 10 * 1024  # 10KB max output
        
        # Supported languages
        self.supported_languages = {
            "python": {
                "extensions": [".py"],
                "command": [sys.executable],
                "repl_available": True
            },
            "javascript": {
                "extensions": [".js"],
                "command": ["node"],
                "repl_available": True
            },
            "bash": {
                "extensions": [".sh"],
                "command": ["/bin/bash"],
                "repl_available": False
            },
            "shell": {
                "extensions": [".sh"],
                "command": ["/bin/sh"],
                "repl_available": False
            }
        }
        
        # Security restrictions
        self.blocked_imports = {
            "python": ["os", "subprocess", "sys", "shutil", "glob", "socket", "urllib", "requests"],
            "javascript": ["fs", "child_process", "net", "http", "https", "cluster"],
            "bash": ["rm", "sudo", "chmod", "chown", "wget", "curl"]
        }
        
        # Temp directory for code execution
        self.temp_dir = Path(tempfile.gettempdir()) / "mcp_code_exec"
        self.temp_dir.mkdir(exist_ok=True)
    
    async def execute(self, code: str, language: str = "python", 
                     timeout: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Execute code safely
        
        Args:
            code: Code to execute
            language: Programming language
            timeout: Execution timeout in seconds
            **kwargs: Additional execution parameters
            
        Returns:
            Dictionary with execution results
        """
        
        try:
            # Validate language
            if language not in self.supported_languages:
                return {"error": f"Unsupported language: {language}"}
            
            # Validate and sanitize code
            validation_result = self._validate_code(code, language)
            if validation_result["blocked"]:
                return {
                    "error": f"Code blocked for security reasons: {validation_result['reason']}",
                    "blocked_items": validation_result["blocked_items"]
                }
            
            # Set execution timeout
            exec_timeout = timeout or self.timeout
            
            # Execute code based on language
            if language == "python":
                return await self._execute_python(code, exec_timeout)
            elif language == "javascript":
                return await self._execute_javascript(code, exec_timeout)
            elif language in ["bash", "shell"]:
                return await self._execute_shell(code, exec_timeout, language)
            else:
                return {"error": f"Execution not implemented for {language}"}
                
        except Exception as e:
            return {"error": f"Code execution failed: {str(e)}"}
    
    def _validate_code(self, code: str, language: str) -> Dict[str, Any]:
        """Validate code for security issues"""
        
        blocked_items = []
        code_lower = code.lower()
        
        # Check for blocked imports/commands
        if language in self.blocked_imports:
            for blocked_item in self.blocked_imports[language]:
                if blocked_item in code_lower:
                    blocked_items.append(blocked_item)
        
        # Check for dangerous patterns
        dangerous_patterns = [
            "eval(", "exec(", "__import__", "open(", "file(", "input(",
            "raw_input(", "reload(", "compile(", "globals(", "locals()",
            "system(", "popen(", "spawn(", "call(", "check_output("
        ]
        
        for pattern in dangerous_patterns:
            if pattern in code_lower:
                blocked_items.append(pattern)
        
        # Check for file system access
        fs_patterns = ["open(", "with open", "file(", "pathlib", "tempfile"]
        for pattern in fs_patterns:
            if pattern in code_lower:
                blocked_items.append(f"file_access:{pattern}")
        
        # Check for network access
        network_patterns = ["socket", "urllib", "requests", "http", "ftp", "ssh"]
        for pattern in network_patterns:
            if pattern in code_lower:
                blocked_items.append(f"network_access:{pattern}")
        
        blocked = len(blocked_items) > 0 and self.safe_mode
        
        return {
            "blocked": blocked,
            "blocked_items": blocked_items,
            "reason": "Potentially unsafe operations detected" if blocked else None
        }
    
    async def _execute_python(self, code: str, timeout: int) -> Dict[str, Any]:
        """Execute Python code"""
        
        try:
            # Create a safe execution environment
            safe_code = self._create_safe_python_wrapper(code)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', 
                                           dir=self.temp_dir, delete=False) as f:
                f.write(safe_code)
                temp_file = f.name
            
            try:
                # Execute code
                process = await asyncio.create_subprocess_exec(
                    sys.executable, temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.temp_dir
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=timeout
                    )
                    
                    return_code = process.returncode
                    
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    return {
                        "error": "Code execution timed out",
                        "timeout": timeout,
                        "language": "python"
                    }
                
                # Decode output
                stdout_text = stdout.decode('utf-8', errors='replace')
                stderr_text = stderr.decode('utf-8', errors='replace')
                
                # Limit output size
                if len(stdout_text) > self.max_output_size:
                    stdout_text = stdout_text[:self.max_output_size] + "\n... (output truncated)"
                
                if len(stderr_text) > self.max_output_size:
                    stderr_text = stderr_text[:self.max_output_size] + "\n... (error output truncated)"
                
                return {
                    "output": stdout_text,
                    "error_output": stderr_text,
                    "return_code": return_code,
                    "success": return_code == 0,
                    "language": "python",
                    "execution_time": timeout
                }
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file)
                except:
                    pass
                
        except Exception as e:
            return {"error": f"Python execution failed: {str(e)}"}
    
    def _create_safe_python_wrapper(self, code: str) -> str:
        """Create a safe wrapper for Python code execution"""
        
        wrapper = f'''
import sys
import io
from contextlib import redirect_stdout, redirect_stderr

# Redirect stdout/stderr to capture output
stdout_capture = io.StringIO()
stderr_capture = io.StringIO()

try:
    with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
        # User code execution
{chr(10).join("        " + line for line in code.split(chr(10)))}
    
    # Print captured output
    print(stdout_capture.getvalue(), end='')
    if stderr_capture.getvalue():
        print(stderr_capture.getvalue(), file=sys.stderr, end='')
        
except Exception as e:
    print(f"Execution error: {{e}}", file=sys.stderr)
    sys.exit(1)
'''
        
        return wrapper
    
    async def _execute_javascript(self, code: str, timeout: int) -> Dict[str, Any]:
        """Execute JavaScript code using Node.js"""
        
        try:
            # Check if Node.js is available
            try:
                subprocess.run(["node", "--version"], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                return {"error": "Node.js not available for JavaScript execution"}
            
            # Create safe wrapper
            safe_code = self._create_safe_js_wrapper(code)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', 
                                           dir=self.temp_dir, delete=False) as f:
                f.write(safe_code)
                temp_file = f.name
            
            try:
                # Execute code
                process = await asyncio.create_subprocess_exec(
                    "node", temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.temp_dir
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=timeout
                    )
                    
                    return_code = process.returncode
                    
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    return {
                        "error": "JavaScript execution timed out",
                        "timeout": timeout,
                        "language": "javascript"
                    }
                
                # Decode output
                stdout_text = stdout.decode('utf-8', errors='replace')
                stderr_text = stderr.decode('utf-8', errors='replace')
                
                return {
                    "output": stdout_text,
                    "error_output": stderr_text,
                    "return_code": return_code,
                    "success": return_code == 0,
                    "language": "javascript"
                }
                
            finally:
                # Clean up
                try:
                    os.unlink(temp_file)
                except:
                    pass
                
        except Exception as e:
            return {"error": f"JavaScript execution failed: {str(e)}"}
    
    def _create_safe_js_wrapper(self, code: str) -> str:
        """Create a safe wrapper for JavaScript code execution"""
        
        wrapper = f'''
// Safe JavaScript execution wrapper
try {{
    // User code
{code}
}} catch (error) {{
    console.error('Execution error:', error.message);
    process.exit(1);
}}
'''
        
        return wrapper
    
    async def _execute_shell(self, code: str, timeout: int, shell_type: str) -> Dict[str, Any]:
        """Execute shell commands"""
        
        try:
            # Extra validation for shell commands
            if self.safe_mode:
                dangerous_commands = [
                    "rm", "sudo", "chmod", "chown", "passwd", "su", "wget", "curl",
                    "nc", "netcat", "ssh", "scp", "rsync", "dd", "mkfs", "fdisk"
                ]
                
                code_words = code.lower().split()
                for cmd in dangerous_commands:
                    if cmd in code_words:
                        return {"error": f"Dangerous command blocked: {cmd}"}
            
            # Choose shell
            shell_cmd = "/bin/bash" if shell_type == "bash" else "/bin/sh"
            
            # Execute in subprocess
            process = await asyncio.create_subprocess_exec(
                shell_cmd, "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.temp_dir
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
                
                return_code = process.returncode
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "error": "Shell execution timed out",
                    "timeout": timeout,
                    "language": shell_type
                }
            
            # Decode output
            stdout_text = stdout.decode('utf-8', errors='replace')
            stderr_text = stderr.decode('utf-8', errors='replace')
            
            return {
                "output": stdout_text,
                "error_output": stderr_text,
                "return_code": return_code,
                "success": return_code == 0,
                "language": shell_type
            }
            
        except Exception as e:
            return {"error": f"Shell execution failed: {str(e)}"}
    
    async def validate_syntax(self, code: str, language: str) -> Dict[str, Any]:
        """Validate code syntax without execution"""
        
        try:
            if language == "python":
                return self._validate_python_syntax(code)
            elif language == "javascript":
                return self._validate_javascript_syntax(code)
            else:
                return {"valid": True, "message": "Syntax validation not available"}
                
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def _validate_python_syntax(self, code: str) -> Dict[str, Any]:
        """Validate Python syntax"""
        try:
            compile(code, '<string>', 'exec')
            return {"valid": True, "language": "python"}
        except SyntaxError as e:
            return {
                "valid": False,
                "language": "python",
                "error": str(e),
                "line": e.lineno,
                "offset": e.offset
            }
    
    def _validate_javascript_syntax(self, code: str) -> Dict[str, Any]:
        """Validate JavaScript syntax (basic check)"""
        # This is a simplified check - in production you'd use a proper JS parser
        try:
            # Basic checks for common syntax errors
            if code.count('(') != code.count(')'):
                return {"valid": False, "error": "Mismatched parentheses"}
            if code.count('{') != code.count('}'):
                return {"valid": False, "error": "Mismatched braces"}
            if code.count('[') != code.count(']'):
                return {"valid": False, "error": "Mismatched brackets"}
            
            return {"valid": True, "language": "javascript"}
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported programming languages"""
        return list(self.supported_languages.keys())
    
    def get_language_info(self, language: str) -> Dict[str, Any]:
        """Get information about a supported language"""
        return self.supported_languages.get(language, {})
    
    async def run_code_snippet(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Convenience method to run a code snippet"""
        return await self.execute(code, language)
    
    async def test_environment(self) -> Dict[str, Any]:
        """Test the code execution environment"""
        
        results = {}
        
        # Test Python
        python_result = await self.execute("print('Python OK')", "python")
        results["python"] = {
            "available": "error" not in python_result,
            "result": python_result
        }
        
        # Test JavaScript (if Node.js available)
        js_result = await self.execute("console.log('JavaScript OK')", "javascript")
        results["javascript"] = {
            "available": "error" not in js_result,
            "result": js_result
        }
        
        # Test Shell
        shell_result = await self.execute("echo 'Shell OK'", "bash")
        results["bash"] = {
            "available": "error" not in shell_result,
            "result": shell_result
        }
        
        return {
            "environment_test": results,
            "safe_mode": self.safe_mode,
            "timeout": self.timeout,
            "temp_dir": str(self.temp_dir)
        }
