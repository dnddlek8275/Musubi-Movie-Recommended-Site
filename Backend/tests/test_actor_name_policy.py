import unittest
from types import SimpleNamespace

from app.services.actor_name_policy import (
    actor_display_name,
    infer_is_korean,
    resolved_actor_name,
    select_korean_name,
)


class ActorNamePolicyTests(unittest.TestCase):
    def test_verified_actor_id_uses_manual_display_name(self):
        actor = SimpleNamespace(
            id=10199,
            name="Noh Young-hak",
            original_name="Noh Young-hak",
            korean_name=None,
            is_korean=None,
        )
        self.assertEqual(actor_display_name(actor), "노영학")

    def test_korean_alias_is_selected_for_korean_actor(self):
        self.assertEqual(
            select_korean_name("Noh Young-hak", ["노영학", "Noh Yeong Hak"]),
            "노영학",
        )

    def test_explicit_south_korean_birthplace_is_korean(self):
        self.assertIs(
            infer_is_korean(
                place_of_birth="Seoul, South Korea",
                korean_name="노영학",
                korean_credit_count=3,
                total_credit_count=3,
            ),
            True,
        )

    def test_explicit_foreign_birthplace_is_not_korean(self):
        self.assertIs(
            infer_is_korean(
                place_of_birth="Baltimore, Maryland, USA",
                korean_name="  ",
                korean_credit_count=0,
                total_credit_count=12,
            ),
            False,
        )

    def test_unknown_birthplace_needs_strong_korean_credit_evidence(self):
        self.assertIs(
            infer_is_korean(
                place_of_birth=None,
                korean_name="한재영",
                korean_credit_count=7,
                total_credit_count=7,
            ),
            True,
        )
        self.assertIsNone(
            infer_is_korean(
                place_of_birth=None,
                korean_name="한재영",
                korean_credit_count=1,
                total_credit_count=1,
            )
        )

    def test_foreign_actor_uses_original_name(self):
        self.assertEqual(
            resolved_actor_name(
                current_name="레오나르도 디카프리오",
                original_name="Leonardo DiCaprio",
                korean_name="레오나르도 디카프리오",
                is_korean=False,
            ),
            "Leonardo DiCaprio",
        )

    def test_korean_actor_uses_korean_name(self):
        self.assertEqual(
            resolved_actor_name(
                current_name="Noh Young-hak",
                original_name="Noh Young-hak",
                korean_name="노영학",
                is_korean=True,
            ),
            "노영학",
        )

    def test_short_stage_name_is_preserved(self):
        self.assertEqual(
            resolved_actor_name(
                current_name="RM",
                original_name="RM",
                korean_name="래퍼",
                is_korean=True,
            ),
            "RM",
        )


if __name__ == "__main__":
    unittest.main()
