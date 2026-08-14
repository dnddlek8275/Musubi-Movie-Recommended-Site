# 줄거리 짧게 보여주기
def shorten_text(text:str | None = None, max_length : int =80) :
    if not text : return text
    return text[:max_length].rstrip() + "..."