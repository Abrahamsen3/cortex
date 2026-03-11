def _snippet_locations(
    file_content: str, snippet: str
) -> list[tuple[int, int, int, int]]:
    """
    Find all occurrences of a text snippet in a file and return their locations.

    Each location is a 4-tuple of (start_line, start_col, end_line, end_col),
    where lines and columns are 0-indexed.

    Args:
        file_content: The full text content of the file to search.
        snippet: The text snippet to find within the file content.

    Returns:
        List of location tuples, each containing:
        - start_line: 0-indexed line number where snippet starts
        - start_col: 0-indexed column number where snippet starts
        - end_line: 0-indexed line number where snippet ends
        - end_col: 0-indexed column number where snippet ends

    Note:
        Returns empty list if snippet is empty or not found.
        Finds all non-overlapping occurrences.
    """
    if not snippet:
        return []
    locations = []
    start = 0
    while True:
        pos = file_content.find(snippet, start)
        if pos == -1:
            break
        start_line = file_content[:pos].count("\n")
        start_col = (
            pos - file_content.rfind("\n", 0, pos) - 1
            if "\n" in file_content[:pos]
            else pos
        )
        end_pos = pos + len(snippet)
        end_line = file_content[:end_pos].count("\n")
        end_col = (
            end_pos - file_content.rfind("\n", 0, end_pos) - 1
            if "\n" in file_content[:end_pos]
            else end_pos
        )
        locations.append((start_line, start_col, end_line, end_col))
        start = end_pos
    return locations


def _line_col_to_offset(text: str, line: int, col: int) -> int:
    """
    Convert a line and column position to a character offset in the text.

    Args:
        text: The text content of the file.
        line: 0-indexed line number.
        col: 0-indexed column number.

    Returns:
        Character offset from the beginning of the text to the specified position.

    Raises:
        ValueError: If line or column is negative, line is out of range, or
            column is out of range for the specified line.
    """
    if line < 0 or col < 0:
        raise ValueError(f"Negative line/column not allowed: line={line}, col={col}")
    if line == 0:
        if col > len(text.split("\n", 1)[0]):
            raise ValueError(f"Column out of range for line 0: {col}")
        return col
    current_line = 0
    offset = 0
    text_len = len(text)
    while current_line < line and offset < text_len:
        newline_idx = text.find("\n", offset)
        if newline_idx == -1:
            raise ValueError(f"Line out of range: {line}")
        offset = newline_idx + 1
        current_line += 1
    if current_line != line:
        raise ValueError(f"Line out of range: {line}")
    line_end = text.find("\n", offset)
    if line_end == -1:
        line_end = text_len
    if offset + col > line_end:
        raise ValueError(
            f"Column out of range for line {line}: {col} > {line_end - offset}"
        )
    return offset + col


def _replace_text(
    text: str, replace_location: tuple[int, int, int, int], insert_text: str
) -> tuple[str, str]:
    """
    Replace a portion of text at a specified location with new text.

    Args:
        text: The original text content.
        replace_location: A 4-tuple (start_line, start_col, end_line, end_col)
            specifying the range of text to replace (0-indexed).
        insert_text: The text to insert in place of the replaced text.

    Returns:
        A tuple of (new_text, removed_text) where:
        - new_text: The text with the replacement applied
        - removed_text: The portion of text that was removed

    Raises:
        ValueError: If the replacement range is invalid (end before start),
            or if the line/column positions are out of bounds.
    """
    start_line, start_col, end_line, end_col = replace_location
    start_offset = _line_col_to_offset(text, start_line, start_col)
    end_offset = _line_col_to_offset(text, end_line, end_col)
    if end_offset < start_offset:
        raise ValueError(
            f"Invalid replace range: start offset {start_offset} is after end offset {end_offset}"
        )
    removed_text = text[start_offset:end_offset]
    new_text = text[:start_offset] + insert_text + text[end_offset:]
    return (new_text, removed_text)
