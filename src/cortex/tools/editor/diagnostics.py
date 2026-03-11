import json
import subprocess
from typing import Any

from .filesystem import _abs_file_path


def _get_lsp_diagnostics(path: str) -> list[dict[str, Any]]:
    """
    Run basedpyright on a Python file and return its diagnostics as a list.

    This is an internal helper function that executes the basedpyright linter
    as a subprocess and parses its JSON output.

    Args:
        path: Path to the Python file to analyze.

    Returns:
        List of diagnostic dictionaries, each containing information about
        an error, warning, or informational message from basedpyright.

    Raises:
        RuntimeError: If basedpyright is not installed, if the subprocess
            times out (15 second limit), if basedpyright produces no output,
            or if the output is not valid JSON or does not contain the expected format.
        ValueError: If the path is not a valid .py file.
    """
    abs_path = _abs_file_path(path)
    try:
        result = subprocess.run(
            ["basedpyright", "--outputjson", abs_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "basedpyright not found. Install with: pip install basedpyright"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("Diagnostics timed out (15 second limit)") from e
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if not stdout:
        raise RuntimeError(stderr or "basedpyright produced no output.")
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"basedpyright returned non-JSON output: {stdout or stderr}"
        ) from e
    diagnostics = data.get("generalDiagnostics", [])
    if not isinstance(diagnostics, list):
        raise RuntimeError(
            f"basedpyright JSON did not contain a diagnostics list: {type(diagnostics).__name__}"
        )
    return diagnostics


def _get_text_info(text1: str) -> tuple[int, int]:
    """
    Analyze a text string and return information about its line endings.

    Args:
        text1: The text to analyze.

    Returns:
        A tuple of (newline_count, chars_after_last_newline) where:
        - newline_count: Number of newline characters in the text
        - chars_after_last_newline: Number of characters after the final newline
    """
    newline_count = text1.count("\n")
    if newline_count == 0:
        chars_after_last_newline = len(text1)
    else:
        last_newline_idx = text1.rfind("\n")
        chars_after_last_newline = len(text1) - last_newline_idx - 1
    return newline_count, chars_after_last_newline


def _compare_location(line1: int, col1: int, line2: int, col2: int) -> int:
    """
    Compare two code locations (line, column pairs) lexicographically.

    Args:
        line1: Line number of the first location.
        col1: Column number of the first location.
        line2: Line number of the second location.
        col2: Column number of the second location.

    Returns:
        -1 if first location comes before second,
        1 if first location comes after second,
        0 if locations are equal.
    """
    if line1 < line2:
        return -1
    if line1 > line2:
        return 1
    if col1 < col2:
        return -1
    if col1 > col2:
        return 1
    return 0


def _advance_lsp_position(
    start_location: tuple[int, int], text_info: tuple[int, int]
) -> tuple[int, int]:
    """
    Calculate the position after inserting text at a given location.

    Args:
        start_location: The starting position (line, column) where text was inserted.
        text_info: A tuple (newline_count, chars_after_last_newline) describing
            the inserted text from _get_text_info.

    Returns:
        The position (line, column) immediately after the inserted text.
    """
    line_count, col_tail = text_info
    if line_count == 0:
        return (start_location[0], start_location[1] + col_tail)
    return (start_location[0] + line_count, col_tail)


def _shift_position_after_replace(
    position: tuple[int, int],
    old_end_location: tuple[int, int],
    new_end_location: tuple[int, int],
) -> tuple[int, int]:
    """
    Calculate the new position after a text replacement operation.

    When text is replaced in a file, subsequent positions may need to be adjusted
    based on the size change of the replacement.

    Args:
        position: The original position (line, column) to adjust.
        old_end_location: The end position (line, column) of the text being replaced.
        new_end_location: The end position (line, column) after the replacement.

    Returns:
        The adjusted position (line, column) after the replacement.
    """
    line, col = position
    if line == old_end_location[0]:
        return (new_end_location[0], new_end_location[1] + (col - old_end_location[1]))
    return (line + (new_end_location[0] - old_end_location[0]), col)


def _adjust_lsp_diagnostic_location(
    lsp_diagnostic: Any,
    old_start: tuple[int, int],
    old_end: tuple[int, int],
    new_end: tuple[int, int],
) -> Any | None:
    """
    Adjust an LSP diagnostic location after a text replacement.

    This function determines whether a diagnostic's location needs to be adjusted
    based on a text replacement that occurred in the file.

    Args:
        lsp_diagnostic: The diagnostic object from LSP (with 'range' containing 'start' and 'end').
        old_start: Start position (line, column) of the replaced text.
        old_end: End position (line, column) of the replaced text.
        new_end: New end position (line, column) after the replacement.

    Returns:
        Adjusted diagnostic object if the diagnostic is after the replacement,
        or None if the diagnostic should not be adjusted.
    """
    diag = copy.deepcopy(lsp_diagnostic)

    start_location = diag["range"]["start"]
    end_location = diag["range"]["end"]

    diag_start = (start_location["line"], start_location["character"])
    diag_end = (end_location["line"], end_location["character"])

    if _compare_location(diag_end[0], diag_end[1], old_start[0], old_start[1]) <= 0:
        return diag

    if _compare_location(diag_start[0], diag_start[1], old_end[0], old_end[1]) >= 0:
        new_start = _shift_position_after_replace(diag_start, old_end, new_end)
        new_diag_end = _shift_position_after_replace(diag_end, old_end, new_end)

        diag["range"]["start"]["line"] = new_start[0]
        diag["range"]["start"]["character"] = new_start[1]
        diag["range"]["end"]["line"] = new_diag_end[0]
        diag["range"]["end"]["character"] = new_diag_end[1]
        return diag

    return None


def _diagnostic_signature(d: Any) -> tuple[Any, Any, Any, Any, Any, Any]:
    """
    Extract a unique signature from an LSP diagnostic for comparison.

    Args:
        d: An LSP diagnostic dictionary containing 'rule', 'message', and 'range' fields.

    Returns:
        A 6-tuple containing (rule, message, start_line, start_character,
        end_line, end_character) that uniquely identifies the diagnostic.
    """
    range_data = d.get("range", {})
    start = range_data.get("start", {})
    end = range_data.get("end", {})

    return (
        d.get("rule"),
        d.get("message"),
        start.get("line"),
        start.get("character"),
        end.get("line"),
        end.get("character"),
    )


def _get_lsp_diagnostic_diff(
    replace_location: tuple[int, int, int, int],
    new_text: str,
    old_lsp_diagnostics: list[Any],
    new_lsp_diagnostics: list[Any],
) -> list[Any]:
    """
    Compute the difference between old and new LSP diagnostics after a text replacement.

    This function identifies new diagnostics in the new version of the file
    that were not present (or should be ignored) in the old version.

    Args:
        replace_location: A 4-tuple (start_line, start_col, end_line, end_col)
            representing the replaced text location.
        new_text: The text that was inserted to replace the old text.
        old_lsp_diagnostics: List of diagnostics before the replacement.
        new_lsp_diagnostics: List of diagnostics after the replacement.

    Returns:
        List of diagnostics that are newly introduced by the replacement
        and were not present in the old version.
    """
    old_start = (replace_location[0], replace_location[1])
    old_end = (replace_location[2], replace_location[3])
    new_end = _advance_lsp_position(old_start, _get_text_info(new_text))

    transformed_old = []
    for d in old_lsp_diagnostics:
        adjusted = _adjust_lsp_diagnostic_location(d, old_start, old_end, new_end)
        if adjusted is not None:
            transformed_old.append(adjusted)

    old_signatures = {_diagnostic_signature(d) for d in transformed_old}

    return [
        d for d in new_lsp_diagnostics if _diagnostic_signature(d) not in old_signatures
    ]
