"""轻量、离线、可复现的中文字符 n-gram 哈希向量。"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any


def normalize_text(text: str) -> str:
    """保留中英文和数字并统一大小写，消除空格与常见标点差异。"""
    return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", text.lower()))


def char_ngrams(text: str, sizes: tuple[int, ...] = (1, 2, 3)) -> list[str]:
    normalized = normalize_text(text)
    grams: list[str] = []
    for size in sizes:
        grams.extend(
            normalized[index : index + size]
            for index in range(max(len(normalized) - size + 1, 0))
        )
    return grams


def hashing_vector(text: str, dimensions: int = 384) -> list[float]:
    """使用稳定哈希生成归一化向量，不依赖 Python 的随机 hash seed。"""
    vector = [0.0] * dimensions
    for gram in char_ngrams(text):
        digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        index = value % dimensions
        sign = 1.0 if value & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        return [value / norm for value in vector]
    return vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


class HashingEmbeddingFunction:
    """兼容 ChromaDB 1.x EmbeddingFunction 协议。"""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [hashing_vector(text, self.dimensions) for text in input]

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        return "zh-char-ngram-hashing"

    def get_config(self) -> dict[str, Any]:
        return {"dimensions": self.dimensions}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "HashingEmbeddingFunction":
        return HashingEmbeddingFunction(int(config.get("dimensions", 384)))

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> list[str]:
        return ["cosine", "l2", "ip"]
