import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from .analytics import clean

# Interaction weights reflecting behavioral engagement strength
WEIGHTS = {
    "view": 1.0,
    "click": 1.5,
    "like": 3.0,
    "save": 4.0,
    "share": 5.0,
    "comment": 4.5,
}

# Signal weight distribution for hybrid scoring (total = 1.0)
MIX = {
    "content": 0.40,
    "collab": 0.25,
    "popularity": 0.15,
    "recency": 0.10,
    "feedback": 0.10,
}


def _norm(arr: np.ndarray) -> np.ndarray:
    """Normalize array values to 0.0 - 1.0 range."""
    if not isinstance(arr, np.ndarray) or arr.size == 0:
        return np.zeros(0, dtype=float)
    max_val = float(np.max(arr))
    min_val = float(np.min(arr))
    if max_val > min_val:
        return (arr - min_val) / (max_val - min_val)
    elif max_val > 0:
        return arr / max_val
    return np.zeros_like(arr, dtype=float)


class Recommender:
    """Hybrid Recommendation Engine combining Content-Based, Collaborative,

    Popularity, Recency, and User Feedback Signals with Explainability.
    """

    def __init__(
        self,
        analyzer,
        ids: list[int],
        interactions: list[tuple],
        user_interests: dict[int, list[str]] | None = None,
        user_feedback: dict[int, dict[int, str]] | None = None,
    ):
        self.an = analyzer
        self.ids = list(ids)
        self.idx = {cid: i for i, cid in enumerate(ids)}
        n = len(ids)

        self.user_interests = user_interests or {}
        self.user_feedback = user_feedback or {}

        # Build user-item interaction matrix
        self.users: dict[int, np.ndarray] = {}
        for interaction in interactions:
            uid = interaction[0]
            cid = interaction[1]
            kind = interaction[2]
            if cid in self.idx:
                if uid not in self.users:
                    self.users[uid] = np.zeros(n, dtype=float)
                weight = WEIGHTS.get(kind, 1.0)
                self.users[uid][self.idx[cid]] += weight

        # Interaction matrix R
        if self.users and n > 0:
            user_matrix = np.array(list(self.users.values())).reshape(-1, n)
            self.pop = _norm(np.log1p(user_matrix.sum(axis=0)))
            # Item-Item Cosine Similarity for Collaborative Filtering
            # Transpose so rows are items
            item_features = user_matrix.T
            if np.any(item_features):
                self.item_sim = cosine_similarity(item_features)
                np.nan_to_num(self.item_sim, copy=False, nan=0.0)
            else:
                self.item_sim = np.zeros((n, n), dtype=float)
        else:
            self.pop = np.zeros(n, dtype=float)
            self.item_sim = np.zeros((n, n), dtype=float)

        # Recency signal: linear decay based on publication order
        self.recency = (
            np.linspace(1.0, 0.25, n, dtype=float) if n > 1 else np.ones(n, dtype=float)
        )

    def _generate_reasons(
        self,
        cid: int,
        content_score: float,
        collab_score: float,
        pop_score: float,
        recency_score: float,
        feedback_score: float,
        user_interests: list[str],
    ) -> list[str]:
        """Generate human-readable explainable AI rationale for a recommendation."""
        reasons = []

        if content_score > 0.45:
            if user_interests:
                interests_str = ", ".join(user_interests[:3])
                reasons.append(f"Strongly aligns with your interests in {interests_str}")
            else:
                reasons.append("High contextual similarity to topics you explored")
        elif content_score > 0.25:
            reasons.append("Relevant to topics in your reading history")

        if collab_score > 0.35:
            reasons.append("Highly rated by users with similar reading habits")
        elif collab_score > 0.20:
            reasons.append("Frequently read alongside articles you viewed")

        if feedback_score > 0.5:
            reasons.append("Boosted based on your positive feedback")

        if pop_score > 0.55:
            reasons.append("Trending platform-wide with high engagement")
        elif pop_score > 0.30:
            reasons.append("Popular article among active readers")

        if recency_score > 0.80:
            reasons.append("Recently published fresh intelligence")

        if not reasons:
            reasons.append("Recommended based on balanced hybrid platform signals")

        return reasons

    def _compute_user_signals(self, uid: int):
        """Compute all 5 raw signals for user uid."""
        n = len(self.ids)
        if n == 0 or self.an is None or self.an.matrix is None:
            zeros = np.zeros(n, dtype=float)
            return zeros, zeros, zeros, zeros, zeros

        seen = self.users.get(uid, np.zeros(n, dtype=float))
        interests = self.user_interests.get(uid, [])

        # 1. Content Signal (interests + behavior history)
        interest_sim = np.zeros(n, dtype=float)
        if interests and self.an.vec is not None:
            try:
                interest_query = " ".join(interests)
                int_vec = self.an.vec.transform([clean(interest_query)])
                if int_vec.nnz > 0:
                    sim = cosine_similarity(int_vec, self.an.matrix).ravel()
                    interest_sim = _norm(np.nan_to_num(sim, nan=0.0))
            except Exception:
                interest_sim = np.zeros(n, dtype=float)

        behavior_sim = np.zeros(n, dtype=float)
        if seen.any() and self.an.matrix is not None:
            try:
                profile = self.an.matrix.T.dot(seen)
                sim = cosine_similarity(
                    profile.reshape(1, -1), self.an.matrix
                ).ravel()
                behavior_sim = _norm(np.nan_to_num(sim, nan=0.0))
            except Exception:
                behavior_sim = np.zeros(n, dtype=float)

        if interests and seen.any():
            content = 0.55 * interest_sim + 0.45 * behavior_sim
        elif interests:
            content = interest_sim
        elif seen.any():
            content = behavior_sim
        else:
            content = np.zeros(n, dtype=float)

        # 2. Collaborative Signal
        if seen.any() and self.item_sim.shape[0] == n:
            collab = _norm(self.item_sim @ seen)
        else:
            collab = np.zeros(n, dtype=float)

        # 3. Popularity Signal
        popularity = self.pop.copy()

        # 4. Recency Signal
        recency = self.recency.copy()

        # 5. Feedback Signal
        feedback = np.zeros(n, dtype=float)
        uf = self.user_feedback.get(uid, {})
        for cid, f_val in uf.items():
            if cid in self.idx:
                idx = self.idx[cid]
                if f_val == "liked":
                    feedback[idx] = 1.0
                elif f_val == "saved":
                    feedback[idx] = 0.8
                elif f_val == "clicked":
                    feedback[idx] = 0.3
                elif f_val == "ignored":
                    feedback[idx] = -0.3
                elif f_val == "disliked":
                    feedback[idx] = -1.5

        return content, collab, popularity, recency, feedback

    def for_user(self, uid: int, k: int = 10, content_type: str | None = None) -> list[dict]:
        """Generate top-k personalized recommendations for a given user."""
        n = len(self.ids)
        if n == 0:
            return []

        content, collab, popularity, recency, feedback = self._compute_user_signals(uid)
        seen = self.users.get(uid, np.zeros(n, dtype=float))
        interests = self.user_interests.get(uid, [])

        # Combined hybrid scoring
        score = (
            MIX["content"] * content
            + MIX["collab"] * collab
            + MIX["popularity"] * popularity
            + MIX["recency"] * recency
            + MIX["feedback"] * np.clip(feedback, -1.0, 1.0)
        )

        # If user has zero profile signals, boost popularity and recency
        if not seen.any() and not interests:
            score = 0.65 * popularity + 0.35 * recency

        # Disliked items are excluded
        disliked_mask = feedback <= -1.0
        score[disliked_mask] = -np.inf

        # For unconsumed vs consumed: prefer unconsumed items by giving
        # a modest penalty to already consumed items, but DO NOT eliminate them
        # so catalog is never empty!
        consumed_mask = seen > 0
        penalized_score = score.copy()
        penalized_score[consumed_mask] -= 0.35

        ranked_indices = np.argsort(penalized_score)[::-1]
        out = []

        for j in ranked_indices:
            cid = self.ids[j]
            s = float(penalized_score[j])
            if not np.isfinite(s) or s < -99:
                continue

            reasons = self._generate_reasons(
                cid,
                float(content[j]),
                float(collab[j]),
                float(popularity[j]),
                float(recency[j]),
                float(feedback[j]),
                interests,
            )

            why = {
                "content": round(float(content[j]), 3),
                "collaborative": round(float(collab[j]), 3),
                "popularity": round(float(popularity[j]), 3),
                "recency": round(float(recency[j]), 3),
                "feedback": round(float(feedback[j]), 3),
                "reasons": reasons,
            }

            out.append({
                "id": cid,
                "score": round(max(0.01, float(score[j])), 4),
                "why": why,
                "consumed": bool(consumed_mask[j]),
            })

            if len(out) >= k:
                break

        return out

    def similar(self, cid: int, k: int = 5) -> list[dict]:
        """Find most similar content items using TF-IDF cosine similarity."""
        if cid not in self.idx or self.an is None or self.an.matrix is None:
            return []

        i = self.idx[cid]
        sim = cosine_similarity(self.an.matrix[i], self.an.matrix).ravel()
        sim = sim.astype(float).copy()
        sim[i] = -np.inf  # Exclude self

        ranked = np.argsort(sim)[::-1]
        out = []
        for j in ranked[:k]:
            if not np.isfinite(sim[j]) or sim[j] <= 0:
                break
            matched_keywords = []
            if hasattr(self.an, "keywords"):
                matched_keywords = self.an.keywords(j, n=4)
            out.append({
                "id": self.ids[j],
                "score": round(float(sim[j]), 4),
                "why": {
                    "content": round(float(sim[j]), 3),
                    "reasons": [f"High content similarity ({round(float(sim[j]) * 100)}%)"],
                },
                "keywords": matched_keywords,
            })
        return out

    def trending(self, k: int = 10) -> list[dict]:
        """Rank items by dynamic popularity and recency velocity."""
        n = len(self.ids)
        if n == 0:
            return []

        trending_score = 0.65 * self.pop + 0.35 * self.recency
        ranked = np.argsort(trending_score)[::-1]

        out = []
        for rank, j in enumerate(ranked[:k], start=1):
            s = float(trending_score[j])
            out.append({
                "id": self.ids[j],
                "rank": rank,
                "score": round(s, 4),
                "why": {
                    "popularity": round(float(self.pop[j]), 3),
                    "recency": round(float(self.recency[j]), 3),
                    "reasons": [f"Trending #{rank} with high audience momentum"],
                },
            })
        return out

    def explain(self, uid: int, cid: int) -> dict:
        """Provide detailed, full signal breakdown for any given content item."""
        if cid not in self.idx:
            return {"id": cid, "error": "Item not found in recommendation index."}

        j = self.idx[cid]
        content, collab, popularity, recency, feedback = self._compute_user_signals(uid)
        interests = self.user_interests.get(uid, [])
        seen = self.users.get(uid, np.zeros(len(self.ids), dtype=float))

        reasons = self._generate_reasons(
            cid,
            float(content[j]),
            float(collab[j]),
            float(popularity[j]),
            float(recency[j]),
            float(feedback[j]),
            interests,
        )

        total_score = (
            MIX["content"] * float(content[j])
            + MIX["collab"] * float(collab[j])
            + MIX["popularity"] * float(popularity[j])
            + MIX["recency"] * float(recency[j])
            + MIX["feedback"] * float(feedback[j])
        )

        return {
            "id": cid,
            "score": round(float(total_score), 4),
            "consumed": bool(seen[j] > 0),
            "weights": MIX,
            "why": {
                "content": round(float(content[j]), 3),
                "collaborative": round(float(collab[j]), 3),
                "popularity": round(float(popularity[j]), 3),
                "recency": round(float(recency[j]), 3),
                "feedback": round(float(feedback[j]), 3),
                "reasons": reasons,
            },
        }
