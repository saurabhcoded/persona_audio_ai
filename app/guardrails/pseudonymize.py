import re

# Contact names that are really roles; replacing them in text would erase the persona's style.
_ROLE_WORDS = {
    "bhai", "bro", "didi", "di", "mom", "mummy", "mumma", "maa", "papa", "dad", "daddy",
    "sir", "madam", "boss", "babu", "baby", "jaan", "dear", "uncle", "aunty", "bhaiya",
    "chacha", "chachi", "mama", "mami", "nana", "nani", "dada", "dadi", "home", "office",
}  # fmt: skip
_PHONE_SENDER = re.compile(r"^\+?[\d\s()-]{7,}$")


class Pseudonymizer:
    """Consistent pseudonyms for third-party participants: senders become `Person_N`
    (or `Contact_N` for unsaved numbers) and their names in message text are replaced
    case-sensitively, so lowercase words that happen to match a name survive."""

    def __init__(self, keep: set[str], others: list[str]):
        self.keep = keep
        self.senders: dict[str, str] = {}
        tokens: dict[str, str] = {}
        keep_tokens = {t.lower() for name in keep for t in name.split()}
        for i, name in enumerate(others, 1):
            fake = f"Contact_{i}" if _PHONE_SENDER.match(name) else f"Person_{i}"
            self.senders[name] = fake
            if fake.startswith("Contact_"):
                continue
            candidates = [name] + name.split()[:1]
            for token in candidates:
                low = token.lower()
                if (
                    len(token) >= 3
                    and low not in _ROLE_WORDS
                    and low not in keep_tokens
                ):
                    tokens.setdefault(token, fake)
        names = sorted(tokens, key=len, reverse=True)
        self._tokens = tokens
        self._pattern = (
            re.compile(r"(?<!\w)(" + "|".join(map(re.escape, names)) + r")(?!\w)")
            if names
            else None
        )

    def sender(self, name: str) -> str:
        return name if name in self.keep else self.senders.get(name, name)

    def text(self, text: str) -> str:
        if self._pattern is None:
            return text
        return self._pattern.sub(lambda m: self._tokens[m.group(1)], text)
