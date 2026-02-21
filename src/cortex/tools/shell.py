import subprocess


def runShell(cmd: str) -> str:
    """
    Run a shell command in bash login shell
    """
    command = subprocess.run(
        ["/bin/bash", "-lc", cmd],
        text=True,
        capture_output=True,
    )

    return (command.stdout or "") + (command.stderr or "")
