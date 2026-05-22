import pandas as pd

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate
from sklearn.metrics import f1_score, accuracy_score
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

data = pd.read_csv('clean_data.csv')

features = data.drop(['Survived'], axis=1)

labels = data['Survived']

X_train, X_test, y_train, y_test = train_test_split(
    features, labels, test_size=0.2, stratify=labels, random_state=42
)

models = {
    'DecisionTree': DecisionTreeClassifier(random_state=42),
    'RandomForest': RandomForestClassifier(random_state=42),
    'GradientBoosting': GradientBoostingClassifier(random_state=42),
}

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

results = {}

for name, model in models.items():
    scores = cross_validate(model, X_train, y_train, cv=cv, scoring=['accuracy', 'f1'])
    mean_accuracy = scores['test_accuracy'].mean()
    mean_f1 = scores['test_f1'].mean()
    results[name] = {'accuracy': mean_accuracy, 'f1': mean_f1}
    print(f'{name}: CV accuracy = {mean_accuracy:.4f}, CV f1-score = {mean_f1:.4f}')

best_model_name = max(results, key=lambda name: results[name]['f1'])
print(f'\nBest model by cross-validation f1-score: {best_model_name}')

best_model = models[best_model_name]
best_model.fit(X_train, y_train)
predictions = best_model.predict(X_test)

test_accuracy = accuracy_score(y_test, predictions)
test_f1 = f1_score(y_test, predictions)

print(f'{best_model_name} on hidden test set: accuracy = {test_accuracy:.4f}, f1-score = {test_f1:.4f}')

