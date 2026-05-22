import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# Importing the dataset into a dataframe
raw_data = pd.read_csv('titanic.csv',index_col='PassengerId')

#NOTE EDA (Exploratory, data, analysis)
print("Shape of the Dataset:", raw_data.shape, "\n")
print("First Few Rows of the Dataset:")
print(raw_data.head(10), "\n\n")
print("Dataset Information:")
print(raw_data.info(), "\n\n")
print("Number of Missing Values in Each Column:")
print(raw_data.isna().sum(), "\n\n")
print("Number of Duplicated Rows:\n", raw_data.duplicated().sum(), "\n\n")
print("Description of the Numerical Dataset:\n", raw_data.describe(), "\n\n")
print("Number of Unique Values in Each Column:\n", raw_data.nunique(), "\n\n")

# Style of the plots
sns.set_theme(style='darkgrid',palette='muted')
PALETTE = ["#E74C3C","#2ECC71"]

BG_COLOR = '#1C1C2E'
AX_COLOR = "#2A2A3E"
TXT = "#FFFFFF"

plt.rcParams.update({
    "figure.facecolor":  BG_COLOR,
    "axes.facecolor":    AX_COLOR,
    "axes.edgecolor":    "#444",
    "axes.labelcolor":   TXT,
    "xtick.color":       TXT,
    "ytick.color":       TXT,
    "text.color":        TXT,
    "grid.color":        "#333",
    "grid.linewidth":    0.5,
})

# Canvas
fig = plt.figure(figsize=(16, 10), facecolor=BG_COLOR)
fig.suptitle("Titanic — Exploratory Data Analysis",
             fontsize=22, fontweight="bold", color=TXT, y=0.98)
 
gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)
 
axes = [fig.add_subplot(gs[r, c]) for r in range(2) for c in range(3)]

# Overall Survial
ax = axes[0]
counts = raw_data["Survived"].value_counts()
bars = ax.bar(["Died", "Survived"], counts.values, color=PALETTE, width=0.5, edgecolor="#111")
for bar, val in zip(bars, counts.values):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 3,
            str(val), ha="center", va="bottom", fontweight="bold", color=TXT)
ax.set_title("Overall Survival", fontweight="bold")
ax.set_ylabel("Passengers")
ax.set_ylim(0, counts.max() * 1.15)

# Survival by Sex
ax = axes[1]
sns.countplot(data=raw_data, x='Sex', hue='Survived',palette=PALETTE, edgecolor='#111', ax=ax)
ax.set_title('Survived by Sex', fontweight='bold')
ax.set_xlabel('Sex')
ax.set_ylabel('Count')
handles, _ = ax.get_legend_handles_labels()
ax.legend(handles,['Dies','Survived'],title='',framealpha=0.2)


#Survival by Passenger Class
ax = axes[2]
sns.countplot(data=raw_data, x="Pclass", hue="Survived",
              palette=PALETTE, edgecolor="#111", ax=ax)
ax.set_title("Survival by Class", fontweight="bold")
ax.set_xlabel("Passenger Class")
ax.set_ylabel("Count")
handles, _ = ax.get_legend_handles_labels()
ax.legend(handles, ["Died", "Survived"], title="", framealpha=0.2)
 
 
#Age Distribution by Survival
ax = axes[3]
for Survived, label, color in zip([0, 1], ["Died", "Survived"], PALETTE):
    subset = raw_data[raw_data["Survived"] == Survived]["Age"].dropna()
    ax.hist(subset, bins=25, alpha=0.65, color=color, label=label, edgecolor="#111")
ax.axvline(raw_data["Age"].median(), color="white", linestyle="--", linewidth=1,
           label=f"Median Age: {raw_data['Age'].median():.0f}")
ax.set_title("Age Distribution by Survival", fontweight="bold")
ax.set_xlabel("Age")
ax.set_ylabel("Count")
ax.legend(framealpha=0.2)
 
 
#Fare Distribution by Class  
ax = axes[4]
class_palette = ["#3498DB", "#9B59B6", "#F39C12"]
for Pclass, color in zip([1, 2, 3], class_palette):
    subset = raw_data[raw_data["Pclass"] == Pclass]["Fare"].dropna()
    ax.hist(subset, bins=30, alpha=0.65, color=color,
            label=f"Class {Pclass}", edgecolor="#111")
ax.set_title("Fare Distribution by Class", fontweight="bold")
ax.set_xlabel("Fare (£)")
ax.set_ylabel("Count")
ax.set_xlim(0, 300)
ax.legend(framealpha=0.2)
 
 
#Correlation Heatmap 
ax = axes[5]
num_cols = ["Survived", "Pclass", "Age", "SibSp", "Parch", "Fare"]
corr = raw_data[num_cols].corr()
mask_arr = np.zeros(corr.shape, dtype=bool)
mask = pd.DataFrame(mask_arr, index=corr.index, columns=corr.columns)
 
sns.heatmap(corr, ax=ax, annot=True, fmt=".2f", cmap="coolwarm",
            center=0, linewidths=0.5, linecolor="#111",
            cbar_kws={"shrink": 0.8}, annot_kws={"size": 8})
ax.set_title("Feature Correlation", fontweight="bold")
ax.tick_params(axis="x", rotation=30)

plt.show()


#NOTE Data Cleaning
#Dropping the coulmns that have to many nulls or are not necessary
process_data = raw_data.drop('Cabin',axis=1)
process_data = process_data.drop('Name', axis=1)
process_data = process_data.drop('Ticket', axis=1)

#Filling the age with median age
median_age = process_data['Age'].median()
process_data['Age'] = process_data['Age'].fillna(median_age)

#Getting rid of the two rows where the Embarked is null
process_data = process_data.dropna(subset=['Embarked'])

#One-hot enconding the embarked, Pclass and sex
process_data = process_data.copy()

gender_columns = pd.get_dummies(process_data['Sex'], prefix='Sex')
embarked_columns = pd.get_dummies(process_data['Embarked'],prefix='Embarked')
pclass_columns = pd.get_dummies(process_data['Pclass'],prefix='Pclass')
# Concatenate
process_data = pd.concat([process_data,gender_columns],axis=1)
process_data = pd.concat([process_data,embarked_columns],axis=1)
process_data = pd.concat([process_data,pclass_columns],axis=1)

#Dropping the original categorical columns
process_data = process_data.drop(['Sex','Embarked','Pclass'],axis=1)

#Saving the cleaned Data to a new csv
process_data.to_csv('./clean_data.csv', index=None)