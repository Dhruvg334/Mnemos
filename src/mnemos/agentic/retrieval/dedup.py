"""Duplicate Remover.

Removes duplicate evidence using content hashing and optional
semantic similarity comparison.
"""

from __future__ import annotations

import hashlib
from typing import Any


class DuplicateRemover:
    """Removes duplicate evidence entries.

    Uses a two-pass approach:
    1. Content hash deduplication (exact matches)
    2. Near-duplicate detection via first-N-words signature
    """

    def __init__(self, near_duplicate_threshold: float = 0.9) -> None:
        self.near_duplicate_threshold = near_duplicate_threshold

    def remove_duplicates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate candidates, keeping the highest-scored version."""
        if not candidates:
            return []

        # Pass 1: Exact content hash dedup
        hash_map: dict[str, dict[str, Any]] = {}
        for cand in candidates:
            content = cand.get("content", "")
            content_hash = self._content_hash(content)
            existing = hash_map.get(content_hash)
            if existing is None:
                hash_map[content_hash] = cand
            else:
                # Keep the one with higher score
                new_score = cand.get("rerank_score", cand.get("score", 0.0))
                old_score = existing.get("rerank_score", existing.get("score", 0.0))
                if new_score > old_score:
                    hash_map[content_hash] = cand

        # Pass 2: Near-duplicate detection via first-N-words signature
        deduped = list(hash_map.values())
        final: list[dict[str, Any]] = []
        seen_signatures: list[tuple[str, float]] = []

        for cand in deduped:
            content = cand.get("content", "")
            sig = self._first_words_signature(content, n=8)
            score = cand.get("rerank_score", cand.get("score", 0.0))
            is_near_dup = False

            for existing_sig, existing_score in seen_signatures:
                if self._signature_similarity(sig, existing_sig) >= self.near_duplicate_threshold:
                    if score <= existing_score:
                        is_near_dup = True
                        break

            if not is_near_dup:
                final.append(cand)
                seen_signatures.append((sig, score))

        return final

    def remove_region_duplicates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicates by evidence_region_id or chunk_id."""
        seen_ids: set[str] = set()
        unique: list[dict[str, Any]] = []

        for cand in candidates:
            meta = cand.get("metadata", {})
            rid = meta.get("evidence_region_id") or meta.get("chunk_id") or ""
            if rid and rid in seen_ids:
                continue
            if rid:
                seen_ids.add(rid)
            unique.append(cand)

        return unique

    @staticmethod
    def _content_hash(content: str) -> str:
        normalised = " ".join(content.lower().split())
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:32]

    @staticmethod
    def _first_words_signature(content: str, n: int = 8) -> str:
        words = content.lower().split()[:n]
        return " ".join(words)

    @staticmethod
    def _signature_similarity(sig_a: str, sig_b: str) -> float:
        if not sig_a or not sig_b:
            return 0.0
        set_a = set(sig_a.split())
        set_b = set(sig_b.split())
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0
