"""Small TF-IDF logistic regression classifier with a portable inference format."""
import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tokens(text):
    text = re.sub(r"\b(?:19|20)\d{2}\b", " year ", text.lower())
    text = re.sub(r"\d+(?:\.\d+)?", " num ", text).replace("%", " percent ")
    words = re.findall(r"[a-z]+", text)
    return words + [" ".join(pair) for pair in zip(words, words[1:])]


@lru_cache
def weights():
    return json.loads((ROOT / "chartproof/model.json").read_text())


def classify(text):
    model = weights()
    counts = Counter(tokens(text))
    known = {model["vocab"][term]: count for term, count in counts.items() if term in model["vocab"]}
    vec = {i: count * model["idf"][i] for i, count in known.items()}
    norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
    scores = [bias + sum(row[i] * w / norm for i, w in vec.items())
              for row, bias in zip(model["coef"], model["intercept"])]
    exps = [math.exp(s - max(scores)) for s in scores]
    best = max(range(len(scores)), key=scores.__getitem__)
    return model["classes"][best], round(exps[best] / sum(exps), 3)
