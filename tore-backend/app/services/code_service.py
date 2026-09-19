"""Small random-code helper independent from legacy runtime."""

import secrets
import string


def random_code(n: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


__all__ = ["random_code"]
