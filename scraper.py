import json
import re
from datetime import date, datetime
import pandas as pd
import requests

def parse_json(text):
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    elif not text.startswith("{") and not text.startswith("["):
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            text = match.group(1)
    return json.loads(text)

def fix_name(raw_name):
    name = str(raw_name or "").strip()
    if "," in name:
        parts = [part.strip() for part in name.split(",", 1)]
        if len(parts) == 2 and parts[1]:
            return f"{parts[1]} {parts[0]}"
    return name

def get_position_group(pos):
    p = str(pos or "").strip().upper()
    if p in ("D", "LD", "RD"):
        return "D"
    if p in ("C", "LW", "RW", "F"):
        return "F"
    return "Other"

def calc_decimal_age(bday_str):
    if not bday_str:
        return None
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%Y/%m/%d"):
        try:
            bday = datetime.strptime(str(bday_str).strip(), fmt).date()
            return round((date.today() - bday).days / 365.25, 2)
        except ValueError:
            continue
    return None

def get_age_factor(age):
    if age is None:
        return 1.15
    if age < 18.0:
        return 1.35
    elif age < 19.0:
        return 1.25
    elif age < 20.0:
        return 1.10
    return 1.00

def run_prospect_engine():
    # Official public HockeyTech/CHL read-only keys: [client_code, api_key, NHLe]
    leagues = {
        "OHL":   ("ohl",   "2976319eb44abe94", 0.30),
        "WHL":   ("whl",   "41b145a848f4bd67", 0.29),
        "QMJHL": ("lhjmq", "f322673b6bcae299", 0.26),
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    rows = []

    for league_name, (client_code, api_key, nhle) in leagues.items():
        # 1. Auto-detect current 2026-27 regular season ID
        seasons_url = (
            f"https://lscluster.hockeytech.com/feed/index.php"
            f"?feed=modulekit&view=seasons&fmt=json&key={api_key}&client_code={client_code}"
        )
        s_resp = requests.get(seasons_url, headers=headers, timeout=20)
        s_resp.raise_for_status()
        seasons = parse_json(s_resp.text).get("SiteKit", {}).get("Seasons", [])

        season_id = None
        for s in seasons:
            name = str(s.get("season_name", "")).lower()
            if ("2026-27" in name or "2026-2027" in name) and "pre" not in name and "playoff" not in name:
                season_id = s.get("season_id")
                break
        if not season_id:
            for s in seasons:
                if str(s.get("career", "")) == "1":
                    season_id = s.get("season_id")
                    break

        print(f"{league_name}: using season_id={season_id}")

        # 2. Pull top 500 live skaters from official league feed
        stats_url = (
            f"https://lscluster.hockeytech.com/feed/index.php"
            f"?feed=modulekit&view=statviewtype&type=topscorers&first=0&limit=500"
            f"&season_id={season_id}&fmt=json&key={api_key}&client_code={client_code}"
        )
        p_resp = requests.get(stats_url, headers=headers, timeout=25)
        p_resp.raise_for_status()
        players = parse_json(p_resp.text).get("SiteKit", {}).get("Statviewtype", [])

        for p in players:
            if not isinstance(p, dict):
                continue

            raw_name = p.get("name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
            name = fix_name(raw_name)
            try:
                gp = int(p.get("games_played", 0) or 0)
                goals = int(p.get("goals", 0) or 0)
                assists = int(p.get("assists", 0) or 0)
                tp = int(p.get("points", 0) or 0)
            except (ValueError, TypeError):
                continue

            if not name or gp <= 0:
                continue

            pos = str(p.get("position") or "").strip().upper()
            team = str(p.get("team_code") or p.get("team_name") or "").strip().upper()
            age = calc_decimal_age(p.get("birthdate") or p.get("bday"))
            age_factor = get_age_factor(age)
            ppg = round(tp / gp, 2)
            proj_nhl_ppg = round(ppg * nhle * age_factor, 2)

            rows.append({
                "Player": name,
                "Team": team,
                "Position": pos,
                "Position_Group": get_position_group(pos),
                "League": league_name,
                "Age": age if age is not None else "",
                "GP": gp,
                "G": goals,
                "A": assists,
                "TP": tp,
                "PPG": ppg,
                "NHLe_Multiplier": nhle,
                "Age_Factor": age_factor,
                "Projected_NHL_PPG": proj_nhl_ppg,
            })

    if not rows:
        raise RuntimeError("Zero real prospects returned from HockeyTech API.")

    final_df = pd.DataFrame(rows).sort_values(by="Projected_NHL_PPG", ascending=False)
    final_df.to_csv("live_prospects_feed.csv", index=False)
    print(f"Success! Exported {len(final_df)} live CHL prospects to live_prospects_feed.csv")

if __name__ == "__main__":
    run_prospect_engine()
