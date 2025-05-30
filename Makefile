.PHONY: run run-dev run-prod run-prod-ssl clean

# Development server with auto-reload
run-dev:
	export FLASK_APP=app.py && export FLASK_ENV=development && flask run --debug

# Production server using gunicorn
run-prod:
	gunicorn \
		--workers 4 \
		--bind 127.0.0.1:5000 \
		--timeout 120 \
		--access-logfile - \
		--error-logfile - \
		--log-level info \
		--worker-class gthread \
		--threads 2 \
		app:app

# Production server with SSL (when you have SSL certificates)
run-prod-ssl:
	gunicorn \
		--workers 4 \
		--bind 127.0.0.1:5000 \
		--certfile cert.pem \
		--keyfile key.pem \
		--timeout 120 \
		--access-logfile - \
		--error-logfile - \
		--log-level info \
		--worker-class gthread \
		--threads 2 \
		app:app

# Default to development mode
run: run-dev

clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} +
	find . -type d -name "*.egg" -exec rm -r {} +
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name ".coverage" -exec rm -r {} +
	find . -type d -name "htmlcov" -exec rm -r {} +
	find . -type d -name ".mypy_cache" -exec rm -r {} +
	find . -type d -name ".ruff_cache" -exec rm -r {} + 