from app import create_app

app = create_app()

if __name__ == '__main__':
    # Dev server only (production uses gunicorn). debug=True reloads templates on save.
    app.run(host="0.0.0.0", port=3000, debug=True)

    
