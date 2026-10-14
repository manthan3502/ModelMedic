"""Provider-neutral production entrypoint (PORT supplied by the container host)."""

import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid web service port")
    uvicorn.run(
        "backend.app.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=port,
        access_log=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
