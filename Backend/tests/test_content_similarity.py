import unittest
from datetime import date

from app.models.movies import Movie
from app.services.movies.recommendation_service import (
    CONTENT_MINIMUM_VOTES,
    bayesian_rating,
    calculate_content_similarity,
    qualifies_content_candidate,
)


class ContentSimilarityTests(unittest.TestCase):
    def test_missing_axes_do_not_redistribute_weight(self):
        source = Movie(title="source", genres=["SF"])
        candidate = Movie(title="candidate", genres=["SF"])

        score, components = calculate_content_similarity(source, candidate, global_average=6.0)

        self.assertEqual(components, {"genre": 1.0})
        self.assertEqual(score, 0.3)

    def test_more_content_overlap_scores_higher(self):
        source = Movie(
            title="source",
            genres=["SF", "Drama"],
            keywords=["space", "survival"],
            cast=["Actor A", "Actor B"],
            director="Director A",
            production_countries=["KR"],
            language="ko",
            release_date=date(2020, 1, 1),
            runtime=120,
        )
        close = Movie(
            title="close",
            genres=["SF", "Drama"],
            keywords=["space", "survival"],
            cast=["Actor A", "Actor B"],
            director="Director A",
            production_countries=["KR"],
            language="ko",
            release_date=date(2021, 1, 1),
            runtime=125,
        )
        distant = Movie(
            title="distant",
            genres=["SF", "Comedy"],
            keywords=["friendship"],
            cast=["Actor C"],
            director="Director B",
            production_countries=["US"],
            language="en",
            release_date=date(1990, 1, 1),
            runtime=70,
        )

        close_score, _ = calculate_content_similarity(source, close, global_average=6.0)
        distant_score, _ = calculate_content_similarity(source, distant, global_average=6.0)

        self.assertGreater(close_score, distant_score)

    def test_bayesian_rating_is_included_when_rating_exists(self):
        source = Movie(title="source", genres=["Drama"])
        candidate = Movie(
            title="candidate",
            genres=["Drama"],
            vote_average=8.0,
            vote_count=CONTENT_MINIMUM_VOTES,
        )

        _, components = calculate_content_similarity(source, candidate, global_average=6.0)

        self.assertAlmostEqual(
            components["rating"],
            bayesian_rating(candidate, 6.0, minimum_votes=100) / 10.0,
        )

    def test_low_vote_movie_gets_no_rating_component(self):
        source = Movie(title="source", genres=["Drama"])
        candidate = Movie(
            title="candidate",
            genres=["Drama"],
            vote_average=9.0,
            vote_count=99,
        )

        _, components = calculate_content_similarity(source, candidate, global_average=6.0)

        self.assertNotIn("rating", components)

    def test_one_shared_genre_alone_is_not_a_candidate(self):
        source = Movie(title="source", genres=["SF", "Drama"])
        candidate = Movie(title="candidate", genres=["SF", "Comedy"], vote_count=100)

        qualifies, _ = qualifies_content_candidate(source, candidate)

        self.assertFalse(qualifies)

    def test_two_shared_genres_are_a_candidate_with_enough_votes(self):
        source = Movie(title="source", genres=["SF", "Drama"])
        candidate = Movie(
            title="candidate",
            genres=["SF", "Drama", "Action"],
            vote_count=CONTENT_MINIMUM_VOTES,
        )

        qualifies, _ = qualifies_content_candidate(source, candidate)

        self.assertTrue(qualifies)

    def test_shared_actor_allows_low_vote_exception(self):
        source = Movie(title="source", cast=["Actor A"])
        candidate = Movie(title="candidate", cast=["Actor A"], vote_count=3)

        qualifies, shared = qualifies_content_candidate(source, candidate)

        self.assertTrue(qualifies)
        self.assertTrue(shared["strong_relation"])


if __name__ == "__main__":
    unittest.main()
