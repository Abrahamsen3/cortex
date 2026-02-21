def isConfirmed(question: str) -> bool:
    while True:
        answer = input(f"{question} [y/n]").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
