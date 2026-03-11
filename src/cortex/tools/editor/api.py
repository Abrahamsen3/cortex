import os
from pathlib import Path

from .diagnostics import _get_lsp_diagnostic_diff, _get_lsp_diagnostics
from .filesystem import (_abs_file_path, _atomic_write_text, _get_text_SHA256,
                         _read_text, _write_text)
from .text import _replace_text, _snippet_locations


def read_file(path: str) -> str:
    """
    Read a Python file and return its contents with line numbers.

    This function validates the file path, handles common errors gracefully,
    and returns a formatted string with each line prefixed by its line number.

    Args:
        path: Path to the Python file to read.

    Returns:
        File contents with each line prefixed by "LINE N: ", or an error message
        string if the file cannot be read.

    Note:
        Does not raise exceptions; returns error messages for failures.
        Returns an error message if the file is not found, permission is denied,
        or the file is not a .py file.
    """
    try:
        abs_path = _abs_file_path(path)
        if not os.path.exists(abs_path):
            return f"Error: File not found: {abs_path}"
        if not abs_path.endswith(".py"):
            return f"Error: Only Python files are supported (.py). Got: {abs_path}"
        file_content: str = _read_text(abs_path)
        file_content_split: list[str] = file_content.split("\n")
        file_content_line_numbered: list[str] = []
        for num, line in enumerate(file_content_split, start=1):
            file_content_line_numbered.append(f"LINE {num}: {line}")
        content = "\n".join(file_content_line_numbered)
        return content
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


def write_file(path: str, content: str) -> str:
    """
    Create or overwrite a Python file with the given content.

    This function creates parent directories as needed and writes the content
    atomically to prevent corruption during the write operation.

    Args:
        path: Path to the Python file to create or overwrite.
        content: String content to write to the file.

    Returns:
        Success message with absolute path on success, or an error message
        string on failure.

    Note:
        Does not raise exceptions; returns error messages for failures.
        Returns an error message if permission is denied, the path is invalid,
        or the write operation fails.
    """
    try:
        abs_path = _abs_file_path(path)
        _atomic_write_text(abs_path, content)
        return f"Successfully created/overwritten: {abs_path}"
    except PermissionError:
        return f"Error: Permission denied: {os.path.abspath(path)}"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


def get_lsp_diagnostics(path: str) -> str:
    """
    Run basedpyright on a Python file and return a user-friendly diagnostic report.

    This function is the public API for getting code diagnostics. It wraps the
    internal diagnostic function and handles errors gracefully.

    Args:
        path: Path to the Python file to analyze.

    Returns:
        A formatted string. Either:
        - "✓ No diagnostics found - your code looks good!" if no issues found
        - A string representation of the diagnostics list
        - An error message if the function fails

    Note:
        Does not raise exceptions; returns error messages for failures.
        Returns an error message if basedpyright is not installed or other
        runtime errors occur.
    """
    try:
        diagnostics = _get_lsp_diagnostics(path)
        if not diagnostics:
            return "✓ No diagnostics found - your code looks good!"
        return f"{diagnostics}"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error getting diagnostics: {str(e)}"


def replace_text(path: str, old_text: str, new_text: str) -> str:
    """
    Replace text in a Python file with new text.

    This function validates that the old_text appears exactly once in the file,
    performs the replacement, checks that the replacement does not introduce
    LSP errors, and atomically writes the changes to the file.

    Args:
        path: Path to the Python file to modify.
        old_text: The text to find and replace (must appear exactly once).
        new_text: The text to replace old_text with.

    Returns:
        A string message indicating success or the type of error that occurred:
        - Success message on successful replacement
        - Error message if old_text appears 0 or more than 1 times
        - Error message if the replacement would introduce LSP errors
        - Error message if the file was modified during execution
        - Error message for permission denied or other I/O errors

    Note:
        Does not raise exceptions; returns error messages for failures.
        The function performs LSP diagnostics before and after the replacement
        to ensure the modified code is valid.
    """
    try:
        abs_path = _abs_file_path(path)
        file_hash_before: str = _get_text_SHA256(_read_text(abs_path))
        old_text_occourences = _snippet_locations(_read_text(abs_path), old_text)
        if len(old_text_occourences) != 1:
            return (
                f"Expected old_text to appear exactly once, "
                f"but found {len(old_text_occourences)} occourences"
            )
        try:
            old_lsp_diagnostics = _get_lsp_diagnostics(abs_path)
        except Exception as e:
            return f"Error: Failed to get original LSP diagnostics: {str(e)}"
        old_text_location = old_text_occourences[0]
        source_text = _read_text(abs_path)
        new_source_text, _ = _replace_text(source_text, old_text_location, new_text)
        temp_file = str(Path(abs_path).with_name(f"{Path(abs_path).stem}__tmp__.py"))
        try:
            _write_text(temp_file, new_source_text)
            new_lsp_diagnostics = _get_lsp_diagnostics(temp_file)
            lsp_diff = _get_lsp_diagnostic_diff(
                old_text_location,
                new_text,
                old_lsp_diagnostics,
                new_lsp_diagnostics,
            )
            for d in lsp_diff:
                if d["severity"] == "error":
                    return (
                        f"Modification added LSP errors, edit rejected. LSP error: {d}"
                    )
            if file_hash_before != _get_text_SHA256(_read_text(abs_path)):
                return "File has been modified while running function"
            _atomic_write_text(abs_path, new_source_text)
            return f"Successfully replaced text in: {abs_path}"
        finally:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except OSError:
                pass
    except PermissionError:
        return f"Error: Permission denied {os.path.abspath(path)}"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error replacing text: {str(e)}"
