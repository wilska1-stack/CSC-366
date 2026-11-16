import io
import re
from html.parser import HTMLParser

import pandas as pd
import requests


def fetch_espn_wins(start_year=2016, end_year=2025):
  print('--- [1/5] Fetching Win Totals from ESPN API ---')
  win_records = []

  for year in range(start_year, end_year + 1):
    url = f'https://site.api.espn.com/apis/v2/sports/football/nfl/standings?season={year}'
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    data = response.json()
    found_teams = 0
    for group in data.get('children', []):
      for entry in group.get('standings', {}).get('entries', []):
        team_name = entry.get('team', {}).get('displayName')
        wins = next(
            (
                stat.get('value')
                for stat in entry.get('stats', [])
                if stat.get('name') == 'wins'
            ),
            None,
        )
        if team_name and wins is not None:
          win_records.append(
              {'year': year, 'team': team_name, 'total_wins': int(wins)}
          )
          found_teams += 1
    if found_teams != 32:
      raise ValueError(
          f'ESPN returned {found_teams} teams for {year}; expected 32. '
          'No simulated win totals were added.'
      )

  df_wins = pd.DataFrame(win_records)

  team_map = {
      'Washington Football Team': 'Washington Commanders',
      'Washington Redskins': 'Washington Commanders',
      'Oakland Raiders': 'Las Vegas Raiders',
      'San Diego Chargers': 'Los Angeles Chargers',
      'St. Louis Rams': 'Los Angeles Rams',
  }
  df_wins['team'] = df_wins['team'].replace(team_map)
  print(f'Successfully processed {len(df_wins)} win records across seasons.')
  return df_wins


class _PositionalSpendingParser(HTMLParser):
  def __init__(self):
    super().__init__()
    self.year = None
    self.year_stack = []
    self.in_row = False
    self.in_cell = False
    self.cell_text = ''
    self.team_code = None
    self.row = []
    self.rows = {}

  def handle_starttag(self, tag, attrs):
    attributes = dict(attrs)
    if tag == 'div':
      self.year_stack.append(self.year)
      match = re.fullmatch(r'y(\d{4})', attributes.get('id', ''))
      if match:
        self.year = int(match.group(1))
    if tag == 'tr' and self.year is not None:
      self.in_row = True
      self.row = []
    if tag in ('td', 'th') and self.in_row:
      self.in_cell = True
      self.cell_text = ''
      self.team_code = None
    if tag == 'a' and self.in_cell:
      classes = attributes.get('class', '').split()
      if 'team-link' in classes:
        self.team_code = next(
            (value for value in classes if re.fullmatch(r'[A-Z]{2,3}', value)),
            None,
        )

  def handle_data(self, data):
    if self.in_cell:
      self.cell_text += data

  def handle_endtag(self, tag):
    if tag in ('td', 'th') and self.in_cell:
      self.row.append((self.team_code, self.cell_text.strip()))
      self.in_cell = False
    if tag == 'tr' and self.in_row:
      if self.row and self.row[0][0]:
        self.rows.setdefault(self.year, []).append(self.row)
      self.in_row = False
    if tag == 'div' and self.year_stack:
      self.year = self.year_stack.pop()


def fetch_overthecap_spending(start_year=2016, end_year=2025):
  """Scrape Over the Cap's annual tables; spending values are in US dollars.

  The project's defensive-line group combines IDL and EDGE, while defensive
  backs combines safety and cornerback spending.
  """
  print('--- [2/5] Fetching Positional Cap Spending from Over the Cap ---')
  response = requests.get('https://overthecap.com/positional-spending', timeout=30)
  response.raise_for_status()

  parser = _PositionalSpendingParser()
  parser.feed(response.text)
  team_names = {
      'ARI': 'Arizona Cardinals',
      'ATL': 'Atlanta Falcons',
      'BAL': 'Baltimore Ravens',
      'BUF': 'Buffalo Bills',
      'CAR': 'Carolina Panthers',
      'CHI': 'Chicago Bears',
      'CIN': 'Cincinnati Bengals',
      'CLE': 'Cleveland Browns',
      'DAL': 'Dallas Cowboys',
      'DEN': 'Denver Broncos',
      'DET': 'Detroit Lions',
      'GB': 'Green Bay Packers',
      'HOU': 'Houston Texans',
      'IND': 'Indianapolis Colts',
      'JAX': 'Jacksonville Jaguars',
      'KC': 'Kansas City Chiefs',
      'LAC': 'Los Angeles Chargers',
      'LA': 'Los Angeles Rams',
      'LAR': 'Los Angeles Rams',
      'LV': 'Las Vegas Raiders',
      'MIA': 'Miami Dolphins',
      'MIN': 'Minnesota Vikings',
      'NE': 'New England Patriots',
      'NO': 'New Orleans Saints',
      'NYG': 'New York Giants',
      'NYJ': 'New York Jets',
      'OAK': 'Las Vegas Raiders',
      'PHI': 'Philadelphia Eagles',
      'PIT': 'Pittsburgh Steelers',
      'SD': 'Los Angeles Chargers',
      'SEA': 'Seattle Seahawks',
      'SF': 'San Francisco 49ers',
      'TB': 'Tampa Bay Buccaneers',
      'TEN': 'Tennessee Titans',
      'WAS': 'Washington Commanders',
  }
  source_columns = [
      'team',
      'quarterback',
      'running_back',
      'wide_receiver',
      'tight_end',
      'offensive_line',
      'offense_total',
      'defensive_line_interior',
      'defensive_edge',
      'linebackers',
      'safeties',
      'cornerbacks',
      'defense_total',
  ]
  spending_rows = []

  for year in range(start_year, end_year + 1):
    year_rows = parser.rows.get(year, [])
    if len(year_rows) != 32:
      raise ValueError(
          f'Over the Cap returned {len(year_rows)} teams for {year}; '
          'expected 32. Positional spending data was not simulated.'
      )
    seen_teams = set()
    for cells in year_rows:
      team_code = cells[0][0]
      if team_code not in team_names:
        raise ValueError(
            f'Unrecognized Over the Cap team abbreviation: {team_code}'
        )
      team = team_names[team_code]
      if team in seen_teams:
        raise ValueError(f'Duplicate Over the Cap row for {team} in {year}.')
      seen_teams.add(team)
      if len(cells) != len(source_columns):
        raise ValueError(
            f'Unexpected Over the Cap table format for {team}, {year}: '
            f'expected {len(source_columns)} columns, found {len(cells)}.'
        )
      values = {}
      for column, (_, text) in zip(source_columns[1:], cells[1:]):
        try:
          values[column] = int(text.replace('$', '').replace(',', ''))
        except ValueError as error:
          raise ValueError(
              f'Invalid Over the Cap amount for {team}, {year}, {column}: '
              f'{text!r}'
          ) from error
      spending_rows.append(
          {
              'year': year,
              'team': team,
              'quarterback': values['quarterback'],
              'running_back': values['running_back'],
              'wide_receiver': values['wide_receiver'],
              'tight_end': values['tight_end'],
              'offensive_line': values['offensive_line'],
              'defensive_line': (
                  values['defensive_line_interior'] + values['defensive_edge']
              ),
              'linebackers': values['linebackers'],
              'defensive_backs': values['safeties'] + values['cornerbacks'],
              'total_amount_spent': (
                  values['offense_total'] + values['defense_total']
              ),
          }
      )

  df_spending = pd.DataFrame(spending_rows)
  print(
      f'Successfully processed {len(df_spending)} Over the Cap team-season '
      'records. Amounts are in US dollars.'
  )
  return df_spending


def fetch_nflverse_rosters(start_year=2016, end_year=2025):
  print('--- [3/5] Fetching Player Rosters from nflverse ---')
  team_names = {
      'ARI': 'Arizona Cardinals',
      'ATL': 'Atlanta Falcons',
      'BAL': 'Baltimore Ravens',
      'BUF': 'Buffalo Bills',
      'CAR': 'Carolina Panthers',
      'CHI': 'Chicago Bears',
      'CIN': 'Cincinnati Bengals',
      'CLE': 'Cleveland Browns',
      'DAL': 'Dallas Cowboys',
      'DEN': 'Denver Broncos',
      'DET': 'Detroit Lions',
      'GB': 'Green Bay Packers',
      'HOU': 'Houston Texans',
      'IND': 'Indianapolis Colts',
      'JAX': 'Jacksonville Jaguars',
      'KC': 'Kansas City Chiefs',
      'LAC': 'Los Angeles Chargers',
      'LA': 'Los Angeles Rams',
      'LV': 'Las Vegas Raiders',
      'MIA': 'Miami Dolphins',
      'MIN': 'Minnesota Vikings',
      'NE': 'New England Patriots',
      'NO': 'New Orleans Saints',
      'NYG': 'New York Giants',
      'NYJ': 'New York Jets',
      'OAK': 'Las Vegas Raiders',
      'PHI': 'Philadelphia Eagles',
      'PIT': 'Pittsburgh Steelers',
      'SD': 'Los Angeles Chargers',
      'SEA': 'Seattle Seahawks',
      'SF': 'San Francisco 49ers',
      'TB': 'Tampa Bay Buccaneers',
      'TEN': 'Tennessee Titans',
      'WAS': 'Washington Commanders',
  }
  position_groups = {
      'DB': 'defensive_backs',
      'LB': 'linebackers',
      'DL': 'defensive_line',
      'QB': 'quarterback',
      'WR': 'wide_receiver',
      'RB': 'running_back',
      'TE': 'tight_end',
      'OL': 'offensive_line',
  }
  roster_years = []

  for year in range(start_year, end_year + 1):
    url = (
        'https://github.com/nflverse/nflverse-data/releases/download/'
        f'rosters/roster_{year}.csv'
    )
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    roster = pd.read_csv(io.BytesIO(response.content))
    required_columns = {'season', 'team', 'position', 'full_name'}
    missing_columns = required_columns.difference(roster.columns)
    if missing_columns:
      raise ValueError(
          f'nflverse roster for {year} is missing columns: '
          f'{sorted(missing_columns)}'
      )
    roster_years.append(roster[list(required_columns)].copy())

  rosters = pd.concat(roster_years, ignore_index=True)
  unknown_teams = sorted(set(rosters['team'].dropna()) - set(team_names))
  if unknown_teams:
    raise ValueError(f'Unrecognized nflverse team abbreviations: {unknown_teams}')

  rosters['team'] = rosters['team'].map(team_names)
  roster_counts = (
      rosters.groupby(['season', 'team'])
      .agg(roster_total_players=('full_name', 'nunique'))
      .reset_index()
      .rename(columns={'season': 'year'})
  )
  positional_counts = (
      rosters.assign(roster_group=rosters['position'].map(position_groups))
      .dropna(subset=['roster_group'])
      .groupby(['season', 'team', 'roster_group'])
      .size()
      .unstack(fill_value=0)
      .reset_index()
      .rename(columns={'season': 'year'})
  )
  roster_counts = roster_counts.merge(
      positional_counts, on=['year', 'team'], how='left'
  )
  roster_columns = list(position_groups.values())
  roster_counts[roster_columns] = roster_counts[roster_columns].fillna(0).astype(int)
  roster_counts = roster_counts.rename(
      columns={column: f'roster_{column}_count' for column in roster_columns}
  )
  print(f'Successfully processed {len(rosters)} nflverse roster records.')
  return roster_counts


def build_final_dataset(df_wins, df_spending, df_rosters):
  print('--- [4/5] Merging Multi-Source Data & Structuring ---')
  merged = pd.merge(df_spending, df_wins, on=['year', 'team'], how='inner')
  merged = pd.merge(merged, df_rosters, on=['year', 'team'], how='left')
  merged = merged.drop_duplicates(subset=['year', 'team'])

  cols_order = [
      'year',
      'team',
      'defensive_backs',
      'linebackers',
      'defensive_line',
      'quarterback',
      'wide_receiver',
      'running_back',
      'tight_end',
      'offensive_line',
      'total_amount_spent',
      'total_wins',
      'roster_total_players',
      'roster_defensive_backs_count',
      'roster_linebackers_count',
      'roster_defensive_line_count',
      'roster_quarterback_count',
      'roster_wide_receiver_count',
      'roster_running_back_count',
      'roster_tight_end_count',
      'roster_offensive_line_count',
  ]
  return merged[cols_order]


def run_analysis_and_export(merged_df):
  print('--- [5/5] Exporting Outputs and Generating Insights ---')
  merged_df.to_csv('nfl_positional_spending_2016_2025.csv', index=False)
  merged_df.to_json(
      'nfl_positional_spending_2016_2025.json', orient='records', indent=4
  )
  print(
      "✅ Saved 'nfl_positional_spending_2016_2025.csv' and"
      " 'nfl_positional_spending_2016_2025.json'"
  )


if __name__ == '__main__':
  df_wins = fetch_espn_wins(2016, 2025)
  df_spending = fetch_overthecap_spending(2016, 2025)
  df_rosters = fetch_nflverse_rosters(2016, 2025)
  final_df = build_final_dataset(df_wins, df_spending, df_rosters)
  run_analysis_and_export(final_df)