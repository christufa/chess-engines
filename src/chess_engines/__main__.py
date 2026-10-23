"""Run the API: `chess-engines` (or `python -m chess_engines`)."""

import logging
import os

import uvicorn


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run(
        "chess_engines.app:create_app", factory=True,
        host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8000")),
        proxy_headers=False, access_log=os.environ.get("ACCESS_LOG", "1") == "1",
    )


if __name__ == "__main__":
    main()
