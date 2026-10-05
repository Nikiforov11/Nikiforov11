# Shortcuts. On Windows without make, copy the command after each target.
.PHONY: install sample test cli app worker inngest app-inngest e2e evals evals-fake up down

install:      ## install dependencies
	pip install -r requirements.txt

sample:       ## generate data/sample_sales.csv and data/sample_sales_eu.csv
	python scripts/make_sample_data.py

test:         ## run the test suite (no API key needed)
	pytest

cli: sample   ## chat in the terminal
	python cli.py data/sample_sales.csv

app:          ## Streamlit UI, questions run in-process
	streamlit run app/streamlit_app.py

worker:       ## Inngest worker on :8000
	uvicorn worker.main:app --port 8000 --reload

inngest:      ## Inngest Dev Server on :8288 (needs Node.js)
	npx --yes inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest --no-discovery

app-inngest:  ## Streamlit UI using the worker (run `make worker` and `make inngest` first)
	ANALYST_MODE=inngest streamlit run app/streamlit_app.py

e2e:          ## end-to-end check through a running Dev Server, fake LLM
	python scripts/e2e_inngest.py

evals:        ## eval suite against Gemini (uses quota)
	python -m evals.run

evals-fake:   ## eval harness smoke test, no API key
	python -m evals.run --fake

up:           ## full stack in Docker
	docker compose up --build

down:
	docker compose down
