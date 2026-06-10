from flask import Flask
from wsgiref.simple_server import make_server

from database import init_db
from routes.dashboard import dashboard_bp
from routes.jobs import jobs_bp


def create_app():
    app = Flask(__name__)
    init_db()

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(jobs_bp, url_prefix="/api/jobs")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    host = "127.0.0.1"
    port = 5000
    app = create_app()

    print(f"Cron Monitor running at http://{host}:{port}")
    print("Press CTRL+C to stop")

    with make_server(host, port, app) as server:
        server.serve_forever()
