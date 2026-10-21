"""Run the local PetCare Manager web application."""

from urllib.parse import urlparse

from petcare import create_app


app = create_app()


if __name__ == "__main__":
    lan_url = app.config.get("LAN_ACCESS_BASE_URL", "")
    parsed_url = urlparse(lan_url)
    valid_lan_url = bool(
        parsed_url.scheme in {"http", "https"}
        and parsed_url.netloc
        and not parsed_url.username
        and not parsed_url.password
    )
    lan_enabled = app.config.get("LAN_ACCESS_ENABLED", False) and valid_lan_url
    host = "0.0.0.0" if lan_enabled else "127.0.0.1"
    if app.config.get("LAN_ACCESS_ENABLED") and not valid_lan_url:
        app.logger.warning("LAN access needs a valid http(s) LAN_ACCESS_BASE_URL; binding to localhost.")
    app.run(
        host=host,
        port=app.config.get("APP_PORT", 5000),
        debug=app.config.get("DEBUG", False),
    )
