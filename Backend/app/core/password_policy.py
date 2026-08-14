MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128


def validate_password_policy(password: str) -> str:
    """회원가입과 비밀번호 재설정에서 공유하는 비밀번호 보안 정책."""
    if len(password) < MIN_PASSWORD_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError("비밀번호는 10~128자로 입력해 주세요.")
    if not any(character.isalpha() and character.isascii() for character in password):
        raise ValueError("비밀번호에 영문을 포함해 주세요.")
    if not any(character.isdigit() for character in password):
        raise ValueError("비밀번호에 숫자를 포함해 주세요.")
    if not any(not character.isalnum() and not character.isspace() for character in password):
        raise ValueError("비밀번호에 특수문자를 포함해 주세요.")
    if any(character.isspace() for character in password):
        raise ValueError("비밀번호에는 공백을 사용할 수 없습니다.")
    return password
