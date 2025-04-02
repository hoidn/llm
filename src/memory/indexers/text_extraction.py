"""Utility functions for text extraction and processing."""
from typing import List, Dict, Set, Tuple, Optional
import re
import os

def extract_identifiers_by_language(content: str, file_ext: str) -> List[str]:
    """Extract code identifiers based on the file extension/language.
    
    Args:
        content: File content
        file_ext: File extension (e.g., '.py', '.js')
        
    Returns:
        List of extracted identifiers
    """
    # Normalize file extension
    if file_ext.startswith('.'):
        file_ext = file_ext[1:]
    
    identifiers = []
    
    # Python
    if file_ext == 'py':
        # Extract function and class definitions
        func_matches = re.findall(r'def\s+([a-zA-Z0-9_]+)\s*\(', content)
        class_matches = re.findall(r'class\s+([a-zA-Z0-9_]+)\s*[\(:]', content)
        # Extract variable assignments
        var_matches = re.findall(r'([a-zA-Z][a-zA-Z0-9_]*)\s*=', content)
        
        identifiers.extend(func_matches)
        identifiers.extend(class_matches)
        identifiers.extend(var_matches)
    
    # JavaScript
    elif file_ext in ['js', 'jsx', 'ts', 'tsx']:
        # Functions and methods
        func_matches = re.findall(r'function\s+([a-zA-Z0-9_$]+)|([a-zA-Z0-9_$]+)\s*\([^)]*\)\s*{|\b([a-zA-Z0-9_$]+):\s*function', content)
        # Classes
        class_matches = re.findall(r'class\s+([a-zA-Z0-9_$]+)', content)
        # Variables
        var_matches = re.findall(r'(const|let|var)\s+([a-zA-Z0-9_$]+)', content)
        
        # Flatten function matches
        for match in func_matches:
            identifiers.extend([m for m in match if m])
        identifiers.extend(class_matches)
        # Extract variables (second group in the regex)
        identifiers.extend([m[1] for m in var_matches if len(m) > 1])
    
    # C/C++
    elif file_ext in ['c', 'cpp', 'h', 'hpp']:
        # Functions
        func_matches = re.findall(r'([a-zA-Z0-9_]+)\s*\([^)]*\)\s*{', content)
        # Classes/structs
        class_matches = re.findall(r'(class|struct)\s+([a-zA-Z0-9_]+)', content)
        # Typedefs
        typedef_matches = re.findall(r'typedef\s+.*\s+([a-zA-Z0-9_]+)\s*;', content)
        
        identifiers.extend(func_matches)
        # Extract class/struct names (second group in the regex)
        identifiers.extend([m[1] for m in class_matches if len(m) > 1])
        identifiers.extend(typedef_matches)
    
    # Java/C#
    elif file_ext in ['java', 'cs']:
        # Methods
        method_matches = re.findall(r'(public|private|protected|static|\s) +[\w\<\>\[\]]+\s+([a-zA-Z0-9_]+) *\([^\)]*\)', content)
        # Classes
        class_matches = re.findall(r'class\s+([a-zA-Z0-9_]+)', content)
        # Interfaces
        interface_matches = re.findall(r'interface\s+([a-zA-Z0-9_]+)', content)
        
        # Extract method names (second group in the regex)
        identifiers.extend([m[1] for m in method_matches if len(m) > 1])
        identifiers.extend(class_matches)
        identifiers.extend(interface_matches)
    
    # Go
    elif file_ext == 'go':
        # Functions
        func_matches = re.findall(r'func\s+([a-zA-Z0-9_]+)', content)
        # Structs
        struct_matches = re.findall(r'type\s+([a-zA-Z0-9_]+)\s+struct', content)
        # Interfaces
        interface_matches = re.findall(r'type\s+([a-zA-Z0-9_]+)\s+interface', content)
        
        identifiers.extend(func_matches)
        identifiers.extend(struct_matches)
        identifiers.extend(interface_matches)
    
    # Ruby
    elif file_ext == 'rb':
        # Methods
        method_matches = re.findall(r'def\s+([a-zA-Z0-9_?!]+)', content)
        # Classes
        class_matches = re.findall(r'class\s+([a-zA-Z0-9_]+)', content)
        # Modules
        module_matches = re.findall(r'module\s+([a-zA-Z0-9_]+)', content)
        
        identifiers.extend(method_matches)
        identifiers.extend(class_matches)
        identifiers.extend(module_matches)
    
    # PHP
    elif file_ext == 'php':
        # Functions
        func_matches = re.findall(r'function\s+([a-zA-Z0-9_]+)', content)
        # Classes
        class_matches = re.findall(r'class\s+([a-zA-Z0-9_]+)', content)
        
        identifiers.extend(func_matches)
        identifiers.extend(class_matches)
    
    # Remove duplicates and limit to reasonable number
    unique_identifiers = list(set(identifiers))
    return unique_identifiers[:30]  # Limit to top 30 identifiers

def extract_markdown_headings(content: str) -> List[str]:
    """Extract headings from markdown content.
    
    Args:
        content: Markdown content
        
    Returns:
        List of headings
    """
    # Match both styles of headers: # Header and Header\n===
    header_matches = re.findall(r'^(#{1,6})\s+(.+?)$|^([^\n]+)\n[=]{2,}$', content, re.MULTILINE)
    
    headings = []
    for match in header_matches:
        if match[0]:  # # style headers
            headings.append(match[1].strip())
        elif match[2]:  # underline style headers
            headings.append(match[2].strip())
    
    return headings[:20]  # Limit to 20 headings

def extract_document_summary(content: str, file_ext: str) -> str:
    """Extract a summary of the document based on its content and type.
    
    Args:
        content: Document content
        file_ext: File extension
        
    Returns:
        Document summary
    """
    # Normalize file extension
    if file_ext.startswith('.'):
        file_ext = file_ext[1:]
    
    # Initialize summary
    summary = ""
    
    # For Markdown files
    if file_ext in ['md', 'markdown']:
        headings = extract_markdown_headings(content)
        if headings:
            summary += "Headings: " + ", ".join(headings) + "\n"
    
    # For code files, extract file-level comments
    elif file_ext in ['py', 'js', 'java', 'c', 'cpp', 'h', 'cs', 'go', 'rb', 'php']:
        # Try to extract docstrings or file-level comments
        doc_comment_patterns = [
            # Python docstrings
            r'"""(.*?)"""',
            # Block comments
            r'/\*\*(.*?)\*/',
            # Single line comments (consecutive)
            r'(?:^|\n)(?:(?:#|//)[^\n]*(?:\n(?:#|//)[^\n]*)*)'
        ]
        
        for pattern in doc_comment_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                # Extract the first comment/docstring
                doc_text = matches[0].strip()
                # Clean up and normalize
                doc_text = re.sub(r'\s+', ' ', doc_text)
                doc_text = re.sub(r'[*#/\s]+', ' ', doc_text).strip()
                if doc_text:
                    summary += "Documentation: " + doc_text[:200] + "\n"
                    break
    
    # Extract first few non-blank lines for all files
    lines = content.split('\n')
    content_lines = [line.strip() for line in lines if line.strip()]
    if content_lines:
        preview_lines = content_lines[:5]
        preview = " ".join(preview_lines)
        summary += "Preview: " + preview[:200] + "\n"
    
    return summary

def extract_text_content(file_path: str, max_size: int = 100 * 1024) -> Optional[str]:
    """Extract text content from a file.
    
    Args:
        file_path: Path to file
        max_size: Maximum file size in bytes
        
    Returns:
        Extracted text content or None if extraction failed
    """
    try:
        # Check if file exists
        if not os.path.isfile(file_path):
            print(f"File not found: {file_path}")
            return None
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > max_size:
            print(f"File too large: {file_path} ({file_size} bytes)")
            return None
        
        # Get file extension
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        # Text files
        text_extensions = {
            ".txt", ".md", ".py", ".js", ".java", ".c", ".cpp", ".h", ".hpp",
            ".html", ".css", ".json", ".xml", ".yaml", ".yml", ".ini", ".conf",
            ".sh", ".rb", ".properties", ".gitignore", ".env"
        }
        
        if ext in text_extensions:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        
        # Binary files (not supported)
        binary_extensions = {
            ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".pdf", ".doc", ".docx",
            ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".tar", ".gz", ".exe",
            ".dll", ".so", ".class", ".jar", ".war", ".ear"
        }
        
        if ext in binary_extensions:
            return f"[Binary file: {ext} format]"
        
        # Unknown file type, try as text
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            return f"[Unrecognized file format: {ext}]"
    except Exception as e:
        print(f"Error extracting text from {file_path}: {str(e)}")
        return None
