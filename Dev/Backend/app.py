from flask import Flask, jsonify


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/api/health")
    def health_check():
        return jsonify(status="healthy", service="backend"), 200

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
