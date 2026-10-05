# AI Analyst

AI Analyst lets you upload a sales CSV, ask questions in plain language, and
receive answers, charts, and the calculations behind them. Google Gemini
interprets the question and chooses analysis tools; pandas computes the results
from your data.

The application uses Streamlit for the interface, SQLite and Parquet for local
storage, and can run questions either directly in the app or through an
Inngest-managed worker workflow.

## How it works

```text
CSV upload
    |
    v
Streamlit reads, cleans, profiles, and saves the dataset
    |
    v
Question + dataset profile + conversation history
    |
    +--> Direct mode: agent loop runs in the Streamlit process
    |
    +--> Inngest mode: app submits a job to the worker
              |
              +--> Gemini selects one of the analysis tools
              +--> pandas computes the result from the dataset
              +--> Gemini uses the result to answer or request another tool
    |
    v
Answer, chart, and calculation details in the Streamlit UI
```

The model receives a dataset profile, not the full dataset. Analysis tools
compute all figures with pandas, and the model is instructed to use those
results rather than inventing numbers.

## Project structure

| File or folder | Purpose |
|---|---|
| `app/streamlit_app.py` | Streamlit interface for uploads, questions, charts, and conversation history |
| `app/runner.py` | Selects and coordinates the direct or Inngest runner |
| `worker/` | FastAPI app and durable Inngest question/model-generation functions |
| `core/agent.py` | Agent loop, tool selection, and response assembly |
| `core/llm.py` | Provider-neutral LLM interface and Google Gemini client |
| `core/declarations.py` | Builds Gemini tool declarations from Pydantic schemas |
| `core/prompts.py` | System prompt and dataset context |
| `data_layer/` | CSV loading, profiling, ingestion, and SQLite/Parquet storage |
| `tools/` | Filters, pandas analysis, chart preparation, and tool registry |
| `evals/` | Example questions, scoring, and evaluation runner |
| `scripts/` | Sample-data generator and Inngest end-to-end check |
| `tests/` | Unit and integration tests; the LLM is faked or mocked |
| `docker-compose.yml` | App, worker, and Inngest development server |
| `Dockerfile` | Shared image used by the app and worker |

## Requirements

- Python 3.11 or newer for running locally
- Docker Desktop with Docker Compose for the containerized setup
- A Google Gemini API key for real model responses
- Node.js and npm only if running the Inngest development server without Docker

Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).
Check which model and request quota are enabled for the key; set `GEMINI_MODEL`
and `GEMINI_RPM` to match if needed.

## Setup

Run commands from this project directory:

```powershell
cd "My Projects\ai_analyst"
```

Create a `.env` file in this folder and add your key:

```dotenv
GEMINI_API_KEY=your_gemini_api_key
```

The `.env` file is optional for starting the Docker services, but a valid
`GEMINI_API_KEY` is required to ask questions. Do not commit the key.

## Run with Docker

From the project directory, build and start the complete stack:

```powershell
docker compose up --build
```

Open:

- Streamlit app: <http://localhost:8501>
- Inngest dashboard: <http://localhost:8288>

The Compose stack includes the Streamlit app, the FastAPI worker, and the
Inngest development server. The app and worker share the `analyst-data` Docker
volume, which keeps the SQLite database and uploaded datasets available across
container restarts. Stop the services with `Ctrl+C`, or in another terminal run:

```powershell
docker compose down
```

To also remove the stored dataset volume, use `docker compose down --volumes`.
This deletes the application's persisted local data.

In the app, choose **Use sample data** or upload a sales CSV, then ask a
question. The Inngest dashboard's **Runs** view shows question runs, their
steps, inputs, outputs, and retries.

## Run locally without Docker

Create and activate a virtual environment, then install dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For direct mode, run:

```powershell
streamlit run app/streamlit_app.py
```

Questions run in the Streamlit process; no worker or Inngest server is needed.

To use the full Inngest workflow locally, start these three processes in
separate terminals from the project directory:

```powershell
uvicorn worker.main:app --port 8000
```

```powershell
npx --yes inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest --no-discovery
```

```powershell
$env:ANALYST_MODE = "inngest"
streamlit run app/streamlit_app.py
```

The Inngest development server requires Node.js. In this mode the worker and
Inngest server must be running before submitting questions from the app.

## Ask questions in other ways

Generate the built-in sample CSV and start a terminal chat:

```powershell
python scripts\make_sample_data.py
python cli.py data\sample_sales.csv
```

Ask a single question and open a generated chart when available:

```powershell
python cli.py data\sample_sales.csv -q "Top 5 customers in 2024?" --open
```

Run the unit tests or the model-backed evaluation suite:

```powershell
pytest
python -m evals.run
```

The tests do not require an API key. The evaluation suite calls Gemini and uses
API quota. To run selected cases or only feedback submitted in the app:

```powershell
python -m evals.run --only yoy_growth follow_up
python -m evals.run --feedback
```

Evaluation reports are saved under `data/evals/`; CLI run traces are saved
under `data/runs/`.

## Analysis workflow

1. **Load and profile.** The CSV loader detects separators, encodings, number
   formats, dates, and text columns while preserving values such as zip codes.
   The profiler identifies column types and likely roles such as date, revenue,
   or region. Column roles can be corrected in the app.
2. **Build context.** Gemini receives the profile and selected conversation
   history rather than the full dataset.
3. **Select tools.** The agent can call tools for column statistics,
   aggregation, time series, period comparisons, distinct values, and charts.
4. **Compute with pandas.** Tools validate arguments and compute results from
   the stored data. Readable tool errors let the model correct invalid
   arguments.
5. **Respond.** Gemini explains the computed results. For charts, application
   code computes the chart data and Plotly renders it.

The same agent loop is used by the CLI, tests, direct mode, and the Inngest
worker. In Inngest mode, model calls and tool calls are durable steps. This
makes progress visible in the dashboard and allows failed steps to be retried
without repeating completed work.

## Configuration

Set optional values in the project's `.env` file or environment:

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | unset | Google AI Studio API key |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Gemini model name |
| `GEMINI_RPM` | `10` | Maximum model requests per minute |
| `LLM_MAX_RETRIES` | `3` | Retries for retryable Gemini API errors |
| `ANALYST_MODE` | `direct` | `direct` or `inngest` execution mode |
| `MAX_AGENT_STEPS` | `6` | Maximum model calls per question |
| `HISTORY_TURNS` | `6` | Number of previous question/answer pairs retained |
| `DATE_DAYFIRST` | `false` | Interpret ambiguous dates day-first when set to `true` |
| `DATA_DIR` | `./data` | Local datasets, database, run traces, and evaluation reports |

Docker Compose sets `ANALYST_MODE=inngest` and `DATA_DIR=/data` for the
containers. The app and worker share that directory through the `analyst-data`
volume.

## Evals and debugging

`evals/cases.py` contains questions about the generated sample data, including
totals, year-over-year growth, a multilingual question, a misspelled filter, a
follow-up, a chart request, and a question the data cannot answer. Expected
values are computed with pandas.

To investigate an answer:

1. Expand **How this was calculated** below the response to inspect tool calls,
   arguments, and errors.
2. In Inngest mode, inspect the run and its steps in the dashboard.
3. In CLI mode, inspect the saved trace in `data/runs/`.

If an answer is wrong, check the column roles, the rules in `core/prompts.py`,
and the tool descriptions in `tools/registry.py`; then run the evaluation
suite.

## Limitations

- The application is designed for local analysis and does not include
  authentication or multi-user access controls.
- Gemini responses require internet access and are subject to the model's
  availability and the API key's quota.
- Data stays in local application storage; Docker deployments persist it in a
  local named volume, not a managed database or object store.
- Answers depend on CSV parsing, inferred column roles, tool selection, and
  model interpretation. The calculation details and evaluation suite help
  verify results.

## Tech stack

- Python, pandas, Pydantic
- Streamlit and Plotly
- Google Gemini via the `google-genai` SDK
- FastAPI and Inngest
- SQLite and Parquet
- pytest
