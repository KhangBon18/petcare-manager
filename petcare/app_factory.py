"""Compose the Flask application and register its route blueprints."""

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from petcare.app_configuration import validate_app_configuration
from petcare.app_hooks import (
    register_error_handlers,
    register_request_hooks,
    register_template_helpers,
)
from petcare.config import Config

csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__package__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    validate_app_configuration(app)
    register_request_hooks(app, csrf)

    from petcare.routes.auth_routes import bp as auth_bp
    from petcare.routes.assistant_routes import bp as assistant_bp
    from petcare.routes.audit_routes import bp as audit_bp
    from petcare.routes.account_routes import bp as account_bp
    from petcare.routes.customer_routes import bp as customer_bp
    from petcare.routes.invoice_routes import bp as invoice_bp
    from petcare.routes.health_routes import bp as health_bp
    from petcare.routes.main_routes import bp as main_bp
    from petcare.routes.metrics_routes import bp as metrics_bp
    from petcare.routes.pet_routes import bp as pet_bp
    from petcare.routes.product_routes import bp as product_bp
    from petcare.routes.purchasing_routes import bp as purchasing_bp
    from petcare.routes.report_routes import bp as report_bp
    from petcare.routes.store_routes import bp as store_bp
    from petcare.routes.user_routes import bp as user_bp

    for blueprint in (
        health_bp, metrics_bp, auth_bp, assistant_bp, main_bp, customer_bp, pet_bp, product_bp,
        invoice_bp, purchasing_bp, report_bp, user_bp, audit_bp, account_bp, store_bp,
    ):
        app.register_blueprint(blueprint)

    register_error_handlers(app)
    register_template_helpers(app)
    return app
