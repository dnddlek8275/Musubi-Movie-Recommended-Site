import unittest

from pipeline.retrieval_policy import choose_rerank_mode


class RetrievalPolicyTests(unittest.TestCase):
    def test_verified_metadata_filter_skips_cross_encoder(self):
        self.assertEqual(
            choose_rerank_mode(
                has_metadata_filter=True,
                quality_priority=None,
                has_topic=False,
                has_personalization=False,
            ),
            "skip",
        )

    def test_mood_query_uses_complex_rerank_even_with_genre(self):
        self.assertEqual(
            choose_rerank_mode(
                has_metadata_filter=True,
                quality_priority="mood",
                has_topic=False,
                has_personalization=False,
            ),
            "complex",
        )

    def test_topic_and_personalization_use_complex_rerank(self):
        for has_topic, has_personalization in ((True, False), (False, True)):
            with self.subTest(topic=has_topic, personalization=has_personalization):
                self.assertEqual(
                    choose_rerank_mode(
                        has_metadata_filter=False,
                        quality_priority=None,
                        has_topic=has_topic,
                        has_personalization=has_personalization,
                    ),
                    "complex",
                )

    def test_unclassified_free_form_query_keeps_standard_rerank(self):
        self.assertEqual(
            choose_rerank_mode(
                has_metadata_filter=False,
                quality_priority=None,
                has_topic=False,
                has_personalization=False,
            ),
            "standard",
        )


if __name__ == "__main__":
    unittest.main()
