from ..api import get_lsp_diagnostics, read_file, replace_text, write_file
from ..filesystem import _abs_file_path, _read_text

if __name__ == "__main__":
    print("\n--- TEST 1: successful replacement on copied real file ---")
    status1 = write_file(
        _abs_file_path("test1.py"),
        _read_text(_abs_file_path("src/cortex/tools/editor/text.py")),
    )
    print(status1)

    status2 = replace_text(
        _abs_file_path("test1.py"),
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
        _abs_file_path("test2.py"),
        "def foo() -> int:\n    value = 1\n    return value\n",
    )
    print(status3)

    status4 = replace_text(
        _abs_file_path("test2.py"),
        "    value = 2\n",
        "    value = 3\n",
    )
    print(status4)

    print("\n--- TEST 3: fail because old_text occurs more than once ---")
    status5 = write_file(
        _abs_file_path("test3.py"),
        "x = 1\nprint(x)\nx = 1\n",
    )
    print(status5)

    status6 = replace_text(
        _abs_file_path("test3.py"),
        "x = 1",
        "x = 2",
    )
    print(status6)

    print("\n--- TEST 4: fail because replacement introduces LSP/parser error ---")
    status7 = write_file(
        _abs_file_path("test4.py"),
        "def add_one(x: int) -> int:\n    return x + 1\n",
    )
    print(status7)

    status8 = replace_text(
        _abs_file_path("test4.py"),
        "    return x + 1\n",
        "    return (\n",
    )
    print(status8)

    print("\n--- TEST 5: successful replacement after edit boundary shift ---")
    status9 = write_file(
        _abs_file_path("test5.py"),
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
        _abs_file_path("test5.py"),
        "def alpha() -> int:\n    return 1\n\ndef beta() -> int:\n    return 2\n",
        "def alpha() -> int:\n    return 1\n",
    )
    print(status10)

    print("\n--- TEST 6: fail because edit introduces LSP error elsewhere in file ---")
    status11 = write_file(
        _abs_file_path("test6.py"),
        "def get_value() -> int:\n"
        "    return 1\n"
        "\n"
        "def use_value() -> int:\n"
        "    value = get_value()\n"
        "    return value + 1\n",
    )
    print(status11)

    status12 = replace_text(
        _abs_file_path("test6.py"),
        "def get_value() -> int:\n    return 1\n",
        "def get_value() -> str:\n    return '1'\n",
    )
    print(status12)

    print(get_lsp_diagnostics(_abs_file_path("text7.py")))

    print(
        "\n--- TEST 7: success when file already has unrelated pre-existing LSP error ---"
    )
    status13 = write_file(
        _abs_file_path("test7.py"),
        "def broken() -> int:\n"
        "    return 'oops'\n"
        "\n"
        "def ok() -> int:\n"
        "    value = 1\n"
        "    return value\n",
    )
    print(status13)

    status14 = replace_text(
        _abs_file_path("test7.py"),
        "    value = 1\n",
        "    value = 2\n",
    )
    print(status14)

    print(get_lsp_diagnostics(_abs_file_path("text8.py")))

    print(
        "\n--- TEST 8: fail because shorter edit shifts lines and causes new error later ---"
    )
    status15 = write_file(
        _abs_file_path("test8.py"),
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
        _abs_file_path("test8.py"),
        "def a() -> int:\n    return 1\n\ndef b() -> int:\n    return 2\n",
        "def a() -> str:\n    return '1'\n",
    )
    print(status16)

    print(read_file(_abs_file_path("test8.py")))
