web: gunicorn --workers 1 --threads 4 --timeout 90 --bind 0.0.0.0:$PORT src.app:app
release: python -m src.scraper && python -m src.extractor
