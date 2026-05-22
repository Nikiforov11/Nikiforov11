# Machine Learning Portfolio

This repository holds a couple of small machine learning
projects I built on my own to get hands-on exposure to a complete ML workflow —
from raw data to a cleaned dataset, to a trained model, to measured results.
Each project is intentionally end-to-end: there is a data-cleaning stage and a
modelling stage, so the whole pipeline is visible and reproducible.

## Tech stack

- **Python**
- **pandas** / **NumPy** — data loading, cleaning and feature engineering
- **scikit-learn** — models, cross-validation and metrics
- **seaborn** / **matplotlib** — exploratory data analysis and plots

## Repository structure

```
My Projects/
├── requirements.txt
└── Machine Learning/
    ├── Classification/                 # Project 1 — Titanic classification
    │   ├── titanic.csv                # raw dataset
    │   ├── data_cleaning.py           # EDA + cleaning  -> clean_data.csv
    │   ├── clean_data.csv             # cleaned, encoded dataset
    │   └── titanic_predictions.py     # trains & compares 3 models
    └── Regression/              # Project 2 — Housing price regression
        ├── housing.csv                # raw dataset
        ├── data_cleaning.py           # ETL + feature engineering -> clean_housing.csv
        ├── clean_housing.csv          # cleaned, engineered dataset
        └── housing_predictions.py     # trains & evaluates the model
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

## Contact

- Telegram: [@Nikifor9v](https://t.me/Nikifor9v)
