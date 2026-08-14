import unittest
from unittest.mock import Mock, patch

from app.services import object_storage_service


class ObjectStorageServiceTests(unittest.TestCase):
    def tearDown(self):
        object_storage_service.get_object_storage_client.cache_clear()

    def test_parse_object_uri(self):
        self.assertEqual(
            object_storage_service.parse_object_uri(
                "s3://profile-bucket/profiles/user/1/profile.jpg"
            ),
            ("profile-bucket", "profiles/user/1/profile.jpg"),
        )
        self.assertIsNone(
            object_storage_service.parse_object_uri("/uploads/profile.jpg")
        )

    def test_resolve_public_object_url(self):
        with patch.object(
            object_storage_service.settings,
            "OBJECT_STORAGE_PUBLIC_BASE_URL",
            "https://cdn.example.com/project:bucket",
        ):
            result = object_storage_service.resolve_object_url(
                "s3://profile-bucket/profiles/user/한글 사진.jpg"
            )

        self.assertEqual(
            result,
            "https://cdn.example.com/project:bucket/"
            "profiles/user/%ED%95%9C%EA%B8%80%20%EC%82%AC%EC%A7%84.jpg",
        )

    def test_resolve_private_object_url_uses_presigned_url(self):
        client = Mock()
        client.generate_presigned_url.return_value = "https://signed.example.com/object"
        with (
            patch.object(
                object_storage_service.settings,
                "OBJECT_STORAGE_PUBLIC_BASE_URL",
                "",
            ),
            patch.object(
                object_storage_service.settings,
                "OBJECT_STORAGE_PRESIGN_EXPIRES_SECONDS",
                3600,
            ),
            patch.object(
                object_storage_service,
                "get_object_storage_client",
                return_value=client,
            ),
        ):
            result = object_storage_service.resolve_object_url(
                "s3://profile-bucket/profiles/user/1/profile.jpg"
            )

        self.assertEqual(result, "https://signed.example.com/object")
        client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": "profile-bucket",
                "Key": "profiles/user/1/profile.jpg",
            },
            ExpiresIn=3600,
        )


if __name__ == "__main__":
    unittest.main()
