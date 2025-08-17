import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import tempfile
from datetime import datetime

from config import settings


class FileOperationsTool:
    """Tool for file system operations with safety constraints"""
    
    def __init__(self):
        self.name = "file_ops"
        self.description = "File system operations: read, write, create, delete, list files"
        self.keywords = ["file", "save", "load", "read", "write", "create", "delete", "folder"]
        
        # Safety settings
        self.safe_mode = settings.safe_mode
        self.allowed_extensions = set(settings.allowed_file_extensions)
        self.max_file_size = settings.max_file_size_mb * 1024 * 1024  # Convert to bytes
        
        # Working directory constraints
        self.base_path = Path.cwd()
        self.allowed_directories = [
            self.base_path / "data",
            self.base_path / "outputs",
            self.base_path / "temp",
            self.base_path / "exports"
        ]
        
        # Create allowed directories if they don't exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure allowed directories exist"""
        for directory in self.allowed_directories:
            directory.mkdir(exist_ok=True)
    
    async def execute(self, operation: str, **kwargs) -> Dict[str, Any]:
        """
        Execute file operation
        
        Args:
            operation: Operation type (read, write, create, delete, list, copy, move)
            **kwargs: Operation-specific arguments
            
        Returns:
            Dictionary with operation results
        """
        
        try:
            if operation == "read":
                return await self._read_file(kwargs.get("path"))
            elif operation == "write":
                return await self._write_file(kwargs.get("path"), kwargs.get("content"))
            elif operation == "create":
                return await self._create_file(kwargs.get("path"), kwargs.get("content", ""))
            elif operation == "delete":
                return await self._delete_file(kwargs.get("path"))
            elif operation == "list":
                return await self._list_directory(kwargs.get("path", "."))
            elif operation == "copy":
                return await self._copy_file(kwargs.get("source"), kwargs.get("destination"))
            elif operation == "move":
                return await self._move_file(kwargs.get("source"), kwargs.get("destination"))
            elif operation == "info":
                return await self._get_file_info(kwargs.get("path"))
            elif operation == "search":
                return await self._search_files(kwargs.get("pattern"), kwargs.get("directory", "."))
            else:
                return {"error": f"Unknown operation: {operation}"}
                
        except Exception as e:
            return {"error": f"File operation failed: {str(e)}"}
    
    def _validate_path(self, path: Union[str, Path]) -> Path:
        """Validate and resolve file path"""
        if isinstance(path, str):
            path = Path(path)
        
        # Resolve to absolute path
        if not path.is_absolute():
            path = self.base_path / path
        
        # Normalize path
        path = path.resolve()
        
        # Check if path is within allowed directories
        if self.safe_mode:
            allowed = False
            for allowed_dir in self.allowed_directories:
                try:
                    path.relative_to(allowed_dir)
                    allowed = True
                    break
                except ValueError:
                    continue
            
            if not allowed:
                raise PermissionError(f"Access denied: {path} is not in allowed directories")
        
        return path
    
    def _validate_extension(self, path: Path) -> bool:
        """Validate file extension"""
        if not self.safe_mode:
            return True
        
        extension = path.suffix.lower()
        return extension in self.allowed_extensions
    
    def _validate_file_size(self, size: int) -> bool:
        """Validate file size"""
        return size <= self.max_file_size
    
    async def _read_file(self, path: str) -> Dict[str, Any]:
        """Read file content"""
        try:
            file_path = self._validate_path(path)
            
            if not file_path.exists():
                return {"error": f"File not found: {path}"}
            
            if not file_path.is_file():
                return {"error": f"Path is not a file: {path}"}
            
            if not self._validate_extension(file_path):
                return {"error": f"File extension not allowed: {file_path.suffix}"}
            
            # Check file size
            file_size = file_path.stat().st_size
            if not self._validate_file_size(file_size):
                return {"error": f"File too large: {file_size} bytes (max: {self.max_file_size})"}
            
            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Try reading as binary and convert to text representation
                with open(file_path, 'rb') as f:
                    binary_content = f.read()
                content = f"Binary file ({len(binary_content)} bytes): {binary_content[:100]}..."
            
            return {
                "path": str(file_path),
                "content": content,
                "size": file_size,
                "encoding": "utf-8"
            }
            
        except Exception as e:
            return {"error": f"Failed to read file: {str(e)}"}
    
    async def _write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to file"""
        try:
            file_path = self._validate_path(path)
            
            if not self._validate_extension(file_path):
                return {"error": f"File extension not allowed: {file_path.suffix}"}
            
            # Validate content size
            content_size = len(content.encode('utf-8'))
            if not self._validate_file_size(content_size):
                return {"error": f"Content too large: {content_size} bytes (max: {self.max_file_size})"}
            
            # Create parent directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "path": str(file_path),
                "size": content_size,
                "operation": "write",
                "success": True
            }
            
        except Exception as e:
            return {"error": f"Failed to write file: {str(e)}"}
    
    async def _create_file(self, path: str, content: str = "") -> Dict[str, Any]:
        """Create a new file"""
        try:
            file_path = self._validate_path(path)
            
            if file_path.exists():
                return {"error": f"File already exists: {path}"}
            
            return await self._write_file(path, content)
            
        except Exception as e:
            return {"error": f"Failed to create file: {str(e)}"}
    
    async def _delete_file(self, path: str) -> Dict[str, Any]:
        """Delete a file"""
        try:
            file_path = self._validate_path(path)
            
            if not file_path.exists():
                return {"error": f"File not found: {path}"}
            
            if file_path.is_file():
                file_path.unlink()
                operation = "delete_file"
            elif file_path.is_dir():
                shutil.rmtree(file_path)
                operation = "delete_directory"
            else:
                return {"error": f"Unknown file type: {path}"}
            
            return {
                "path": str(file_path),
                "operation": operation,
                "success": True
            }
            
        except Exception as e:
            return {"error": f"Failed to delete: {str(e)}"}
    
    async def _list_directory(self, path: str) -> Dict[str, Any]:
        """List directory contents"""
        try:
            dir_path = self._validate_path(path)
            
            if not dir_path.exists():
                return {"error": f"Directory not found: {path}"}
            
            if not dir_path.is_dir():
                return {"error": f"Path is not a directory: {path}"}
            
            items = []
            for item in dir_path.iterdir():
                try:
                    stat = item.stat()
                    items.append({
                        "name": item.name,
                        "path": str(item.relative_to(self.base_path)),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat.st_size if item.is_file() else None,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "extension": item.suffix if item.is_file() else None
                    })
                except (OSError, PermissionError):
                    # Skip items that can't be accessed
                    continue
            
            # Sort by type (directories first) then by name
            items.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
            
            return {
                "path": str(dir_path),
                "items": items,
                "count": len(items)
            }
            
        except Exception as e:
            return {"error": f"Failed to list directory: {str(e)}"}
    
    async def _copy_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Copy a file"""
        try:
            source_path = self._validate_path(source)
            dest_path = self._validate_path(destination)
            
            if not source_path.exists():
                return {"error": f"Source file not found: {source}"}
            
            if not source_path.is_file():
                return {"error": f"Source is not a file: {source}"}
            
            if not self._validate_extension(source_path) or not self._validate_extension(dest_path):
                return {"error": "File extension not allowed"}
            
            # Create destination directory if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            
            return {
                "source": str(source_path),
                "destination": str(dest_path),
                "operation": "copy",
                "success": True
            }
            
        except Exception as e:
            return {"error": f"Failed to copy file: {str(e)}"}
    
    async def _move_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Move a file"""
        try:
            source_path = self._validate_path(source)
            dest_path = self._validate_path(destination)
            
            if not source_path.exists():
                return {"error": f"Source file not found: {source}"}
            
            if not self._validate_extension(source_path) or not self._validate_extension(dest_path):
                return {"error": "File extension not allowed"}
            
            # Create destination directory if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file
            shutil.move(str(source_path), str(dest_path))
            
            return {
                "source": str(source_path),
                "destination": str(dest_path),
                "operation": "move",
                "success": True
            }
            
        except Exception as e:
            return {"error": f"Failed to move file: {str(e)}"}
    
    async def _get_file_info(self, path: str) -> Dict[str, Any]:
        """Get file information"""
        try:
            file_path = self._validate_path(path)
            
            if not file_path.exists():
                return {"error": f"File not found: {path}"}
            
            stat = file_path.stat()
            
            info = {
                "path": str(file_path),
                "name": file_path.name,
                "type": "directory" if file_path.is_dir() else "file",
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "extension": file_path.suffix if file_path.is_file() else None,
                "readable": os.access(file_path, os.R_OK),
                "writable": os.access(file_path, os.W_OK)
            }
            
            if file_path.is_file():
                info["lines"] = self._count_lines(file_path)
            
            return info
            
        except Exception as e:
            return {"error": f"Failed to get file info: {str(e)}"}
    
    def _count_lines(self, file_path: Path) -> int:
        """Count lines in a text file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except:
            return 0
    
    async def _search_files(self, pattern: str, directory: str) -> Dict[str, Any]:
        """Search for files matching a pattern"""
        try:
            dir_path = self._validate_path(directory)
            
            if not dir_path.exists() or not dir_path.is_dir():
                return {"error": f"Invalid directory: {directory}"}
            
            matches = []
            
            # Search files recursively
            for file_path in dir_path.rglob(pattern):
                if file_path.is_file():
                    try:
                        stat = file_path.stat()
                        matches.append({
                            "path": str(file_path.relative_to(self.base_path)),
                            "name": file_path.name,
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "extension": file_path.suffix
                        })
                    except (OSError, PermissionError):
                        continue
            
            return {
                "pattern": pattern,
                "directory": str(dir_path),
                "matches": matches,
                "count": len(matches)
            }
            
        except Exception as e:
            return {"error": f"Failed to search files: {str(e)}"}
    
    async def save_text(self, filename: str, content: str, directory: str = "outputs") -> Dict[str, Any]:
        """Convenience method to save text content"""
        path = f"{directory}/{filename}"
        return await self.execute("write", path=path, content=content)
    
    async def load_text(self, filename: str, directory: str = "data") -> Dict[str, Any]:
        """Convenience method to load text content"""
        path = f"{directory}/{filename}"
        return await self.execute("read", path=path)
    
    async def export_json(self, data: Dict[str, Any], filename: str, 
                         directory: str = "exports") -> Dict[str, Any]:
        """Export data as JSON file"""
        try:
            content = json.dumps(data, indent=2, ensure_ascii=False)
            path = f"{directory}/{filename}"
            if not filename.endswith('.json'):
                path += '.json'
            return await self.execute("write", path=path, content=content)
        except Exception as e:
            return {"error": f"Failed to export JSON: {str(e)}"}
    
    async def import_json(self, filename: str, directory: str = "data") -> Dict[str, Any]:
        """Import JSON file"""
        try:
            path = f"{directory}/{filename}"
            if not filename.endswith('.json'):
                path += '.json'
            
            result = await self.execute("read", path=path)
            if "error" in result:
                return result
            
            data = json.loads(result["content"])
            return {"data": data, "path": result["path"]}
            
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON format: {str(e)}"}
        except Exception as e:
            return {"error": f"Failed to import JSON: {str(e)}"}
    
    def get_allowed_extensions(self) -> List[str]:
        """Get list of allowed file extensions"""
        return list(self.allowed_extensions)
    
    def get_allowed_directories(self) -> List[str]:
        """Get list of allowed directories"""
        return [str(d.relative_to(self.base_path)) for d in self.allowed_directories]
