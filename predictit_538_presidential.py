# TO DO
# 1. Add additional odds
# 2. bestBuyNoCost
# 3. Fix workaround in nan values for implied probability
# 4. Dashboard
# 5. Fair probability

# Import modules
import json
import requests
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import pandas as pd
pd.set_option('display.max_rows', None) #print all rows without truncating
import numpy as np
import datetime
import os

# Pull in market data from PredictIt's API
Predictit_URL = "https://www.predictit.org/api/marketdata/all/"
Predictit_response = requests.get(Predictit_URL)
jsondata = Predictit_response.json()

# Replace null values with zero
def dict_clean(items):
    result = {}
    for key, value in items:
        if value is None:
            value = 0
        result[key] = value
    return result
dict_str = json.dumps(jsondata)
jsondata = json.loads(dict_str, object_pairs_hook=dict_clean)

# Market data by contract/price in dataframe
data = []
for p in jsondata['markets']:
    for k in p['contracts']:
        data.append([p['id'],p['name'],k['id'],k['name'],k['bestBuyYesCost'],k['bestBuyNoCost'],k['bestSellYesCost'],k['bestSellNoCost']])

# Pandas dataframe named 'predictit_df'
predictit_df = pd.DataFrame(data)

# Update dataframe column names
predictit_df.columns=['Market_ID','Market_Name','Contract_ID','Contract_Name','bestBuyYesCost','bestBuyNoCost','BestSellYesCost','BestSellNoCost']

# Filter PredicitIt dataframe to presidential state markets/contracts
predictit_df = predictit_df[predictit_df['Market_Name'].str.contains("Which party will win") & predictit_df['Market_Name'].str.contains("2020 presidential election?")]

# Fix annoying typo (double space) in congressional district market names
predictit_df['Market_Name'] = predictit_df['Market_Name'].str.replace('in the  2020','in the 2020')

# Split Market_Name column into state name column
start_string = "Which party will win"
end_string = "in the 2020 presidential election?"
predictit_df['a'], predictit_df['state'] = predictit_df['Market_Name'].str.split(start_string, 1).str
predictit_df['state'], predictit_df['b'] = predictit_df['state'].str.split(end_string, 1).str
del predictit_df['a']
del predictit_df['b']

# Create answer column from contract names
predictit_df['answer'] = predictit_df['Contract_Name'].str.replace('Republican','Trump').str.replace('Democratic','Biden')

# Strip trailing/leading whitespaces in answer and state columns
predictit_df['state'] = predictit_df['state'].str.strip()
predictit_df['answer'] = predictit_df['answer'].str.strip()

# Pull in polling data from 538
pres_polling = pd.read_csv('https://projects.fivethirtyeight.com/polls-page/president_polls.csv')
pres_polling = pres_polling.dropna(subset=['state'])

# Drop extraneous columns
pres_polling = pres_polling.drop(['pollster_id', 'pollster','sponsor_ids','sponsors','display_name', 'pollster_rating_id', 'pollster_rating_name', 'fte_grade', 'sample_size', 'population', 'population_full', 'methodology', 'seat_number', 'seat_name', 'start_date', 'end_date', 'sponsor_candidate', 'internal', 'partisan', 'tracking', 'nationwide_batch', 'ranked_choice_reallocated', 'notes', 'url'], axis=1)

# Standardize congressional district names in 538 with PredictIt
pres_polling['state'] = pres_polling['state'].str.replace('Maine CD-1','ME-01')
pres_polling['state'] = pres_polling['state'].str.replace('Maine CD-2','ME-02')
pres_polling['state'] = pres_polling['state'].str.replace('Nebraska CD-2','NE-02')

# Filter to most recent poll for Biden & Trump
pres_polling['created_at'] = pd.to_datetime(pres_polling['created_at']) #convert 'created_at' to datetime
recent_pres_polling = pres_polling.sort_values(by=['created_at']).drop_duplicates(['state', 'candidate_name'], keep='last')
recent_pres_polling = recent_pres_polling[recent_pres_polling['answer'].isin(['Biden', 'Trump'])]

# Rename 538 'pct' column to recent_poll
recent_pres_polling = recent_pres_polling.rename({'pct': 'recent_poll'}, axis=1)

# Pull in odds
odds_df = pd.read_csv('https://raw.githubusercontent.com/mauricebransfield/predictit_538_odds/master/odds_state_presidential.csv', index_col=[0]) # error_bad_lines=False,

# Replace hyphen in state names with space
odds_df['state'] = odds_df['state'].str.replace('-',' ') 

# Standardize Washington DC & Washington State
odds_df['state'] = odds_df['state'].str.replace('Washington Dc','DC')
odds_df['state'] = odds_df['state'].str.replace('Washington State','Washington')

# Replace party with candidate names
odds_df['answer'] = odds_df['answer'].str.replace('Republicans','Trump')
odds_df['answer'] = odds_df['answer'].str.replace('Democratic','Biden')
odds_df['answer'] = odds_df['answer'].str.replace('Democrats','Biden')
odds_df['answer'] = odds_df['answer'].str.replace('Democrat','Biden')

# Drop columns with all nan values
odds_df = odds_df.dropna(axis=1, how='all')

# Merge PredictIt and odds dataframes together
df = pd.merge(predictit_df, odds_df, on=['state', 'answer'], how='left')

# Merge 538 polls into new dataframe
df = pd.merge(df, recent_pres_polling, on=['state', 'answer'], how='left')

# Sort alphabetically by state
df = df.reindex(df.state.sort_values(ascending=True).index)

# Convert fractional odds to new column of implied probability
# denominator / (denominator + numerator) = implied probability
df['numerator'], df['denominator'] = df['betfair'].str.split('/', 1).str
df['denominator'] = pd.to_numeric(df['denominator'], errors='coerce').fillna(0).astype(np.int64)
df['denominator'] = df['denominator'].mask(df['denominator']==0).fillna(1) # workaround
df['numerator'] = pd.to_numeric(df['numerator'], errors='coerce').fillna(0).astype(np.int64)
df['betfair_imp_prob'] = (df['denominator'] / (df['denominator'] + df['numerator']))

# workaround to fix previous workaround
mask = df['betfair'].isnull()
column_name = 'betfair_imp_prob'
df.loc[mask, column_name] = np.nan

# Create column of difference in betfair & PredictIt
df['betfair-PredicitIt'] = df['betfair_imp_prob']-df['bestBuyYesCost']

# Round 2 decimal places
df['betfair_imp_prob'] = df['betfair_imp_prob'].round(2)
df['betfair-PredicitIt'] = df['betfair-PredicitIt'].round(2)

#print out select columns
print(df[['state', 
            'answer', 
            'recent_poll', 
            'bestBuyYesCost', 
            'betfair',
            'betfair_imp_prob',
            'betfair-PredicitIt']])

# Write dataframe to CSV file in working directory
df.to_csv(r'./predictit_538_odds.csv', sep=',', encoding='utf-8', header='true')

# Write dataframe with timestamp to archive folder
snapshotdate = datetime.datetime.today().strftime('%Y-%m-%d')
os.chdir('C:/Users/Mick/Documents/Python/Python/predictit_538_odds/Archive')
df.to_csv(open(snapshotdate+'.csv','w'))