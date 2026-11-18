import pandas as pd
import requests
from io import StringIO

def run_prospect_engine():
    # Dictionary of leagues: [Target URL, NHLe Multiplier, Age Factor]
    leagues = {
        'OHL': ['https://www.eliteprospects.com/league/ohl/stats/2026-2027', 0.30, 1.25],
        'WHL': ['https://www.eliteprospects.com/league/whl/stats/2026-2027', 0.29, 1.25],
        'QMJHL': ['https://www.eliteprospects.com/league/qmjhl/stats/2026-2027', 0.26, 1.25]
    }
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    all_prospects = []

    for league_name, (url, nhle, age_factor) in leagues.items():
        response = requests.get(url, headers=headers)
        tables = pd.read_html(StringIO(response.text))
        df = tables[0].copy()

        # Clean rows and ensure numbers
        df = df.dropna(subset=['Player', 'GP', 'TP'])
        df['GP'] = pd.to_numeric(df['GP'], errors='coerce')
        df['TP'] = pd.to_numeric(df['TP'], errors='coerce')
        df = df[df['GP'] > 0].copy()

        # Dynamically calculate PPG and NHLe Ceiling
        df['League'] = league_name
        df['PPG'] = round(df['TP'] / df['GP'], 2)
        df['NHLe_Multiplier'] = nhle
        df['Age_Factor'] = age_factor
        df['Projected_NHL_PPG'] = round(df['PPG'] * nhle * age_factor, 2)

        all_prospects.append(df[['Player', 'Team', 'League', 'GP', 'TP', 'PPG', 'Projected_NHL_PPG']])

    # Combine all leagues and export to CSV
    final_df = pd.concat(all_prospects, ignore_index=True)
    final_df.to_csv('live_prospects_feed.csv', index=False)

if __name__ == "__main__":
    run_prospect_engine()
