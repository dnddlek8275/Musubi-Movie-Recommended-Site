import asyncio
import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.api.admin import update_admin_role
from app.api.auth import register
from app.api.movies import get_actors
from app.api.users import get_ai_recommended_movies
from app.schemas.admin import AdminRoleUpdateRequest
from app.schemas.users import RegisterRequest


class FakeSession:
    def __init__(self):
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True

    def query(self, _model):
        return self

    def filter(self, *_conditions):
        return self

    def first(self):
        return None


class APIErrorResponseTests(unittest.TestCase):
    def test_unexpected_movie_error_returns_flat_500_without_internal_detail(self):
        with patch(
            "app.api.movies.get_actors_result",
            side_effect=RuntimeError("database password leaked"),
        ):
            response = get_actors(db=FakeSession())

        payload = json.loads(response.body)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(payload["state"], "error")
        self.assertNotIn("database password", response.body.decode())

    def test_empty_chat_recommendation_result_returns_failure(self):
        with patch(
            "app.api.users.get_chat_ai_recommended_movies_result",
            return_value=None,
        ):
            response = get_ai_recommended_movies(
                current_user={"user_id": 1},
                limit=10,
                db=FakeSession(),
            )

        self.assertEqual(response["state"], "failure")

    def test_admin_http_exception_is_not_converted_to_500(self):
        session = FakeSession()
        expected = HTTPException(
            status_code=409,
            detail={
                "state": "failure",
                "message": "이미 관리자 권한을 가진 사용자입니다.",
            },
        )

        with patch(
            "app.api.admin.get_admin_role_target",
            side_effect=expected,
        ):
            with self.assertRaises(HTTPException) as raised:
                update_admin_role(
                    request=AdminRoleUpdateRequest(
                        email="admin@example.com",
                        is_admin=True,
                    ),
                    current_admin=object(),
                    db=session,
                )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertTrue(session.rolled_back)

    def test_register_validation_error_returns_flat_400(self):
        session = FakeSession()
        request = RegisterRequest(
            email="user@example.com",
            password="Password1!",
            nickname="user",
            verification_code="123456",
        )

        with patch(
            "app.api.auth.validate_email_verification_code",
            side_effect=ValueError("인증번호가 만료 되었습니다."),
        ):
            response = asyncio.run(register(request=request, db=session))

        payload = json.loads(response.body)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["state"], "failure")
        self.assertTrue(session.rolled_back)


if __name__ == "__main__":
    unittest.main()
