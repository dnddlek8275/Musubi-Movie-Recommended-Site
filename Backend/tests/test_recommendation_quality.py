import unittest

from app.models.movies import Movie
from app.services.movies.recommendation_service import (
    CONTENT_MINIMUM_VOTES,
    GUEST_PREFERENCE_WEIGHT,
    PREFERENCE_WEIGHT,
    bayesian_rating,
    diversify_recommendations,
    preference_confidence,
    qualifies_content_candidate,
)
from app.services.preference_service import (
    CORE_PREFERENCE_LIMITS,
    CORE_PREFERENCE_SHARES,
    CURATED_LEARNABLE_KEYWORDS,
    canonicalize_keyword,
    core_movie_preference_items,
    is_learnable_keyword,
    PreferenceSignal,
    rating_preference_signal,
)
from app.services.movies.genre_relevance import (
    genre_relevance_score,
    weighted_genre_similarity,
)


class RecommendationQualityTests(unittest.TestCase):
    def test_single_weak_view_does_not_become_full_preference(self):
        weak = PreferenceSignal("genre", "SF", 0.057, behavior_score=0.057)
        repeated = PreferenceSignal("genre", "SF", 6.0, behavior_score=6.0)

        self.assertLess(preference_confidence(weak), 0.02)
        self.assertGreater(preference_confidence(repeated), 0.6)

    def test_explicit_preference_remains_strong_without_forcing_full_score(self):
        explicit = PreferenceSignal(
            "genre", "SF", 3.0, behavior_score=0.0, explicit=True
        )

        self.assertEqual(preference_confidence(explicit), 0.75)

    def test_negative_rating_signal_can_reduce_a_preference(self):
        disliked = PreferenceSignal("genre", "공포", -1.0, behavior_score=-1.0)

        self.assertLess(preference_confidence(disliked), 0)

    def test_rating_signal_is_negative_neutral_or_positive(self):
        self.assertLess(rating_preference_signal(1.0), 0)
        self.assertEqual(rating_preference_signal(3.0), 0)
        self.assertGreater(rating_preference_signal(5.0), 0)
        self.assertLess(abs(rating_preference_signal(1.0)), rating_preference_signal(5.0))

    def test_few_vote_ten_is_shrunk_toward_average(self):
        sparse = Movie(title="sparse", vote_average=10.0, vote_count=2)
        trusted = Movie(title="trusted", vote_average=8.0, vote_count=10_000)

        self.assertLess(bayesian_rating(sparse, 6.0, 100), 6.1)
        self.assertGreater(
            bayesian_rating(trusted, 6.0, 100),
            bayesian_rating(sparse, 6.0, 100),
        )

    def test_few_votes_are_excluded_without_a_strong_relation(self):
        source = Movie(title="source", genres=["드라마", "로맨스"])
        sparse = Movie(
            title="sparse",
            genres=["드라마", "로맨스"],
            vote_average=9.5,
            vote_count=1,
        )
        trusted = Movie(
            title="trusted",
            genres=["드라마", "로맨스"],
            vote_average=8.0,
            vote_count=CONTENT_MINIMUM_VOTES,
        )

        sparse_qualifies, _ = qualifies_content_candidate(source, sparse)
        trusted_qualifies, _ = qualifies_content_candidate(source, trusted)

        self.assertFalse(sparse_qualifies)
        self.assertTrue(trusted_qualifies)

    def test_strong_relation_allows_a_low_vote_exception(self):
        source = Movie(title="source", genres=["액션"], cast=["배우 A"])
        related = Movie(
            title="related",
            genres=["액션"],
            cast=["배우 A"],
            vote_count=1,
        )

        qualifies, shared = qualifies_content_candidate(source, related)

        self.assertTrue(shared["strong_relation"])
        self.assertTrue(qualifies)

    def test_diversity_can_promote_a_different_genre(self):
        candidates = [
            {"movie_id": 1, "genres": ["SF", "액션"], "recommendation_score": 10.0},
            {"movie_id": 2, "genres": ["SF", "액션"], "recommendation_score": 9.8},
            {"movie_id": 3, "genres": ["드라마"], "recommendation_score": 9.5},
        ]

        result = diversify_recommendations(candidates, 3)

        self.assertEqual([item["movie_id"] for item in result[:2]], [1, 3])

    def test_interacted_movies_do_not_dominate_personalized_results(self):
        candidates = [
            {
                "movie_id": index,
                "genres": ["로맨스"],
                "recommendation_score": 20.0 - index,
                "_is_interacted": True,
                "_interaction_kind": "like" if index <= 2 else "view",
            }
            for index in range(1, 13)
        ] + [
            {
                "movie_id": 100 + index,
                "genres": ["로맨스", "드라마"],
                "recommendation_score": 8.0 - index / 10,
                "_is_interacted": False,
            }
            for index in range(1, 13)
        ]

        result = diversify_recommendations(candidates, 12)

        interacted_count = sum(item["movie_id"] < 100 for item in result)
        self.assertLessEqual(interacted_count, 4)
        self.assertIn(1, [item["movie_id"] for item in result])

    def test_actor_is_only_a_supporting_preference_signal(self):
        self.assertLess(PREFERENCE_WEIGHT["actor"], PREFERENCE_WEIGHT["genre"])
        self.assertLess(PREFERENCE_WEIGHT["actor"], PREFERENCE_WEIGHT["keyword"])
        self.assertLess(GUEST_PREFERENCE_WEIGHT["actor"], GUEST_PREFERENCE_WEIGHT["genre"])
        self.assertLess(GUEST_PREFERENCE_WEIGHT["actor"], GUEST_PREFERENCE_WEIGHT["keyword"])
        self.assertEqual(CORE_PREFERENCE_LIMITS["actor"], 3)
        self.assertLess(CORE_PREFERENCE_SHARES["actor"], 0.1)
        self.assertAlmostEqual(sum(CORE_PREFERENCE_SHARES.values()), 1.0)

    def test_keywords_distinguish_primary_and_secondary_genres(self):
        romance = Movie(
            title="romance",
            genres=["로맨스", "액션"],
            keywords=["first love", "dating", "wedding"],
        )
        action = Movie(
            title="action",
            genres=["로맨스", "액션"],
            keywords=["gunfight", "combat", "martial arts"],
        )

        self.assertGreater(
            genre_relevance_score(romance, "로맨스"),
            genre_relevance_score(romance, "액션"),
        )
        self.assertEqual(genre_relevance_score(romance, "로맨스"), 1.0)
        self.assertLessEqual(genre_relevance_score(romance, "액션"), 0.25)
        self.assertGreater(
            genre_relevance_score(action, "액션"),
            genre_relevance_score(action, "로맨스"),
        )

    def test_weighted_genre_similarity_uses_keyword_emphasis(self):
        source = Movie(title="source", genres=["로맨스", "액션"], keywords=["first love"])
        romantic = Movie(title="romantic", genres=["로맨스", "드라마"], keywords=["wedding"])
        action = Movie(title="action", genres=["액션", "드라마"], keywords=["gunfight"])

        self.assertGreater(
            weighted_genre_similarity(source, romantic),
            weighted_genre_similarity(source, action),
        )

    def test_behavior_learning_excludes_a_weak_secondary_genre(self):
        movie = Movie(
            title="romance",
            genres=["로맨스", "액션"],
            keywords=["first love", "dating", "wedding"],
        )

        learned_genres = dict(core_movie_preference_items(movie)["genre"])

        self.assertEqual(learned_genres, {"로맨스": 1.0})

    def test_behavior_learning_keeps_only_curated_taste_keywords(self):
        movie = Movie(
            title="editor romance",
            genres=["로맨스"],
            keywords=[
                "magazine editor",
                "advertising",
                "body exchange",
                "romcom",
                "bromance",
                "magic",
            ],
        )

        learned_keywords = dict(core_movie_preference_items(movie)["keyword"])

        self.assertEqual(
            learned_keywords,
            {"romcom": 1.0, "bromance": 1.0, "magic": 1.0},
        )

    def test_curated_keyword_taxonomy_has_sixty_canonical_values(self):
        self.assertEqual(len(CURATED_LEARNABLE_KEYWORDS), 60)
        self.assertEqual(canonicalize_keyword("사랑"), "romance")
        self.assertEqual(canonicalize_keyword("teenage romance"), "romance")
        self.assertEqual(canonicalize_keyword("aliens"), "alien")
        self.assertFalse(is_learnable_keyword("maze"))
        self.assertFalse(is_learnable_keyword("teleportation"))

    def test_behavior_learning_merges_keyword_aliases_before_scoring(self):
        movie = Movie(
            title="aliases",
            genres=["로맨스", "SF"],
            keywords=["love", "로맨스", "teenage romance", "alien", "aliens"],
        )

        learned_keywords = dict(core_movie_preference_items(movie)["keyword"])

        self.assertEqual(learned_keywords, {"romance": 1.0, "alien": 1.0})

    def test_weak_shared_genres_do_not_make_movies_related(self):
        source = Movie(
            title="source",
            genres=["로맨스", "액션", "범죄"],
            keywords=["first love", "wedding"],
        )
        candidate = Movie(
            title="candidate",
            genres=["코미디", "액션", "범죄"],
            keywords=["satire"],
            vote_count=CONTENT_MINIMUM_VOTES,
        )

        qualifies, shared = qualifies_content_candidate(source, candidate)

        self.assertEqual(shared["genre_count"], 0)
        self.assertFalse(qualifies)


if __name__ == "__main__":
    unittest.main()
