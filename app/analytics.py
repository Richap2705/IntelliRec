import re
import numpy as np
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from .config import N_TOPICS

_sia = SentimentIntensityAnalyzer()
_NOISE = re.compile(r"https?://\S+|@\w+|#|[^\w\s.,!?-]")


def strip_noise(text: str) -> str:
    """Strip URLs, handles, and excessive special characters."""
    if not text:
        return ""
    cleaned = _NOISE.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def clean(text: str) -> str:
    """Normalize and lower text for NLP feature extraction."""
    return strip_noise(text).lower()


def sentiment(text: str) -> float:
    """Return compound VADER sentiment score between -1.0 and 1.0."""
    if not text or not text.strip():
        return 0.0
    return float(_sia.polarity_scores(strip_noise(text))["compound"])


def sentiment_detail(text: str) -> dict:
    """Return comprehensive VADER sentiment polarity distribution and classification."""
    if not text or not text.strip():
        return {
            "compound": 0.0,
            "pos": 0.0,
            "neu": 1.0,
            "neg": 0.0,
            "label": "neutral",
        }
    scores = _sia.polarity_scores(strip_noise(text))
    comp = float(scores["compound"])
    return {
        "compound": round(comp, 3),
        "pos": round(float(scores["pos"]), 3),
        "neu": round(float(scores["neu"]), 3),
        "neg": round(float(scores["neg"]), 3),
        "label": label(comp),
    }


def label(score: float) -> str:
    """Categorize sentiment compound score into positive, neutral, or negative."""
    if score >= 0.05:
        return "positive"
    elif score <= -0.05:
        return "negative"
    return "neutral"


class Analyzer:
    """NLP and Topic Extraction Engine using TF-IDF and Non-Negative Matrix Factorization (NMF)."""

    def __init__(self):
        self.ids = []
        self.vec = None
        self.matrix = None
        self.terms_ = np.array([])
        self.topic_terms = []
        self.doc_topic = np.array([])
        self.nmf_model = None

    def fit(self, docs):
        """Fit TF-IDF vectorizer and NMF topic model on input documents [(id, title, body)]."""
        if not docs:
            self.ids = []
            self.matrix = None
            return self

        self.ids = [d[0] for d in docs]
        texts = [clean(f"{d[1]}. {d[2]}") for d in docs]

        # TF-IDF Vectorization
        self.vec = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            max_df=0.95,
        )

        self.matrix = self.vec.fit_transform(texts)
        self.terms_ = self.vec.get_feature_names_out()

        # Determine safe number of topics
        n_features = self.matrix.shape[1]
        n_samples = len(docs)
        max_topics = min(n_samples, n_features)
        k = max(1, min(N_TOPICS, max_topics))

        # Ensure C-contiguous float64 array for NMF stability on Windows
        matrix_dense = np.ascontiguousarray(
            self.matrix.toarray(), dtype=np.float64
        )

        try:
            self.nmf_model = NMF(
                n_components=k,
                init="random",
                random_state=42,
                max_iter=500,
                solver="cd",
            )
            weights = self.nmf_model.fit_transform(matrix_dense)

            self.topic_terms = []
            for component in self.nmf_model.components_:
                top_indices = component.argsort()[-6:][::-1]
                terms = [
                    self.terms_[i]
                    for i in top_indices
                    if i < len(self.terms_) and component[i] > 0
                ]
                if not terms:
                    terms = ["general", "insights", "content"]
                self.topic_terms.append(terms)

            self.doc_topic = weights.argmax(axis=1)
        except Exception:
            # Fallback if NMF fails on edge cases
            self.topic_terms = [["content", "media", "technology"]]
            self.doc_topic = np.zeros(n_samples, dtype=int)

        return self

    def _top(self, row, n=6):
        """Get top n non-zero term features from a vector."""
        if self.terms_.size == 0 or row.size == 0:
            return []
        nonzero_idx = np.where(row > 0)[0]
        if nonzero_idx.size == 0:
            return []
        sorted_sub = nonzero_idx[np.argsort(row[nonzero_idx])[::-1][:n]]
        return [self.terms_[i] for i in sorted_sub]

    def keywords(self, index: int, n: int = 6):
        """Extract top TF-IDF keywords for document by internal row index."""
        if self.matrix is None or index >= self.matrix.shape[0]:
            return []
        row = self.matrix[index].toarray().ravel()
        return self._top(row, n)

    def terms(self, text: str, n: int = 6):
        """Extract top TF-IDF keywords for arbitrary query or text."""
        if not self.vec or not text.strip():
            return []
        try:
            row = self.vec.transform([clean(text)]).toarray().ravel()
            return self._top(row, n)
        except Exception:
            return []

    def predict_topic(self, text: str) -> int:
        """Predict the most relevant NMF topic index for arbitrary text."""
        if not self.vec or not self.nmf_model or not text.strip():
            return 0
        try:
            row = self.vec.transform([clean(text)])
            weights = self.nmf_model.transform(
                np.ascontiguousarray(row.toarray(), dtype=np.float64)
            )
            return int(weights.argmax(axis=1)[0])
        except Exception:
            return 0