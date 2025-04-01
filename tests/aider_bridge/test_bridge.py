"""Tests for the AiderBridge component."""
import pytest
from unittest.mock import patch, MagicMock

from aider_bridge.bridge import AiderBridge
from aider_bridge.result_formatter import format_automatic_result

class TestAiderBridge:
    """Tests for the AiderBridge class."""
    
    def test_init(self, mock_memory_system):
        """Test initialization of AiderBridge."""
        # Test with Aider not available
        with patch('aider_bridge.bridge.AiderBridge._initialize_aider_components') as mock_init, \
             patch('aider_bridge.bridge.AiderBridge.aider_available', False):
            bridge = AiderBridge(mock_memory_system)
            
            assert bridge.memory_system == mock_memory_system
            assert bridge.file_context == set()
            assert bridge.context_source is None
            assert not bridge.aider_available
    
    def test_set_file_context(self, mock_memory_system, tmp_path):
        """Test setting file context."""
        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("print('Hello, world!')")
        
        # Create AiderBridge instance
        bridge = AiderBridge(mock_memory_system)
        
        # Set file context
        result = bridge.set_file_context([str(test_file)], source="explicit_specification")
        
        # Check result
        assert result["status"] == "success"
        assert result["file_count"] == 1
        assert result["context_source"] == "explicit_specification"
        
        # Check bridge state
        assert bridge.file_context == {str(test_file)}
        assert bridge.context_source == "explicit_specification"
        
        # Test with invalid file
        result = bridge.set_file_context(["nonexistent.py"], source="explicit_specification")
        
        # Check result (should succeed with warnings, but no files)
        assert result["status"] == "success"
        assert result["file_count"] == 0
    
    def test_get_file_context(self, mock_memory_system):
        """Test getting file context."""
        # Create AiderBridge instance
        bridge = AiderBridge(mock_memory_system)
        
        # Set file context
        bridge.file_context = {"/path/to/file1.py", "/path/to/file2.py"}
        bridge.context_source = "associative_matching"
        
        # Get file context
        result = bridge.get_file_context()
        
        # Check result
        assert set(result["file_paths"]) == {"/path/to/file1.py", "/path/to/file2.py"}
        assert result["file_count"] == 2
        assert result["context_source"] == "associative_matching"
    
    def test_get_context_for_query(self, mock_memory_system):
        """Test getting context for a query."""
        # Setup mock for memory system
        matches = [("/path/to/file1.py", "metadata1"), ("/path/to/file2.py", "metadata2")]
        mock_result = MagicMock()
        mock_result.matches = matches
        mock_memory_system.get_relevant_context_for.return_value = mock_result
        
        # Create AiderBridge instance
        bridge = AiderBridge(mock_memory_system)
        
        # Get context for query
        result = bridge.get_context_for_query("test query")
        
        # Check result
        assert result == ["/path/to/file1.py", "/path/to/file2.py"]
        
        # Check bridge state
        assert bridge.file_context == {"/path/to/file1.py", "/path/to/file2.py"}
        assert bridge.context_source == "associative_matching"
        
        # Check memory system was called
        mock_memory_system.get_relevant_context_for.assert_called_once()
        call_args = mock_memory_system.get_relevant_context_for.call_args[0][0]
        assert call_args["taskText"] == "test query"
    
    def test_execute_code_edit_aider_not_available(self, mock_memory_system):
        """Test execute_code_edit when Aider is not available."""
        # Create AiderBridge instance with Aider not available
        with patch('aider_bridge.bridge.AiderBridge.aider_available', False):
            bridge = AiderBridge(mock_memory_system)
            
            # Execute code edit
            result = bridge.execute_code_edit("Implement a function to calculate factorial")
            
            # Check result
            assert result["status"] == "error"
            assert "Aider is not available" in result["content"]
            assert "error" in result["notes"]
            assert "Aider dependency not installed" in result["notes"]["error"]
    
    @patch('aider_bridge.bridge.AiderBridge._get_coder')
    @patch('aider_bridge.bridge.AiderBridge.aider_available', True)
    @patch('aider_bridge.bridge.AiderBridge._initialize_aider_components', return_value=True)
    def test_execute_code_edit_success(self, mock_init, mock_get_coder, mock_memory_system):
        """Test execute_code_edit with successful execution."""
        # Setup mock coder
        mock_coder = MagicMock()
        mock_coder.run.return_value = "Code edited successfully"
        mock_coder.aider_edited_files = ["/path/to/file1.py"]
        mock_get_coder.return_value = mock_coder
        
        # Create AiderBridge instance
        bridge = AiderBridge(mock_memory_system)
        
        # Set file context
        bridge.file_context = {"/path/to/file1.py", "/path/to/file2.py"}
        
        # Execute code edit
        result = bridge.execute_code_edit("Implement a function to calculate factorial")
        
        # Check result
        assert result["status"] == "COMPLETE"
        assert "Code changes applied successfully" in result["content"]
        assert "files_modified" in result["notes"]
        assert result["notes"]["files_modified"] == ["/path/to/file1.py"]
        assert "changes" in result["notes"]
        assert len(result["notes"]["changes"]) == 1
        assert result["notes"]["changes"][0]["file"] == "/path/to/file1.py"
        
        # Check coder was called
        mock_get_coder.assert_called_once_with(["/path/to/file1.py", "/path/to/file2.py"])
        mock_coder.run.assert_called_once_with(
            with_message="Implement a function to calculate factorial", 
            preproc=True
        )
    
    @patch('aider_bridge.bridge.AiderBridge._get_coder')
    @patch('aider_bridge.bridge.AiderBridge.aider_available', True)
    @patch('aider_bridge.bridge.AiderBridge._initialize_aider_components', return_value=True)
    def test_execute_code_edit_no_changes(self, mock_init, mock_get_coder, mock_memory_system):
        """Test execute_code_edit with no changes made."""
        # Setup mock coder
        mock_coder = MagicMock()
        mock_coder.run.return_value = "No changes needed"
        mock_coder.aider_edited_files = []
        mock_get_coder.return_value = mock_coder
        
        # Create AiderBridge instance
        bridge = AiderBridge(mock_memory_system)
        
        # Set file context
        bridge.file_context = {"/path/to/file1.py", "/path/to/file2.py"}
        
        # Execute code edit
        result = bridge.execute_code_edit("Implement a function to calculate factorial")
        
        # Check result
        assert result["status"] == "COMPLETE"
        assert "No changes needed" in result["content"]
        assert "files_modified" in result["notes"]
        assert result["notes"]["files_modified"] == []
        assert "changes" in result["notes"]
        assert len(result["notes"]["changes"]) == 0
    
    @patch('aider_bridge.bridge.AiderBridge._get_coder', return_value=None)
    @patch('aider_bridge.bridge.AiderBridge.aider_available', True)
    @patch('aider_bridge.bridge.AiderBridge._initialize_aider_components', return_value=True)
    def test_execute_code_edit_coder_initialization_failed(self, mock_init, mock_get_coder, mock_memory_system):
        """Test execute_code_edit when coder initialization fails."""
        # Create AiderBridge instance
        bridge = AiderBridge(mock_memory_system)
        
        # Set file context
        bridge.file_context = {"/path/to/file1.py", "/path/to/file2.py"}
        
        # Execute code edit
        result = bridge.execute_code_edit("Implement a function to calculate factorial")
        
        # Check result
        assert result["status"] == "error"
        assert "Failed to initialize Aider Coder" in result["content"]
        assert "error" in result["notes"]
        assert "Coder initialization failed" in result["notes"]["error"]
        
        # Check coder was attempted to be created
        mock_get_coder.assert_called_once_with(["/path/to/file1.py", "/path/to/file2.py"])
    
    @patch('aider_bridge.bridge.AiderBridge.get_context_for_query')
    @patch('aider_bridge.bridge.AiderBridge.aider_available', True)
    def test_execute_code_edit_with_no_context(self, mock_get_context, mock_memory_system):
        """Test execute_code_edit when no file context is available."""
        # Setup mock to return no files
        mock_get_context.return_value = []
        
        # Create AiderBridge instance
        bridge = AiderBridge(mock_memory_system)
        
        # Execute code edit with no context
        result = bridge.execute_code_edit("Implement a function to calculate factorial")
        
        # Check result
        assert result["status"] == "error"
        assert "No relevant files found" in result["content"]
        assert "error" in result["notes"]
        assert "No file context available" in result["notes"]["error"]
        
        # Check get_context_for_query was called
        mock_get_context.assert_called_once_with("Implement a function to calculate factorial")

class TestResultFormatter:
    """Tests for the result formatter utilities."""
    
    def test_format_automatic_result(self):
        """Test formatting an automatic result."""
        result = format_automatic_result(
            status="COMPLETE",
            content="Code changes applied successfully",
            files_modified=["/path/to/file1.py", "/path/to/file2.py"],
            changes=[
                {"file": "/path/to/file1.py", "description": "Added factorial function"},
                {"file": "/path/to/file2.py", "description": "Fixed bug in main function"}
            ]
        )
        
        # Check result structure
        assert result["status"] == "COMPLETE"
        assert result["content"] == "Code changes applied successfully"
        assert "notes" in result
        assert "operation_type" in result["notes"]
        assert result["notes"]["operation_type"] == "automatic"
        assert "files_modified" in result["notes"]
        assert set(result["notes"]["files_modified"]) == {"/path/to/file1.py", "/path/to/file2.py"}
        assert "changes" in result["notes"]
        assert len(result["notes"]["changes"]) == 2
        
        # Test automatic changes generation
        result = format_automatic_result(
            status="COMPLETE",
            content="Code changes applied successfully",
            files_modified=["/path/to/file1.py", "/path/to/file2.py"]
        )
        
        assert "changes" in result["notes"]
        assert len(result["notes"]["changes"]) == 2
        assert result["notes"]["changes"][0]["file"] == "/path/to/file1.py"
        assert "Modified" in result["notes"]["changes"][0]["description"]
    
    def test_format_automatic_result_with_error(self):
        """Test formatting an automatic result with an error."""
        result = format_automatic_result(
            status="FAILED",
            content="Failed to apply code changes",
            error="Something went wrong"
        )
        
        # Check result structure
        assert result["status"] == "FAILED"
        assert result["content"] == "Failed to apply code changes"
        assert "notes" in result
        assert "error" in result["notes"]
        assert result["notes"]["error"] == "Something went wrong"
