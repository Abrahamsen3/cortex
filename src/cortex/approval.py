def isConfirmed(question: str) -> str:
    while True:
        answer = input(f"{question} [y/n/e]: ").strip().lower()
        if answer in ("y", "yes"):
            return "yes"
        if answer in ("n", "no"):
            return "no"
        if answer in ("e", "edit"):
            return "edit"
