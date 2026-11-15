from app import create_app

app = create_app()

if __name__ == "__main__":
    app.logger.info("Starting AI Lip Sync Studio at http://127.0.0.1:5000")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False,
        threaded=True
    )