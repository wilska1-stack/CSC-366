"""Step 1 of cleaning: validate, fix types, and normalize the NFL spending data.

Input:  the CSV made by the scraper (nfl_positional_spending_2016_2025.csv)
Output: nfl_spending_clean.csv  - one row per team-season, with new columns
        cleaning_log.txt         - every check that ran and what it found

Run:  python clean_nfl_data.py "path/to/nfl_positional_spending_2016_2025.csv"
"""

import sys
from pathlib import Path

import pandas as pd

POSITIONS = [
    'defensive_backs',
    'linebackers',
    'defensive_line',
    'quarterback',
    'wide_receiver',
    'running_back',
    'tight_end',
    'offensive_line',
]
ROSTER_COLS = [f'roster_{p}_count' for p in POSITIONS]

log_lines = []


def log(message):
  print(message)
  log_lines.append(message)


def check(condition, message):
  """Log PASS/FAIL for one data-quality rule."""
  log(f"  [{'PASS' if condition else 'FAIL'}] {message}")
  return condition


# ---------------------------------------------------------------------------
# 1. Load and fix basic formatting
# ---------------------------------------------------------------------------
def load(path):
  log('1. LOAD')
  df = pd.read_csv(path)
  log(f'  Loaded {len(df)} rows x {len(df.columns)} columns from {path}')

  df.columns = df.columns.str.strip().str.lower()
  df['team'] = df['team'].astype(str).str.strip()
  numeric_cols = [c for c in df.columns if c != 'team']
  df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
  df = df.sort_values(['year', 'team']).reset_index(drop=True)
  return df


# ---------------------------------------------------------------------------
# 2. Structural checks: is every team-season there exactly once, with values?
# ---------------------------------------------------------------------------
def validate_structure(df):
  log('\n2. STRUCTURE CHECKS')
  check(df.isna().sum().sum() == 0, f'No missing values (found {df.isna().sum().sum()})')
  dups = df.duplicated(['year', 'team']).sum()
  check(dups == 0, f'No duplicate team-seasons (found {dups})')
  check(df['team'].nunique() == 32, f"32 distinct teams (found {df['team'].nunique()})")
  per_year = df.groupby('year').size()
  check((per_year == 32).all(), f'32 teams in every season {per_year.to_dict()}')
  negatives = (df[POSITIONS + ['total_amount_spent']] < 0).sum().sum()
  check(negatives == 0, f'No negative dollar amounts (found {negatives})')

  diff = df['total_amount_spent'] - df[POSITIONS].sum(axis=1)
  check(
      (diff == 0).all(),
      'total_amount_spent equals the sum of the 8 position groups '
      '(so it leaves out kickers, punters, long snappers and fullbacks)',
  )


# ---------------------------------------------------------------------------
# 3. Wins: the season length changed, so raw wins are not comparable
# ---------------------------------------------------------------------------
def clean_wins(df):
  log('\n3. WINS')
  # The NFL went from 16 to 17 games in 2021. Buffalo and Cincinnati only
  # played 16 in 2022 because their Week 17 game was cancelled.
  df['games_played'] = df['year'].apply(lambda y: 16 if y <= 2020 else 17)
  cancelled = (df['year'] == 2022) & df['team'].isin(
      ['Buffalo Bills', 'Cincinnati Bengals']
  )
  df.loc[cancelled, 'games_played'] = 16

  check(
      df['total_wins'].between(0, df['games_played']).all(),
      'Every win total is between 0 and games played',
  )

  # In a full league, total wins = total games / 2. Any shortfall means ties.
  league = df.groupby('year').agg(
      wins=('total_wins', 'sum'), games=('games_played', 'sum')
  )
  league['implied_ties'] = league['games'] / 2 - league['wins']
  log('  Wins per season vs. games/2 (a gap = tied games, which count as 0 wins):')
  for year, row in league.iterrows():
    log(f"    {year}: {int(row.wins)} wins, {int(row.games / 2)} games, "
        f'{int(row.implied_ties)} tie(s)')

  # Win percentage puts 16- and 17-game seasons on the same scale.
  # NOTE: ties are counted as losses here because the scraper did not save
  # ties. Standard NFL win % counts a tie as half a win; see the README.
  df['win_pct'] = (df['total_wins'] / df['games_played']).round(4)
  log('  Added games_played and win_pct (wins / games_played)')
  return df


# ---------------------------------------------------------------------------
# 4. Spending: the salary cap grew a lot, so raw dollars are not comparable
# ---------------------------------------------------------------------------
def normalize_spending(df):
  log('\n4. SPENDING')
  avg_total = (df.groupby('year')['total_amount_spent'].mean() / 1e6).round(1)
  log(f'  Average team spending by year ($M): {avg_total.to_dict()}')
  log('  Spending grows ~70% over the decade, so a 2016 dollar and a 2025 '
      'dollar mean different things. Adding two adjusted versions:')

  for pos in POSITIONS:
    # Share: what fraction of this team's spending went to this position.
    df[f'{pos}_share'] = (df[pos] / df['total_amount_spent']).round(4)
    # Z-score within the season: how far above/below that year's league
    # average this team spent on the position (in standard deviations).
    by_year = df.groupby('year')[pos]
    df[f'{pos}_z'] = ((df[pos] - by_year.transform('mean'))
                      / by_year.transform('std')).round(3)
  by_year = df.groupby('year')['total_amount_spent']
  df['total_spent_z'] = ((df['total_amount_spent'] - by_year.transform('mean'))
                         / by_year.transform('std')).round(3)
  log('    <position>_share = position dollars / team total that season')
  log('    <position>_z     = standard deviations from that season\'s league mean')

  shares = df[[f'{p}_share' for p in POSITIONS]].sum(axis=1)
  check((shares.round(3) == 1).all(), 'Shares add to 1 for every team-season')

  # Flag (do not delete) unusually large contracts. These are real -- e.g. a
  # new QB extension -- and removing them would remove the thing we study.
  z_cols = [f'{p}_z' for p in POSITIONS]
  extreme = df[(df[z_cols].abs() > 3).any(axis=1)]
  df['has_extreme_spend'] = (df[z_cols].abs() > 3).any(axis=1)
  log(f'  Flagged {len(extreme)} team-season(s) with a position more than '
      '3 SD from its season mean (kept, column has_extreme_spend):')
  for _, row in extreme.iterrows():
    pos = max(z_cols, key=lambda c: abs(row[c]))
    log(f"    {row.year} {row.team}: {pos[:-2]} z = {row[pos]}")
  return df


# ---------------------------------------------------------------------------
# 5. Roster counts: supporting data, check that it looks reasonable
# ---------------------------------------------------------------------------
def check_rosters(df):
  log('\n5. ROSTER COUNTS')
  log('  These count every player listed on the team during the season '
      '(not the 53-man roster), so numbers near 90-110 are normal.')
  desc = df['roster_total_players'].describe().round(1)
  log(f"  roster_total_players: min {desc['min']}, median {desc['50%']}, "
      f"max {desc['max']}")
  check(
      (df[ROSTER_COLS].sum(axis=1) <= df['roster_total_players']).all(),
      'Position counts never add to more than the roster total',
  )
  q1, q3 = df['roster_total_players'].quantile([0.25, 0.75])
  low = df['roster_total_players'] < q1 - 1.5 * (q3 - q1)
  df['roster_count_low'] = low
  log(f'  Flagged {low.sum()} unusually small roster(s) (column roster_count_low):')
  for _, row in df[low].iterrows():
    log(f'    {row.year} {row.team}: {row.roster_total_players} players')
  return df


def main():
  if len(sys.argv) < 2:
    sys.exit('Usage: python clean_nfl_data.py <input.csv>')
  out_dir = Path(__file__).resolve().parent

  df = load(sys.argv[1])
  validate_structure(df)
  df = clean_wins(df)
  df = normalize_spending(df)
  df = check_rosters(df)

  out_csv = out_dir / 'nfl_spending_clean.csv'
  df.to_csv(out_csv, index=False)
  log(f'\nSaved {len(df)} rows x {len(df.columns)} columns to {out_csv}')
  (out_dir / 'cleaning_log.txt').write_text('\n'.join(log_lines), encoding='utf-8')


if __name__ == '__main__':
  main()
