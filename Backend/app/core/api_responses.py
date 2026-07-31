from fastapi.responses import JSONResponse


def error_response(
    message: str,
    *,
    status_code: int = 500,
    state: str = "error",
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "state": state,
            "message": message,
        },
    )
