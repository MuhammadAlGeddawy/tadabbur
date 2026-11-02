.PHONY: install data index check-models run test eval eval-full docker
PY ?= python3

install:            ## install the package and dev tools
	$(PY) -m pip install -e ".[dev]"

data:               ## download sources and build data/quran.json + data/qqa23.json
	bash scripts/fetch_sources.sh
	$(PY) -m tadabbur.build_data

index:              ## build the dense embedding index (needs OPENROUTER_API_KEY)
	$(PY) -m tadabbur.build_index

check-models:       ## confirm the model IDs in config/models.yaml exist on OpenRouter
	$(PY) -m tadabbur.check_models

run:                ## start the API and web app on http://localhost:8000
	$(PY) -m uvicorn tadabbur.api:app --host 0.0.0.0 --port 8000

test:
	$(PY) -m pytest -q

eval:               ## keyword-stage evaluation on Qur'an QA 2023 (no key needed)
	$(PY) -m tadabbur.evaluate --split all --mode keyword

eval-full:          ## full pipeline on the dev split (uses the LLM; replies are cached)
	$(PY) -m tadabbur.evaluate --split dev --mode full

docker:
	docker compose up --build
