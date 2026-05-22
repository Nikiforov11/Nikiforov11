import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler

data = pd.read_csv('clean_housing.csv')

# Separating Featrures (X) and Target (y)
X = data.drop(columns=['median_house_value'])
y = data['median_house_value']

# Initial 80/20 split where 80 for training and 20 for testing
# random_state ensures we get the exact same split every time we run the code
X_train, X_test, y_train, y_test = train_test_split(X,y, test_size=0.20, random_state=60)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Initialization of your model
model = LinearRegression()

# 5-Fold Cross-Validation on the Training Data
#cv=5 means 5 folds

cv_scores = cross_val_score(model,X_train_scaled,y_train, cv=5)

print("--- Cross-Validation Results ---")
print(f"Scores for each fold: {cv_scores}")
print(f"Average CV Score: {cv_scores.mean():.4f}")