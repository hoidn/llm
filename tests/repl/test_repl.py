"""Tests for the REPL Interface."""
import pytest
from unittest.mock import patch, MagicMock, call
import sys
from io import StringIO
from repl.repl import Repl

@pytest.fixture
def mock_application():
    """Fixture for mock application."""
    app = MagicMock()
    app.indexed_repositories = ["/path/to/repo"]
    app.handle_query.return_value = {
        "content": "This is a sample response.",
        "metadata": {"key": "value"}
    }
    return app

@pytest.fixture
def repl_instance(mock_application):
    """Fixture for REPL instance with mock application."""
    return Repl(application=mock_application)

@pytest.fixture
def capture_stdout():
    """Fixture to capture stdout."""
    captured_output = StringIO()
    sys.stdout = captured_output
    yield captured_output
    sys.stdout = sys.__stdout__

class TestRepl:
    """Tests for the REPL class."""

    def test_init(self, mock_application):
        """Test REPL initialization."""
        repl = Repl(mock_application)
        
        assert repl.application == mock_application
        assert repl.mode == "passthrough"
        assert repl.verbose is False
        assert "/help" in repl.commands
        assert "/mode" in repl.commands
        assert "/exit" in repl.commands
        assert "/reset" in repl.commands
        assert "/verbose" in repl.commands
        assert "/index" in repl.commands

    def test_process_input_command(self, repl_instance):
        """Test processing a command input."""
        with patch.object(repl_instance, '_handle_command') as mock_handle_command:
            repl_instance._process_input("/help")
            mock_handle_command.assert_called_once_with("/help")

    def test_process_input_query(self, repl_instance):
        """Test processing a query input."""
        with patch.object(repl_instance, '_handle_query') as mock_handle_query:
            repl_instance._process_input("test query")
            mock_handle_query.assert_called_once_with("test query")

    def test_handle_command_known(self, repl_instance):
        """Test handling a known command."""
        mock_cmd = MagicMock()
        repl_instance.commands["/test"] = mock_cmd
        
        repl_instance._handle_command("/test arg1 arg2")
        mock_cmd.assert_called_once_with("arg1 arg2")

    def test_handle_command_unknown(self, repl_instance, capture_stdout):
        """Test handling an unknown command."""
        repl_instance._handle_command("/unknown")
        
        output = capture_stdout.getvalue()
        assert "Unknown command: /unknown" in output
        assert "Type /help for available commands" in output

    def test_handle_query_passthrough(self, repl_instance, capture_stdout):
        """Test handling a query in passthrough mode."""
        repl_instance._handle_query("test query")
        
        # Verify application.handle_query was called
        repl_instance.application.handle_query.assert_called_once_with("test query")
        
        # Verify response was displayed
        output = capture_stdout.getvalue()
        assert "Response:" in output
        assert "This is a sample response." in output

    def test_handle_query_no_repositories(self, repl_instance, capture_stdout):
        """Test handling a query with no repositories indexed."""
        # Set indexed_repositories to empty list
        repl_instance.application.indexed_repositories = []
        
        repl_instance._handle_query("test query")
        
        # Verify application.handle_query was not called
        repl_instance.application.handle_query.assert_not_called()
        
        # Verify error message was displayed
        output = capture_stdout.getvalue()
        assert "No repositories indexed" in output
        assert "/index REPO_PATH" in output

    def test_handle_query_with_verbose(self, repl_instance, capture_stdout):
        """Test handling a query with verbose mode enabled."""
        repl_instance.verbose = True
        repl_instance._handle_query("test query")
        
        # Verify application.handle_query was called
        repl_instance.application.handle_query.assert_called_once_with("test query")
        
        # Verify response and metadata were displayed
        output = capture_stdout.getvalue()
        assert "Response:" in output
        assert "This is a sample response." in output
        assert "Metadata:" in output
        assert "key: value" in output

    def test_cmd_help(self, repl_instance, capture_stdout):
        """Test the help command."""
        repl_instance._cmd_help("")
        
        output = capture_stdout.getvalue()
        assert "Available commands:" in output
        assert "/help" in output
        assert "/mode" in output
        assert "/index" in output
        assert "/reset" in output
        assert "/verbose" in output
        assert "/exit" in output

    def test_cmd_mode_set(self, repl_instance, capture_stdout):
        """Test setting the mode."""
        repl_instance._cmd_mode("standard")
        
        assert repl_instance.mode == "standard"
        output = capture_stdout.getvalue()
        assert "Mode set to: standard" in output

    def test_cmd_mode_invalid(self, repl_instance, capture_stdout):
        """Test setting an invalid mode."""
        repl_instance._cmd_mode("invalid")
        
        assert repl_instance.mode == "passthrough"  # Mode should not change
        output = capture_stdout.getvalue()
        assert "Invalid mode: invalid" in output
        assert "Available modes: passthrough, standard" in output

    def test_cmd_mode_show(self, repl_instance, capture_stdout):
        """Test showing the current mode."""
        repl_instance._cmd_mode("")
        
        output = capture_stdout.getvalue()
        assert "Current mode: passthrough" in output

    def test_cmd_reset(self, repl_instance, capture_stdout):
        """Test the reset command."""
        repl_instance._cmd_reset("")
        
        repl_instance.application.reset_conversation.assert_called_once()
        output = capture_stdout.getvalue()
        assert "Conversation reset" in output

    def test_cmd_verbose_toggle(self, repl_instance, capture_stdout):
        """Test toggling verbose mode."""
        # Initially verbose is False
        assert repl_instance.verbose is False
        
        # Toggle on
        repl_instance._cmd_verbose("")
        assert repl_instance.verbose is True
        
        # Reset capture
        capture_stdout.truncate(0)
        capture_stdout.seek(0)
        
        # Toggle off
        repl_instance._cmd_verbose("")
        assert repl_instance.verbose is False
        
        output = capture_stdout.getvalue()
        assert "Verbose mode: off" in output

    def test_cmd_verbose_explicit(self, repl_instance, capture_stdout):
        """Test explicitly setting verbose mode."""
        # Set to on
        repl_instance._cmd_verbose("on")
        assert repl_instance.verbose is True
        
        # Reset capture
        capture_stdout.truncate(0)
        capture_stdout.seek(0)
        
        # Set to off
        repl_instance._cmd_verbose("off")
        assert repl_instance.verbose is False
        
        output = capture_stdout.getvalue()
        assert "Verbose mode: off" in output

    def test_cmd_index(self, repl_instance, capture_stdout):
        """Test the index command."""
        repl_instance._cmd_index("/path/to/repo")
        
        repl_instance.application.index_repository.assert_called_once_with("/path/to/repo")

    def test_cmd_index_no_path(self, repl_instance, capture_stdout):
        """Test the index command with no path."""
        repl_instance._cmd_index("")
        
        repl_instance.application.index_repository.assert_not_called()
        output = capture_stdout.getvalue()
        assert "Error: Repository path required" in output
        assert "Usage: /index REPO_PATH" in output

    def test_cmd_exit(self, repl_instance):
        """Test the exit command."""
        with patch('sys.exit') as mock_exit:
            repl_instance._cmd_exit("")
            mock_exit.assert_called_once_with(0)
