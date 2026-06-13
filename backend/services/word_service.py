import re


LETTER_PATTERN = re.compile(r"^[A-Z]+$")
MAX_WORD_LENGTH = 7


def normalize_word(word: str) -> str:
    normalized = word.strip().upper()
    if not normalized:
        raise ValueError("word must not be empty")
    if len(normalized) > MAX_WORD_LENGTH:
        raise ValueError(f"word must be {MAX_WORD_LENGTH} characters or fewer")
    if not LETTER_PATTERN.fullmatch(normalized):
        raise ValueError("word may contain only A-Z letters")
    return normalized


def split_letters(word: str) -> list[str]:
    return list(word)
