"""Fit the operation classifier and serialize coefficients for dependency-light serving."""
import json
from pathlib import Path
import sys
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chartproof.language import tokens


dataset = json.loads((ROOT / "evaluation/training.json").read_text())
phrases = [s for phrases in dataset.values() for s in phrases]
labels = [label for label, phrases_for_label in dataset.items() for _ in phrases_for_label]
vectorizer = TfidfVectorizer(analyzer=tokens, lowercase=False)
matrix = vectorizer.fit_transform(phrases)
classifier = LogisticRegression(C=12, max_iter=1000, random_state=901).fit(matrix, labels)
model = {"classes": classifier.classes_.tolist(), "vocab": {k: int(v) for k, v in vectorizer.vocabulary_.items()},
         "idf": vectorizer.idf_.round(10).tolist(), "coef": classifier.coef_.round(10).tolist(),
         "intercept": classifier.intercept_.round(10).tolist()}
(ROOT / "chartproof/model.json").write_text(json.dumps(model, separators=(",", ":"), sort_keys=True) + "\n")
print(f"Trained on {len(labels)} labeled examples across {len(dataset)} classes.")
