import hashlib
import os
import tempfile


def _abs_file_path(path: str) -> str:
    """
    Convert a file path to an absolute path and validate it ends with .py.

    Args:
        path: File path to convert to absolute path.

    Returns:
        Absolute path to the Python file.

    Raises:
        ValueError: If the path does not end with .py extension.
    """
    abs_path = os.path.abspath(path)
    if not abs_path.endswith(".py"):
        raise ValueError(f"Only Python files are supported (.py). Got: {abs_path}")
    return abs_path


def _read_text(abs_path: str) -> str:
    """
    Read the contents of a file and return as a string.

    Args:
        abs_path: Absolute path to the file to read.

    Returns:
        Contents of the file as a string.

    Raises:
        FileNotFoundError: If the file does not exist.
        PermissionError: If permission is denied to read the file.
        UnicodeDecodeError: If the file cannot be decoded as UTF-8.
        OSError: For other file I/O errors.
    """
    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(abs_path: str, content: str) -> None:
    """
    Write content to a file, creating parent directories if needed.

    Args:
        abs_path: Absolute path to the file to write.
        content: String content to write to the file.

    Raises:
        PermissionError: If permission is denied to write to the path.
        OSError: If parent directories cannot be created or other I/O errors occur.
        UnicodeEncodeError: If content cannot be encoded as UTF-8.
    """
    dir_path = os.path.dirname(abs_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(abs_path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def _atomic_write_text(abs_path: str, content: str) -> None:
    """
    Write content to a file atomically using a temporary file.

    This ensures the target file is only updated if the write succeeds completely.

    Args:
        abs_path: Absolute path to the file to write.
        content: String content to write to the file.

    Raises:
        PermissionError: If permission is denied to create the temp file or write to the target.
        OSError: If temporary file creation fails, write fails, or temp file cleanup fails.
        UnicodeEncodeError: If content cannot be encoded as UTF-8.
        TimeoutExpired: If the file operation times out (rare).
    """
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


def _get_text_SHA256(text: str) -> str:
    """
    Compute the SHA-256 hash of a text string.

    Args:
        text: The text to hash.

    Returns:
        Hexadecimal string representing the SHA-256 hash of the text.
    """
    return hashlib.sha256(text.encode()).hexdigest()
