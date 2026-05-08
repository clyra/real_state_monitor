from __future__ import annotations

import os
import re
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask import Flask

load_dotenv()

# Set Flask's built-in env vars from our config
os.environ.setdefault("FLASK_RUN_HOST", os.environ.get("WEB_HOST", "0.0.0.0"))
os.environ.setdefault("FLASK_RUN_PORT", os.environ.get("WEB_PORT", "5000"))
os.environ.setdefault("FLASK_DEBUG", os.environ.get("WEB_DEBUG", "1"))


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    )
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-prod")

    def maps_url(address: str | None) -> str | None:
        if not address or not re.search(r"\d", address):
            return None
        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(address)}"

    app.jinja_env.filters["maps_url"] = maps_url

    from real_estate_monitor.web.routes import register_routes

    register_routes(app)

    return app


def main():
    host = os.environ.get("WEB_HOST", "0.0.0.0")
    port = int(os.environ.get("WEB_PORT", "5000"))
    debug = os.environ.get("WEB_DEBUG", "true").lower() == "true"

    app = create_app()
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
