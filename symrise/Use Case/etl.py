import pandas as pd
import numpy as np

raw_data = pd.read_csv('data_set.csv')
print('Raw Shape:', raw_data.shape)

clean = raw_data.copy()

#Time Stamp
clean['event_timestamp'] =  pd.to_datetime(raw_data['event_timestamp'], format='mixed', dayfirst=True)

#Plant_location and plant_country are identical since we have one plant per country with multiples lines (Reactors)
assert (clean.groupby('plant_country')['plant_location'].nunique() == 1).all()
clean = clean.drop(columns=['plant_location'])

#Temperature, converting the rows with F into C, and dropping the temp_unit
is_f = clean['temp_unit'] == 'F'
print(f'\nRows F converted to C: {is_f.sum()}')

clean['reaction_temperature_celsius'] = clean['temp_value']
clean.loc[is_f, 'reaction_temperature_celsius'] = (clean.loc[is_f, 'temp_value'] - 32) * 5 / 9
clean = clean.drop(columns=['temp_value', 'temp_unit'])

#Sensor fault codes, the constant NaN that where found in the EDA process that are constant
fault_codes = {
    'reaction_temperature_celsius': 210,
    'vessel_pressure_bar': -1,
    'density_g_cm3': 860,
    'ph_level': 14
}

print('\nFault codes replaced by NaN:')
for col, code in fault_codes.items():
    mask = clean[col].round(2) == code
    clean.loc[mask, col] = np.nan
    print(f' {col} == {code}: {mask.sum()}')
    

#Physically impossible values transformation to NaN
cannot_be_negative = ['vessel_pressure_bar', 'mixing_torque_nm', 'mass_flow_rate_kg_h']
print('\nNegative values replaced by NaN:')
for col in cannot_be_negative:
    mask = clean[col] < 0
    clean.loc[mask, col] = np.nan
    print(f' {col}: {mask.sum()}')
    
#Reordering column to match the Spec
sensor_cols = ['reaction_temperature_celsius', 'vessel_pressure_bar', 'refractive_index',
               'density_g_cm3', 'ph_level', 'mixing_torque_nm', 'mass_flow_rate_kg_h']
clean = clean[['batch_id', 'event_timestamp', 'plant_country', 'production_line_id']
              + sensor_cols
              + ['stability_months', 'purity_grade', 'oxidation_risk_flag']]


#Summary
print('\nMissing values after cleaning')
print(clean[sensor_cols].isna().sum())
print('\nSensor rangtes after cleaning')
print(clean[sensor_cols].describe().loc[['min', 'max']].T)

clean.to_csv('data_clean.csv', index=False)
print('\nClean Shape', clean.shape)