# Machine Learning & AI Portfolio

This repository holds the small hands-on projects I built on my own: two
end-to-end machine learning projects — from raw data to a cleaned dataset, to a
trained model, to measured results — an agentic-AI project that uses a large
language model as a strict, structured-data extractor, and a small browser game
built with the Phaser engine. Each project is intentionally end-to-end so the
whole pipeline is visible and reproducible.

## Tech stack

- **Python**
- **pandas** / **NumPy** — data loading, cleaning and feature engineering
- **scikit-learn** — models, cross-validation and metrics
- **seaborn** / **matplotlib** — exploratory data analysis and plots
- **Pydantic AI** / **Google Gemini** — the agentic-AI project: constraining an
  LLM to return strictly typed, validated data
- **Streamlit** / **Inngest** / **Qdrant** / **LlamaIndex** — the RAG project:
  ingesting PDFs, retrieving relevant passages and generating grounded answers

## Repository structure

```
My Projects/
├── requirements.txt
├── Machine Learning/
│   ├── Classification/                 # Project 1 — Titanic classification
│   │   ├── titanic.csv                # raw dataset
│   │   ├── data_cleaning.py           # EDA + cleaning  -> clean_data.csv
│   │   ├── clean_data.csv             # cleaned, encoded dataset
│   │   └── titanic_predictions.py     # trains & compares 3 models
│   └── Regression/                    # Project 2 — Housing price regression
│       ├── housing.csv                # raw dataset
│       ├── data_cleaning.py           # ETL + feature engineering -> clean_housing.csv
│       ├── clean_housing.csv          # cleaned, engineered dataset
│       └── housing_predictions.py     # trains & evaluates the model
├── Agentic AI/                        # Project 3 — Strict Web Scraper
│   ├── models.py                      # Pydantic models — the strict data contract
│   ├── scraper.py                     # fetch URL + clean HTML to text (no LLM)
│   ├── agents.py                      # the 2 Pydantic AI agents
│   ├── main.py                        # CLI orchestrator
│   ├── requirements.txt               # this project's own dependencies
│   └── README.md                      # full project documentation
├── phaser_game/                       # Project 4 — Phaser mini game
    ├── index.html                     # browser entry point
    ├── readme.md                      # project documentation
    ├── assets/                        # sprites, sounds, fonts and maps
    ├── libs/                          # Phaser engine library
    └── src/                           # scenes, entities and game logic
  └── RAG_project/                       # Project 5 — PDF question answering with RAG
    ├── data_loader.py                  # PDF extraction, chunking and embeddings
    ├── vector_db.py                    # Qdrant storage and similarity search
    ├── main.py                         # FastAPI and Inngest workflows
    ├── streamlip_app.py                # Streamlit upload and question interface
    ├── requirements.txt                # project dependencies
    └── readme.md                       # full project documentation
```

## Project 1 — Titanic Survival Classification

**Why I built it.** I wanted to practise a full classification workflow and,
more importantly, learn how to *compare* models fairly instead of just trusting
the first one I trained.

**What I did.** Starting from the raw `titanic.csv`, I ran an exploratory data
analysis (survival by sex, class, age and fare, plus a correlation heatmap) and
cleaned the data: dropped columns with too many missing values (`Cabin`, `Name`,
`Ticket`), filled missing ages with the median, dropped the rows with a missing
`Embarked`, and one-hot encoded the categorical columns. Then I compared three
scikit-learn classifiers — `DecisionTreeClassifier`, `RandomForestClassifier`
and `GradientBoostingClassifier`. To keep the comparison honest, I held out 20%
of the data as a test set the models never see during training, and evaluated
the other 80% with stratified 5-fold cross-validation, measuring both accuracy
and F1-score.

**Results.** Cross-validation on the training data:

| Model | CV accuracy | CV F1-score |
|---|---|---|
| DecisionTree | 0.7666 | 0.6994 |
| RandomForest | 0.8172 | 0.7584 |
| GradientBoosting | 0.8214 | 0.7543 |

`RandomForest` had the best cross-validation F1-score, so it was chosen as the
final model. On the hidden 20% test set it scored **0.8034 accuracy** and
**0.7368 F1-score** — close to its cross-validation numbers, which means the
model generalises well and is not just overfitting the training data.

## Project 2 — California Housing Price Prediction

**Why I built it.** After the classification project I wanted a regression
problem, and one where the *feature engineering* mattered as much as the model.

**What I did.** Starting from the raw `housing.csv`, I cleaned and reshaped the
data: removed the few `ISLAND` rows as outliers, one-hot encoded
`ocean_proximity`, and dropped rows whose price hit the dataset's artificial
cap. The interesting part was feature engineering — I used the Haversine formula
to compute each district's distance to five major California hubs (Los Angeles,
San Diego, San Jose, San Francisco and Fresno), and turned the raw totals into
more meaningful per-household ratios (rooms, bedrooms and population per
household). Finally I scaled the features with `StandardScaler` and trained a
`LinearRegression` model, evaluated with 5-fold cross-validation.

**Results.** The model reached a **mean cross-validation R² of 0.6043**, meaning
it explains roughly 60% of the variance in median house value. That is a
reasonable result for a plain linear model and gives a solid baseline to improve
on later with non-linear models.

## Project 3 — Strict Web Scraper & Entity Extractor (Agentic AI)

**Why I built it.** Most LLM-based scrapers are unreliable because the model
replies with free-form prose. I wanted to learn how to *constrain* an LLM so it
returns reliable, programmatic data — the kind of thing that is actually usable
in automation, not just a chatbot answer.

**What I did.** I built a command-line tool that takes a job-posting URL and
returns strictly structured, validated JSON. It uses **Pydantic AI**: the
expected data shape is a Pydantic model passed as the agent's `output_type`, so
every reply is validated against that schema and retried if it does not fit.
The application is genuinely *agentic* — it runs **two LLM agents** in a
pipeline: an Extraction Agent pulls the raw fields out of the page, and a
Validation Agent then normalizes the skills, sanity-checks the salary, flags
missing fields and assigns a confidence score. A plain-Python step in front
fetches the page and strips it to clean text so the agents never see raw HTML.

**Result.** Given a public job posting (Greenhouse, Lever, LinkedIn job-view
pages, most company career pages), the tool reliably returns a typed object with
the job title, company, location, employment type, required skills, salary range
and a summary. When a field is genuinely absent it stays `null` rather than being
hallucinated — that honesty is the whole point of the strict approach.

Full setup and usage are in the project's own
[README](My%20Projects/Agentic%20AI/README.md).

## Project 4 — Little Things: Phaser Edition

**Why I built it.** After the data-heavy projects, I wanted something more
visual and interactive — a small browser game to practise scene management,
physics, level flow, and game object composition.

**What I did.** I built a compact pixel-art platformer in Phaser with a main
menu, multiple level scenes, tilemap-based level loading, custom entities for
buttons, blocks, doors, stairs, spikes, keys and NPC interactions, and a HUD that
runs alongside the gameplay scene.

**Result.** The project works as a playable mini-game prototype with a clear
scene structure, reusable assets, and a simple progression loop. It is a good
example of how a small Phaser game can be organised cleanly and expanded later.

## Project 5 — PDF Question Answering with RAG

**Why I built it.** I wanted to build a complete Retrieval-Augmented Generation
pipeline that can answer questions from a user's own documents instead of
relying only on a model's general knowledge.

**What I did.** The application accepts PDF uploads through Streamlit, extracts
and splits their text with LlamaIndex, embeds the chunks with Gemini, and stores
them in a local Qdrant collection. Inngest coordinates the ingestion and query
workflows. When a user asks a question, the application retrieves the most
relevant chunks and sends only that context to Gemini to generate the answer.
The UI also displays the source filenames used for the response.

**Result.** The project is a working local document-question-answering,
with separate ingestion and query workflows, deterministic chunk IDs,
vector similarity search, and a simple Streamlit interface.

Full setup and usage are in the project's own
[README](My%20Projects/RAG_project/readme.md).

## How to run

```bash
# 1. Clone the repository
git clone https://github.com/Nikiforov11/Nikiforov11.git
cd Nikiforov11

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 3. Install the dependencies
pip install -r "My Projects/requirements.txt"

# 4. Run a project (scripts read their CSVs by relative path,
#    so run them from inside the project folder)
cd "My Projects/Machine Learning/Classification"
python data_cleaning.py          # regenerates clean_data.csv
python titanic_predictions.py    # trains and compares the models
```

The Housing project runs the same way from its own
`My Projects/Machine Learning/Regression` folder.

The Agentic AI project has its **own** `requirements.txt` and needs a free
Google Gemini API key:

```bash
cd "My Projects/Agentic AI/strict_web_scraper"
pip install -r requirements.txt
copy .env.example .env        # then edit .env and add your GEMINI_API_KEY
python main.py "<job-posting-url>"
```

See its [README](My%20Projects/Agentic%20AI/README.md) for
the full details.

The RAG project has its own dependencies and also requires a local Qdrant
instance, a local Inngest development server, and a Gemini API key. See its
[README](My%20Projects/RAG_project/readme.md) for the startup commands.

## Contact

- Telegram: [@Nikifor9v](https://t.me/Nikifor9v)
- LinkedIn: [Nichifor Ioan Tudor](https://www.linkedin.com/in/nikifor-ioan-tudor)
