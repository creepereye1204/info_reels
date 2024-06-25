.PHONY: run-server
run-server:
	poetry run uvicorn info_reels_docker.apps.app.main:app --host 0.0.0.0 --port 8080 --reload

.PHONY: build
build:
	docker-compose build

.PHONY: up
up:
	docker-compose up

.PHONY: build-up
build-up: build up;