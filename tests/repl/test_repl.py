"""Tests for the REPL Interface."""
import pytest
from unittest.mock import patch, MagicMock, call
import sys
from repl.repl import Repl

class TestRepl:
    """Tests for the REPL class."""

    def test_init(self, mock_task_system, mock_memory_system):
        """Test REPL initialization."""
        with patch('handler.passthrough_handler.PassthroughHandler') as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler
            
            repl = Repl(mock_task_system, mock_memory_system)
            
            assert repl.task_system == mock_task_system
            assert repl.memory_system == mock_memory_system
            assert repl.mode == "passthrough"
            assert repl.passthrough_handler == mock_handler
            assert "/help" in repl.commands
            assert "/mode" in repl.commands
            assert "/exit" in repl.commands

    def test_process_input_command(self, mock_task_system, mock_memory_system):
        """Test processing a command input."""
        with patch('handler.passthrough_handler.PassthroughHandler'):
            repl = Repl(mock_task_system, mock_memory_system)
            
            with patch.object(repl, '_handle_command') as mock_handle_command:
                repl._process_input("/help")
                mock_handle_command.assert_called_once_with("/help")

    def test_process_input_query(self, mock_task_system, mock_memory_system):
        """Test processing a query input."""
        with patch('handler.passthrough_handler.PassthroughHandler'):
            repl = Repl(mock_task_system, mock_memory_system)
            
            with patch.object(repl, '_handle_query') as mock_handle_query:
                repl._process_input("test query")
                mock_handle_query.assert_called_once_with("test query")

    def test_handle_command_known(self, mock_task_system, mock_memory_system):
        """Test handling a known command."""
        with patch('handler.passthrough_handler.PassthroughHandler'):
            repl = Repl(mock_task_system, mock_memory_system)
            mock_cmd = MagicMock()
            repl.commands["/test"] = mock_cmd
            
            repl._handle_command("/test arg1 arg2")
            mock_cmd.assert_called_once_with(["arg1", "arg2"])

    def test_handle_command_unknown(self, mock_task_system, mock_memory_system, capsys):
        """Test handling an unknown command."""
        with patch('handler.passthrough_handler.PassthroughHandler'):
            repl = Repl(mock_task_system, mock_memory_system)
            
            repl._handle_command("/unknown")
            
            captured = capsys.readouterr()
            assert "Unknown command: /unknown" in captured.out

    def test_handle_query_passthrough(self, mock_task_system, mock_memory_system):
        """Test handling a query in passthrough mode."""
        with patch('handler.passthrough_handler.PassthroughHandler') as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler.handle_query.return_value = {"content": "test response"}
            mock_handler_class.return_value = mock_handler
            
            repl = Repl(mock_task_system, mock_memory_system)
            
            with patch('builtins.print') as mock_print:
                repl._handle_query("test query")
                
                mock_handler.handle_query.assert_called_once_with("test query")
                mock_print.assert_any_call("\nResponse:")
                mock_print.assert_any_call("test response")

    def test_cmd_help(self, mock_task_system, mock_memory_system, capsys):
        """Test the help command."""
        with patch('handler.passthrough_handler.PassthroughHandler'):
            repl = Repl(mock_task_system, mock_memory_system)
            
            repl._cmd_help([])
            
            captured = capsys.readouterr()
            assert "Available commands:" in captured.out
            assert "/help" in captured.out
            assert "/mode" in captured.out
            assert "/exit" in captured.out

    def test_cmd_mode_set(self, mock_task_system, mock_memory_system, capsys):
        """Test setting the mode."""
        with patch('handler.passthrough_handler.PassthroughHandler'):
            repl = Repl(mock_task_system, mock_memory_system)
            
            repl._cmd_mode(["standard"])
            
            assert repl.mode == "standard"
            captured = capsys.readouterr()
            assert "Mode set to: standard" in captured.out

    def test_cmd_mode_show(self, mock_task_system, mock_memory_system, capsys):
        """Test showing the current mode."""
        with patch('handler.passthrough_handler.PassthroughHandler'):
            repl = Repl(mock_task_system, mock_memory_system)
            
            repl._cmd_mode([])
            
            captured = capsys.readouterr()
            assert "Current mode: passthrough" in captured.out

    def test_cmd_exit(self, mock_task_system, mock_memory_system):
        """Test the exit command."""
        with patch('handler.passthrough_handler.PassthroughHandler'):
            repl = Repl(mock_task_system, mock_memory_system)
            
            with patch('sys.exit') as mock_exit:
                repl._cmd_exit([])
                mock_exit.assert_called_once_with(0)

    # Add more tests for start() method with mocked input when needed
