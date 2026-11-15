import logging
from logging.handlers import RotatingFileHandler
from time import perf_counter

from flask import Flask, request, g

from config import Config


def configure_logging(app):
    log_file = app.config["LOG_FOLDER"] / "application.log"

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    app.logger.handlers.clear()
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    for directory in [
        app.config["UPLOAD_FOLDER"],
        app.config["OUTPUT_FOLDER"],
        app.config["LOG_FOLDER"],
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    configure_logging(app)

    @app.before_request
    def log_request():
        g.request_start = perf_counter()
        app.logger.info(
            "REQUEST | %s %s",
            request.method,
            request.path
        )

    @app.after_request
    def log_response(response):
        duration = perf_counter() - g.get("request_start", perf_counter())

        app.logger.info(
            "RESPONSE | %s %s | Status: %s | Duration: %.3fs",
            request.method,
            request.path,
            response.status_code,
            duration
        )
        return response

    from app.routes.main import main_bp
    from app.routes.generation import generation_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(generation_bp)

    app.logger.info("AI Lip Sync Studio initialized.")

    return app