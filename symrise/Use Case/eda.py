import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

raw_data = pd.read_csv('data_set.csv')

# Structure Audit
print('Data Shape:')
print(raw_data.shape)
print('\n First 5 rows of the Data')
print(raw_data.head(10))
print('\n Data info:')
print(raw_data.info())
print('\n Description of the Data:')
print(raw_data.describe(include='all'))
print('\n Types of the Data:')
print(raw_data.dtypes)

batches_per_line = raw_data.groupby('production_line_id')['batch_id'].nunique()
print('\nBatch per line')
print(batches_per_line)
print(batches_per_line.sum())

# Checking if there are overlaping batches in lines
lines_per_batch = raw_data.groupby('batch_id')['production_line_id'].nunique()

multiple_lines = lines_per_batch[lines_per_batch > 1]

print(f"Number of batches in multiple lines: {len(multiple_lines)}")

if len(multiple_lines) > 0:
    print("\nBatch IDs and their production line counts:")
    print(multiple_lines)
    
    
#Checking for duplicates
print('\nDuplicated Rows:')
print(raw_data.duplicated().sum())
print('\nDuplicated Batches:')
print(raw_data['batch_id'].duplicated().sum())

#Cehcking the time to see if the format it DD/MM/YYYY
print('Time Check')
slash = raw_data[raw_data['event_timestamp'].str.match(r'\d{2}/\d{2}/\d{4}')]
parts = slash['event_timestamp'].str.split('/', expand=True).astype(int)
print(parts[0].max(), parts[1].max())  

#Formating the DateTime to a single format
raw_data['event_timestamp'] = pd.to_datetime(raw_data['event_timestamp'], format='mixed', dayfirst=True)

#Checking the data types, time, country location and lines
start_date = raw_data['event_timestamp'].min()
end_date = raw_data['event_timestamp'].max()

total_duration = end_date - start_date

print('\n Time Stamps')
print(f'First record: {start_date}')
print(f'Last record: {end_date}')
print(f'Total Duration: {total_duration}')

#Checking the names of the plant_country, plant_location and production_line_id
country = raw_data['plant_country'].unique()
location = raw_data['plant_location'].unique()
lines = raw_data['production_line_id'].unique()

print('\n Names of country, location and lines')
print(country, raw_data['plant_country'].nunique())
print(location, raw_data['plant_location'].nunique())
print(lines, raw_data['production_line_id'].nunique())

#Checking if the reactores are tied to all plants or do all plants use all reactors?
line_distribution = raw_data.groupby(['plant_country', 'plant_location'])['production_line_id'].unique().reset_index()
line_distribution.rename(columns={'production_line_id': 'assigned_lines'}, inplace=True)

pd.set_option('display.max_colwidth', None)
print(line_distribution)
pd.reset_option('display.max_colwidth')

print('\nBatches per plant and reactor:')
print(pd.crosstab(raw_data['production_line_id'], raw_data['plant_country']))


#Checking the missing Values, and temperature units
missing = raw_data.isna().sum()
missing_percentage = (raw_data.isna().mean() * 100).round(3)

print('\nMissing data per row:')
print(missing)
print('\nPercentage of missing Data:')
print(missing_percentage)

print('\nTemperature Units:')
print(raw_data['temp_unit'].value_counts(dropna=False))

f_rows = raw_data[raw_data['temp_unit'] == 'F']
print('\nFahrenheit rows - value range:')
print(f_rows['temp_value'].describe())
print('\nFahrenheit rows by plant:')
print(f_rows['plant_country'].value_counts())
print('\nfahrengeit rows by production line:')
print(f_rows['production_line_id'].value_counts())

#Converting the F to C, adding the new data to new column.
raw_data['reaction_temperature_celsius'] = raw_data['temp_value']
is_f = raw_data['temp_unit'] == 'F'
raw_data.loc[is_f, 'reaction_temperature_celsius'] = (raw_data.loc[is_f, 'temp_value'] - 32) * 5 / 9
print('\nTemperature after conversion:')
print(raw_data['reaction_temperature_celsius'].describe())

sensor_cols = [
    'reaction_temperature_celsius', 'temp_unit', 'vessel_pressure_bar', 'refractive_index', 
    'density_g_cm3', 'ph_level', 'mixing_torque_nm','mass_flow_rate_kg_h',
]
#By country
missing_by_country = raw_data.groupby('plant_country')[sensor_cols].apply(lambda x: x.isnull().mean() * 100)
print('\nMissing data Percentage by country:')
print(missing_by_country)

#By location
missing_by_location = raw_data.groupby('plant_location')[sensor_cols].apply(lambda x: x.isnull().mean() * 100)
print('\nMissing data Percentage by location:')
print(missing_by_location)

#By Production line
missing_by_line = raw_data.groupby('production_line_id')[sensor_cols].apply(lambda x: x.isnull().mean() * 100)
print('\nMissing data Percentage by productione line:')
print(missing_by_line)

#Out of range Data count
normal_ranges = {
    'reaction_temperature_celsius': (75, 100),
    'vessel_pressure_bar': (2, 3),
    'refractive_index': (1.43, 1.49),
    'density_g_cm3': (0.80, 0.90),
    'ph_level': (5.0, 6.0),
    'mixing_torque_nm': (9, 12.5),
    'mass_flow_rate_kg_h': (380, 520),
    'stability_months': (18, 30)
}
outlier_counts = {}

overall_outlier_mask = pd.Series(False, index=raw_data.index)

for col, (min_val, max_val) in normal_ranges.items():

    column_mask = raw_data[col].notnull() & ((raw_data[col] < min_val) | (raw_data[col] > max_val))
    
    outlier_counts[col] = column_mask.sum()
    
    overall_outlier_mask = overall_outlier_mask | column_mask

print("Number of out-of-range records per parameter:")
for col, count in outlier_counts.items():
    print(f"{col}: {count} outliers")

out_of_range_data = raw_data[overall_outlier_mask]

print(f"\nTotal rows with at least one out-of-range value: {len(out_of_range_data)}")

#Checking to see how many are below and above the normal range
cannot_be_negative = ['vesel_presure_bar', 'mixing_torque_nm', 'mass_flow_rate_kg_h']

outlier_details = []

for col, (min_val, max_val) in normal_ranges.items():
    negative_count = (raw_data[col] < 0).sum() if col in cannot_be_negative else 0
    
    below_count = ((raw_data[col] >= 0) & (raw_data[col] < min_val)).sum() if col in cannot_be_negative else (raw_data[col] < min_val).sum()
    
    above_count = (raw_data[col] > max_val).sum()
    
    outlier_details.append({
        'Parameter': col,
        'Negative': negative_count,
        'Below Min': below_count,
        'Above Max': above_count,
        'Total Outliers': negative_count + below_count + above_count
    })
    
outliers_summary_raw_data = pd.DataFrame(outlier_details)

print('\nOutlier Breakdown by parameter:')
print(outliers_summary_raw_data.to_string(index=False))

#Ploting
num_cols = list(normal_ranges.keys())
print('\nSkewness:')
print(raw_data[num_cols].skew())

fig, axes = plt.subplots(4, 2, figsize=(14, 16))
axes = axes.flatten()

for i, col in enumerate(num_cols):
    min_val, max_val = normal_ranges[col]
    sns.histplot(raw_data[col].dropna(), bins=200, kde=True, ax=axes[i])
    axes[i].axvline(min_val, color='red', linestyle='--')
    axes[i].axvline(max_val, color='red', linestyle='--')
    axes[i].set_title(col)
    axes[i].set_xlabel('')
    
plt.suptitle('Distribution - full data (red = normal range)')
plt.tight_layout()
plt.show()

#Same plots without the out of range, to see the shape
in_range_data = raw_data[~overall_outlier_mask]

fig, axes = plt.subplots(4, 2, figsize=(14, 16))
axes = axes.flatten()

for i, col in enumerate(num_cols):
    sns.histplot(in_range_data[col].dropna(), bins=100, kde=True, ax=axes[i])
    axes[i].set_title(col)
    axes[i].set_xlabel('')
    
plt.suptitle('Distribution - in range rows only')
plt.tight_layout()
plt.show()

#Checking if the distribution differ by reactor:
fig, axes = plt.subplots(4, 2, figsize=(14, 16))
axes = axes.flatten()

for i, col in enumerate(num_cols):
    sns.kdeplot(data=in_range_data, x=col, hue='production_line_id',
                common_norm=False, ax=axes[i], legend=(i == 0))
    axes[i].set_title(col)
    axes[i].set_xlabel('')
    
plt.suptitle('Distributions by production line')
plt.tight_layout()
plt.show()

#Checking the out of range values 
for col, (min_val, max_val) in normal_ranges.items():
    out_mask = raw_data[col].notnull() & ((raw_data[col] < min_val) | (raw_data[col] > max_val))
    
    if out_mask.sum() > 0:
        print(f'\n{col}: {out_mask.sum()} out of range values, most common:')
        print(raw_data.loc[out_mask, col].round(2).value_counts().head(5))
        

# Checking the mixing_torque_nm
raw_data['low_torque'] = raw_data['mixing_torque_nm'] < 11.4

print('\nShare of low_torque batches by production line:')
print(raw_data.groupby('production_line_id')['low_torque'].mean().round(3))

print('\nShare of low torque batches by plant:')
print(raw_data.groupby('plant_location')['low_torque'].mean().round(3))

print('\nStability by torque population:')
print(raw_data.groupby('low_torque')['stability_months'].describe())

#Stability by reactor to check the 3 reactors.
print('\nStability by Reactor:')
print(raw_data.groupby('production_line_id')['stability_months'].agg(['mean', 'median', 'min', 'count']).round(2))

plt.figure(figsize=(12, 5))
sns.boxplot(data=raw_data, x='production_line_id', y='stability_months')
plt.xticks(rotation=45)
plt.title('Stability by Reactor')
plt.tight_layout()
plt.show()

plt.figure(figsize=(8, 5))

sns.scatterplot(data=raw_data.sample(20000, random_state=42),
                x='mixing_torque_nm', y='stability_months',
                hue='production_line_id', alpha=0.4, s=10)
plt.title('Torque vs Stability')
plt.tight_layout()
plt.show()

#Cheking Correlation between sensors and Stability
corr = in_range_data[num_cols].corr()
print('\nCorrelation with Stability_months')
print(corr['stability_months'].sort_values(ascending=False).round(3))

plt.figure(figsize=(9, 7))
sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', center=0)
plt.title('Correlation matrix (in-range rows)')
plt.tight_layout()
plt.show()

#Checking the low torque share by plant and reactor
print('\nShare of low torque batches by reactor and plant')
print(pd.crosstab(raw_data['production_line_id'], raw_data['plant_country'], 
                  values=raw_data['low_torque'], aggfunc='mean').round(3))

#Separating the plant effect from the reactor effect
print('\nStability by plant:')
print(raw_data.groupby('plant_country')['stability_months'].agg(['mean', 'median', 'count']).round(3))

stability_plant_reactor = pd.crosstab(raw_data['production_line_id'], raw_data['plant_country'],
                                      values=raw_data['stability_months'], aggfunc='mean').round(3)
print('\nMean Stability by reactor and plant:')
print(stability_plant_reactor)

low_torque_plant_reactor = pd.crosstab(raw_data['production_line_id'], raw_data['plant_country'],
                                       values=raw_data['low_torque'], aggfunc='mean')

fig, axes = plt.subplots(1, 2, figsize=(16, 7))
sns.heatmap(low_torque_plant_reactor, annot=True, fmt='.2f', cmap='Reds', ax=axes[0])
axes[0].set_title('Share of low torque batches')
sns.heatmap(stability_plant_reactor, annot=True, fmt='.1f', cmap='RdYlGn',ax=axes[1])
axes[1].set_title('Mean Stability (months)')
plt.tight_layout()
plt.show()

#Checking if it appears during a specific time
raw_data['week'] = raw_data['event_timestamp'].dt.to_period('W')
weekly_low_torque = raw_data.groupby(['week', 'production_line_id'])['low_torque'].mean().unstack()

weekly_low_torque.plot(figsize=(14, 6))
plt.title('Weekly share of low torque batches by reactor')
plt.ylabel('Share of batches')
plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
plt.tight_layout()
plt.show()

weekly_stability = raw_data.groupby(['week', 'production_line_id'])['stability_months'].mean().unstack()

weekly_stability.plot(figsize=(14, 6))
plt.title('Weekly mean stability by reactor')
plt.ylabel('Months')
plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
plt.tight_layout()
plt.show()

#Exact Start date of the low-torque issue in Plant-04
plant04_low = raw_data[(raw_data['plant_country'] == 'Country-04') & (raw_data['low_torque'])]
print('\nFirst low-torque batch in Plant-04:', plant04_low['event_timestamp'].min())
print(plant04_low.groupby('production_line_id')['event_timestamp'].min())

#Cheking the low-torque batches differ on anything else, or only on torque
print('\nMean sensor values, low torque vs normal (Plant-04, reactors 03/07/08 only):')
affected = raw_data[(raw_data['plant_country'] == 'Country-04') &
                    (raw_data['production_line_id'].isin(['Fragrance-Synthesis-Reactor-03',
                                                          'Fragrance-Synthesis-Reactor-07',
                                                          'Fragrance-Synthesis-Reactor-08']))]
print(affected.groupby('low_torque')[num_cols].mean().round(3).T)

#Checking sensor fault codes: how many of each, and are they concentrated anywhere
fault_codes = {'reaction_temperature_celsius': 210, 'vessel_pressure_bar': -1,
               'density_g_cm3': 860, 'ph_level': 14}
for col, code in fault_codes.items():
    mask = raw_data[col].round(2) == code
    print(f'\n{col} == {code}: {mask.sum()} rows')
    print(raw_data.loc[mask, 'plant_country'].value_counts())

#Is Plant-01 better because it runs cooler?
print('\nMean temperature and torque by plant:')
print(in_range_data.groupby('plant_country')[['reaction_temperature_celsius', 'mixing_torque_nm', 'stability_months']].mean().round(2))

#Replacing the sensor fault codes with NaN in clean_data
clean_data = raw_data.copy()
for col, code in fault_codes.items():
    clean_data.loc[clean_data[col].round(2) == code, col] = float('nan')

#Clean comparison of the two torque populations in the affected reactors
affected_clean = clean_data[(clean_data['plant_country'] == 'Country-04') &
                            (clean_data['production_line_id'].isin(['Fragrance-Synthesis-Reactor-03',
                                                                    'Fragrance-Synthesis-Reactor-07',
                                                                    'Fragrance-Synthesis-Reactor-08']))]
print('\nSensor means, low torque vs normal (fault codes removed):')
print(affected_clean.groupby('low_torque')[num_cols].mean().round(3).T)

#Where and when do the fault codes appear inside Plant-04?
raw_data['has_fault_code'] = False
for col, code in fault_codes.items():
    raw_data['has_fault_code'] = raw_data['has_fault_code'] | (raw_data[col].round(2) == code)

plant04 = raw_data[raw_data['plant_country'] == 'Country-04']

print('\nShare of batches with a fault code, by reactor (Plant-04):')
print(plant04.groupby('production_line_id')['has_fault_code'].mean().round(3))

print('\nFirst fault-coded batch in Plant-04:', plant04.loc[plant04['has_fault_code'], 'event_timestamp'].min())

plant04.groupby(['week', 'production_line_id'])['has_fault_code'].mean().unstack().plot(figsize=(14, 6))
plt.title('Weekly share of fault-coded batches by reactor (Plant-04)')
plt.ylabel('Share of batches')
plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
plt.tight_layout()
plt.show()

#Daily view around 8 May to confirm it is a clean step and not a ramp
daily = plant04.set_index('event_timestamp').resample('D')['low_torque'].mean()
daily.loc['2023-05-01':'2023-05-15'].plot(figsize=(10, 4), marker='o')
plt.title('Daily share of low-torque batches, Plant-04, early May')
plt.tight_layout()
plt.show()