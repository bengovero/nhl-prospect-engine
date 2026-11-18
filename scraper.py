import pandas as pd
import requests
from io import StringIO

def get_age_factor(age):
    if age <= 17:
        return 1.35
    elif age == 18:
        return 1.25
    elif age == 19:
        return 1.10
    else:
        return 1.00

def run_prospect_engine():
    # Live 2026-2027 QuantHockey leaderboards: [URL, NHLe Multiplier]
    leagues = {
        'OHL': ['https://www.quanthockey.com/ohl/en/seasons/ohl-players-stats.html', 0.30],
        'WHL': ['https://www.quanthockey.com/whl/en/seasons/whl-players-stats.html', 0.29],
        'QMJHL': ['https://www.quanthockey.com/qmjhl/en/seasons/qmjhl-players-stats.html', 0.26],
        'USHL': ['https://www.quanthockey.com/ushl/en/seasons/ushl-players-stats.html', 0.27]
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    all_prospects = []

    for league_name, (url, nhle) in leagues.items():
        print(f"Fetching {league_name}...")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))
        # Pick the largest table on the page (the main player stats table)
        df = max(tables, key=len).copy()

        # Flatten multi-level headers if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[-1] for col in df.columns]

        # Standardize column names
        df = df.rename(columns={'Name': 'Player', 'P': 'TP'})

        # Keep valid player rows with numeric Age, GP, and TP
        df = df.dropna(subset=['Player', 'Age', 'GP', 'TP'])
        df['Age'] = pd.to_numeric(df['Age'], errors='coerce')
        df['GP'] = pd.to_numeric(df['GP'], errors='coerce')
        df['TP'] = pd.to_numeric(df['TP'], errors='coerce')
        df = df.dropna(subset=['Age', 'GP', 'TP'])
        df = df[df['GP'] > 0].copy()

        # Calculate PPG, dynamic Age Factor, and Projected NHL PPG
        df['League'] = league_name
        df['PPG'] = (df['TP'] / df['GP']).round(2)
        df['NHLe_Multiplier'] = nhle
        df['Age_Factor'] = df['Age'].apply(get_age_factor)
        df['Projected_NHL_PPG'] = (df['PPG'] * nhle * df['Age_Factor']).round(2)

        cols = ['Player', 'League', 'Age', 'GP', 'TP', 'PPG', 'NHLe_Multiplier', 'Age_Factor', 'Projected_NHL_PPG']
        all_prospects.append(df[cols])

    final_df = pd.concat(all_prospects, ignore_index=True)
    final_df = final_df.sort_values(by='Projected_NHL_PPG', ascending=False)
    final_df.to_csv('live_prospects_feed.csv', index=False)
    print(f"Success! Exported {len(final_df)} prospects to live_prospects_feed.csv")

if __name__ == "__main__":
    run_prospect_engine()
