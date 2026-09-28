import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

data = pd.read_csv('data_clean.csv', parse_dates=['event_timestamp'])

#Sensor Columns
sensor_cols = ['reaction_temperature_celsius', 'vessel_pressure_bar', 'refractive_index',
               'density_g_cm3', 'ph_level', 'mixing_torque_nm', 'mass_flow_rate_kg_h']
#Categorical Columns
cat_cols = ['plant_country', 'production_line_id']

#Flag from EDA
data['low_torque'] = (data['mixing_torque_nm'] < 11.4).astype(int)

X = data[sensor_cols + ['low_torque'] + cat_cols]
y = data['stability_months']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f'Train: {len(X_train)} Test: {len(X_test)}')

#Adressing the missing numerical values, filling with the median of the training set
medians = X_train[sensor_cols].median()
X_train = X_train.fillna(medians)
X_test = X_test.fillna(medians)

#Adressing the categorical missing values.
X_train = pd.get_dummies(X_train, columns=cat_cols)
X_test = pd.get_dummies(X_test, columns=cat_cols)
X_test = X_test.reindex(columns=X_train.columns, fill_value=0)

#Models
models = {
    'Linear Regression': LinearRegression(),
    'Random Forest': RandomForestRegressor(n_estimators=100, max_depth=12, n_jobs=-1, random_state=42),
    'Gradient Boosting': GradientBoostingRegressor(n_estimators=200, random_state=42),
}

results = []
predictions = {}

for name, model in models.items():
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    predictions[name] = pred
    
    results.append({
        'Model': name,
        'MAE': mean_absolute_error(y_test, pred),
        'RMSE': np.sqrt(mean_squared_error(y_test, pred)),
        'R2': r2_score(y_test, pred),
        'Within ±1 month %': np.mean(np.abs(y_test - pred) <= 1) * 100,
    })
    print(f'{name} Done!')
    
results = pd.DataFrame(results).round(3)
print('\nModel Comparison on the test set:')
print(results.to_string(index=False))

#Best Model
best_name = results.sort_values('MAE').iloc[0]['Model']
best_model = models[best_name]
best_pred = predictions[best_name]
print(f'\nBest model: {best_name}')

#Cheking the Feature importance
importance = pd.Series(best_model.feature_importances_, index=X_train.columns).sort_values()

#Cheking the ph and pressure effect
for col in ['ph_level', 'vessel_pressure_bar']:
    bins = pd.cut(data[col], 10)
    print(f'\nMean stability by {col} bin:')
    print(data.groupby(bins, observed=True)['stability_months'].mean().round(3))
    

plt.figure(figsize=(8, 6))
importance.plot(kind='barh')
plt.title(f'Feature importance ({best_name})')
plt.tight_layout()
plt.show()

#Predicted vs Real
plt.figure(figsize=(6, 6))
plt.scatter(y_test, best_pred, alpha=0.1, s=5)
plt.plot([18, 30], [18, 30], 'r--')
plt.xlabel('Actual Stability (months)')
plt.ylabel('Predicted stability (months)')
plt.title(f'Predicted vs actual ({best_name})')
plt.tight_layout()
plt.show()

#Confidence
errors = np.abs(y_test - best_pred)
print(f'\n80% of the predictions are within -+{np.percentile(errors, 80):.2f} months of the real value')
print(f'95% of the predictions are within -+{np.percentile(errors, 95):.2f} months of the real value')