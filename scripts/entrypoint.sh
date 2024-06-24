set -e
exec poetry run uvicorn info_reels.apps.app.main:app --host 0.0.0.0 --port 8080 --reload

