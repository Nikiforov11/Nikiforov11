# Standard librearies
import pandas as pd
import numpy as np

raw_data = pd.read_csv('housing.csv')

#NOTE ETL(Extraction, Tranforming, Loading)
# We drop the 5 island rows since its considered and outlier
print(f'Rows before: {len(raw_data)}')
island_indexes = raw_data[raw_data['ocean_proximity'] == 'ISLAND'].index
process_data = raw_data.drop(island_indexes)
print(f'After: {len(process_data)}')

#NOTE Features Engineering
# One-hot encoding
process_data = pd.get_dummies(process_data, columns=['ocean_proximity'])
# print(process_data.head())

# Distance to important cities, using the Haversine distance
california_hubs = {
    'Los Angeles': (34.0522, -118.2437),
    'San Diego': (32.7157, -117.1611),
    'San Jose': (37.3382, -121.8863),
    'San Francisco': (37.7749, -122.4194),
    'Fresno': (36.7378, -119.7871)
}

def calculate_harversine(lat1,lon1,lat2,lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2-lat1
    dlon = lon2-lon1
    
    a = np.sin(dlat/2) **2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2) **2
    c = 2 * np.arcsin(np.sqrt(a))
    
    return 6371 * c
    
for hubs, coordinates in california_hubs.items():
    clean_name = hubs.lower().replace(' ', '_')
    col_name = f'dist_to_{clean_name}_km'
    
    city_lat = coordinates[0]
    city_lon = coordinates[1]
    
    process_data[col_name] = calculate_harversine(
        process_data['latitude'], process_data['longitude'], 
        city_lat, city_lon
    )

process_data = process_data.drop(columns=['latitude','longitude'])

#NOTE Computation of the avg_bedrooms, avg_rooms, avg_households, avg_population
# Drop any row that has a missing value
process_data = process_data.dropna()

# Average Rooms per House
process_data['rooms_per_household'] = process_data['total_rooms'] / process_data['households']

# Average Bedrooms per house
process_data['bedrooms_per_household'] = process_data['total_bedrooms'] / process_data['households']

# Average People per house
process_data['population_per_household'] = process_data['population'] / process_data['households']

# Droping the 3 original total columns and replacing them with the avg
columns_to_drop= [
    'total_rooms',
    'total_bedrooms',
    'population',
    'households'
]
process_data = process_data.drop(columns=columns_to_drop)

max_price = process_data['median_house_value'].max()
print(f'The capped maximum price is: {max_price}')

process_data_uncapped = process_data[process_data['median_house_value'] < max_price]
print(f"Rows before dropping cap: {len(process_data)}")
print(f"Rows after dropping cap: {len(process_data_uncapped)}")

#Checking the data before saving
print("Shape of the Dataset:", process_data_uncapped.shape, "\n")
print("First Few Rows of the Dataset:")
print(process_data_uncapped.head(10), "\n\n")
print("Dataset Information:")
print(process_data_uncapped.info(), "\n\n")
print("Number of Missing Values in Each Column:")
print(process_data_uncapped.isna().sum(), "\n\n")
print("Number of Duplicated Rows:\n", process_data_uncapped.duplicated().sum(), "\n\n")
print("Description of the Numerical Dataset:\n", process_data_uncapped.describe(), "\n\n")
print("Number of Unique Values in Each Column:\n", process_data_uncapped.nunique(), "\n\n")
process_data_uncapped.to_csv('data/clean_housing.csv',index=False)