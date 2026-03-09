import copy
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def _abs_file_path(path: str) -> str:
    abs_path = os.path.abspath(path)
    if not abs_path.endswith(".py"):
        raise ValueError(f"Only Python files are supported (.py). Got: {abs_path}")
    return abs_path


def _read_text(abs_path: str) -> str:
    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(abs_path: str, content: str) -> None:
    dir_path = os.path.dirname(abs_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(abs_path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def _atomic_write_text(abs_path: str, content: str) -> None:
    dir_path = os.path.dirname(abs_path) or "."
    os.makedirs(dir_path, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        suffix=".py", prefix=".tmp_", dir=dir_path, text=True
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, abs_path)
    except Exception:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        raise


def read_file(path: str) -> str:
    """
    Read a Python file and return its contents.
    """
    try:
        abs_path = _abs_file_path(path)

        if not os.path.exists(abs_path):
            return f"Error: File not found: {abs_path}"

        # NOTE: can possibly be removed
        # Exists because LSP is using basepyright
        if not abs_path.endswith(".py"):
            return f"Error: Only Python files are supported (.py). Got: {abs_path}"

        # NOTE: this is to get line numbers in output
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
    Create or overwrite a file with content.
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


def _get_lsp_diagnostics(path: str) -> list[dict[str, Any]]:
    """
    Internal helper for programmatic use.
    Always returns a list of diagnostics.
    Raises on tool/runtime/parsing failures.
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


def get_lsp_diagnostics(path: str) -> str:
    """
    Public/user-facing diagnostics function.
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


def _snippet_locations(
    file_content: str, snippet: str
) -> list[tuple[int, int, int, int]]:
    """
    Find all occourances of a snippet in a text.
    """

    if not snippet:
        return []

    locations = []
    start = 0

    while True:
        pos = file_content.find(snippet, start)
        if pos == -1:
            break

        # Calculate start line and column (0-indexed)
        start_line = file_content[:pos].count("\n")
        start_col = (
            pos - file_content.rfind("\n", 0, pos) - 1
            if "\n" in file_content[:pos]
            else pos
        )

        # Calculate end line and column
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


def _get_text_SHA256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _get_text_info(text1: str) -> tuple[int, int]:
    newline_count = text1.count("\n")
    if newline_count == 0:
        chars_after_last_newline = len(text1)
    else:
        last_newline_idx = text1.rfind("\n")
        chars_after_last_newline = len(text1) - last_newline_idx - 1
    return newline_count, chars_after_last_newline


def _compare_location(line1: int, col1: int, line2: int, col2: int) -> int:
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
    line_count, col_tail = text_info
    if line_count == 0:
        return (start_location[0], start_location[1] + col_tail)
    return (start_location[0] + line_count, col_tail)


def _shift_position_after_replace(
    position: tuple[int, int],
    old_end_location: tuple[int, int],
    new_end_location: tuple[int, int],
) -> tuple[int, int]:
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


def _line_col_to_offset(text: str, line: int, col: int) -> int:
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


def replace_text(path: str, old_text: str, new_text: str) -> str:
    """
    Replace text in a file
    """
    try:
        abs_path = _abs_file_path(path)

        file_hash_before: str = _get_text_SHA256(_read_text(abs_path))

        old_text_occourances = _snippet_locations(_read_text(abs_path), old_text)

        if len(old_text_occourances) != 1:
            return (
                f"Expected old_text to appear exactly once, "
                f"but found {len(old_text_occourances)} occourences"
            )

        try:
            old_lsp_diagnostics = _get_lsp_diagnostics(abs_path)
        except Exception as e:
            return f"Error: Failed to get original LSP diagnostics: {str(e)}"

        old_text_location = old_text_occourances[0]

        source_text = _read_text(abs_path)

        new_source_text, replaced_text = _replace_text(
            source_text, old_text_location, new_text
        )

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
                        f"Modification added LSP errors, edit rejected. LSP error: {d})"
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


if __name__ == "__main__":
    print("\n--- TEST 1: successful replacement on copied real file ---")
    status1 = write_file(
        _abs_file_path("text2.py"),
        _read_text(_abs_file_path("src/cortex/tools/editor.py")),
    )
    print(status1)

    status2 = replace_text(
        _abs_file_path("text2.py"),
        "        if not os.path.exists(abs_path):\n"
        '            return f"Error: File not found: {abs_path}"\n'
        "\n"
        "        # NOTE: can possibly be removed\n"
        "        # Exists because LSP is using basepyright\n"
        '        if not abs_path.endswith(".py"):\n'
        '            return f"Error: Only Python files are supported (.py). Got: {abs_path}"\n'
        "\n"
        "        # NOTE: this is to get line numbers in output",
        "        if not os.path.exists(abs_path):\n"
        '            return f"Error: File not found: {abs_path}"\n'
        "\n"
        "        # NOTE: this is to get line numbers in output",
    )
    print(status2)

    print("\n--- TEST 2: fail because old_text is not present ---")
    status3 = write_file(
        _abs_file_path("text3.py"),
        "def foo() -> int:\n    value = 1\n    return value\n",
    )
    print(status3)

    status4 = replace_text(
        _abs_file_path("text3.py"),
        "    value = 2\n",
        "    value = 3\n",
    )
    print(status4)

    print("\n--- TEST 3: fail because old_text occurs more than once ---")
    status5 = write_file(
        _abs_file_path("text4.py"),
        "x = 1\nprint(x)\nx = 1\n",
    )
    print(status5)

    status6 = replace_text(
        _abs_file_path("text4.py"),
        "x = 1",
        "x = 2",
    )
    print(status6)

    print("\n--- TEST 4: fail because replacement introduces LSP/parser error ---")
    status7 = write_file(
        _abs_file_path("text5.py"),
        "def add_one(x: int) -> int:\n    return x + 1\n",
    )
    print(status7)

    status8 = replace_text(
        _abs_file_path("text5.py"),
        "    return x + 1\n",
        "    return (\n",
    )
    print(status8)

    print("\n--- TEST 5: successful replacement after edit boundary shift ---")
    status9 = write_file(
        _abs_file_path("text6.py"),
        "from typing import Any\n"
        "\n"
        "def alpha() -> int:\n"
        "    return 1\n"
        "\n"
        "def beta() -> int:\n"
        "    return 2\n"
        "\n"
        "def gamma() -> int:\n"
        "    return 3\n",
    )
    print(status9)

    status10 = replace_text(
        _abs_file_path("text6.py"),
        "def alpha() -> int:\n    return 1\n\ndef beta() -> int:\n    return 2\n",
        "def alpha() -> int:\n    return 1\n",
    )
    print(status10)

    print("\n--- TEST 6: fail because edit introduces LSP error elsewhere in file ---")
    status11 = write_file(
        _abs_file_path("text7.py"),
        "def get_value() -> int:\n"
        "    return 1\n"
        "\n"
        "def use_value() -> int:\n"
        "    value = get_value()\n"
        "    return value + 1\n",
    )
    print(status11)

    status12 = replace_text(
        _abs_file_path("text7.py"),
        "def get_value() -> int:\n    return 1\n",
        "def get_value() -> str:\n    return '1'\n",
    )
    print(status12)

    print(get_lsp_diagnostics(_abs_file_path("text7.py")))

    print(
        "\n--- TEST 7: success when file already has unrelated pre-existing LSP error ---"
    )
    status13 = write_file(
        _abs_file_path("text8.py"),
        "def broken() -> int:\n"
        "    return 'oops'\n"
        "\n"
        "def ok() -> int:\n"
        "    value = 1\n"
        "    return value\n",
    )
    print(status13)

    status14 = replace_text(
        _abs_file_path("text8.py"),
        "    value = 1\n",
        "    value = 2\n",
    )
    print(status14)

    print(get_lsp_diagnostics(_abs_file_path("text8.py")))

    print(
        "\n--- TEST 8: fail because shorter edit shifts lines and causes new error later ---"
    )
    status15 = write_file(
        _abs_file_path("text9.py"),
        "def a() -> int:\n"
        "    return 1\n"
        "\n"
        "def b() -> int:\n"
        "    return 2\n"
        "\n"
        "def c() -> int:\n"
        "    x = a()\n"
        "    return x + 1\n",
    )
    print(status15)

    status16 = replace_text(
        _abs_file_path("text9.py"),
        "def a() -> int:\n    return 1\n\ndef b() -> int:\n    return 2\n",
        "def a() -> str:\n    return '1'\n",
    )
    print(status16)

    print(read_file(_abs_file_path("text9.py")))
