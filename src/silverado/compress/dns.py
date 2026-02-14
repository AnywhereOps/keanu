"""
COEF DNS: Content-Addressable Store
====================================
The barcode system. Hash -> exact content. Lossless by definition.
Nothing is reconstructed because nothing is disassembled.
"""

import hashlib
import json
from pathlib import Path


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ContentDNS:
    def __init__(self, storage_dir: str | None = None):
        self._by_hash: dict[str, str] = {}
        self._names: dict[str, str] = {}
        self._storage_dir = Path(storage_dir) if storage_dir else None
        if self._storage_dir:
            self._storage_dir.mkdir(parents=True, exist_ok=True)
            self._load()

    def store(self, content: str, name: str | None = None) -> str:
        h = sha256(content)
        self._by_hash[h] = content
        if name:
            self._names[name] = h
        if self._storage_dir:
            p = self._storage_dir / f"{h[:16]}.json"
            with open(p, "w") as f:
                json.dump({"hash": h, "content": content, "name": name}, f)
        return h

    def resolve(self, ref: str) -> str:
        if ref in self._names:
            return self._by_hash[self._names[ref]]
        if ref in self._by_hash:
            return self._by_hash[ref]
        matches = [h for h in self._by_hash if h.startswith(ref)]
        if len(matches) == 1:
            return self._by_hash[matches[0]]
        if len(matches) > 1:
            raise KeyError(f"Ambiguous: '{ref}'")
        raise KeyError(f"'{ref}' not in DNS. Have: {list(self._names.keys())}")

    def has(self, ref: str) -> bool:
        try:
            self.resolve(ref)
        except KeyError:
            return False
        return True

    def hash_of(self, ref: str) -> str:
        if ref in self._names:
            return self._names[ref]
        if ref in self._by_hash:
            return ref
        m = [h for h in self._by_hash if h.startswith(ref)]
        if len(m) == 1:
            return m[0]
        raise KeyError(f"'{ref}' not found")

    def verify(self, ref: str, content: str) -> bool:
        try:
            return sha256(self.resolve(ref)) == sha256(content)
        except KeyError:
            return False

    def names(self) -> dict[str, str]:
        return dict(self._names)

    def _load(self):
        for p in self._storage_dir.glob("*.json"):
            with open(p) as f:
                e = json.load(f)
                self._by_hash[e["hash"]] = e["content"]
                if e.get("name"):
                    self._names[e["name"]] = e["hash"]
