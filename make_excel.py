"""Step 2: turn the cleaned CSV into a formatted Excel workbook.

Run clean_nfl_data.py first, then:
    python make_excel.py

Reads  nfl_spending_clean.csv and cleaning_log.txt (same folder)
Writes nfl_spending_clean.xlsx with three sheets:
  Clean Data    - one row per team-season; adjusted columns are live formulas
  Season Stats  - league mean / standard deviation per season (feeds the z-scores)
  Cleaning Log  - the checks from clean_nfl_data.py
"""

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import ColorScaleRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as col

HERE = Path(__file__).resolve().parent
POSITIONS = [
    'defensive_backs', 'linebackers', 'defensive_line', 'quarterback',
    'wide_receiver', 'running_back', 'tight_end', 'offensive_line',
]
LABELS = {
    'defensive_backs': 'Def. Backs', 'linebackers': 'Linebackers',
    'defensive_line': 'Def. Line', 'quarterback': 'Quarterback',
    'wide_receiver': 'Wide Rec.', 'running_back': 'Running Back',
    'tight_end': 'Tight End', 'offensive_line': 'Off. Line',
}

FONT = 'Arial'
HEADER_FILL = PatternFill('solid', fgColor='1F3864')
GROUP_FILLS = {
    'Team': '404040', 'Spending ($)': '2E5597', 'Wins': '548235',
    'Share of Team Spending': '7F6000', 'Z-score vs. Season Average': '843C0C',
    'Flags': 'C00000', 'Roster Counts': '595959',
}
BAND_FILL = PatternFill('solid', fgColor='F2F2F2')
FLAG_FILL = PatternFill('solid', fgColor='FFC7CE')
thin = Side(style='thin', color='BFBFBF')
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

DOLLARS = '$#,##0'
PCT = '0.0%'
Z = '0.00;-0.00;0.00'

FIRST, LAST = 3, None  # data rows on Clean Data (set in main)


def header_cell(cell, text, fill):
  cell.value = text
  cell.font = Font(name=FONT, bold=True, color='FFFFFF')
  cell.fill = PatternFill('solid', fgColor=fill)
  cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
  cell.border = BORDER


def build_clean_data(wb, df):
  ws = wb.active
  ws.title = 'Clean Data'
  n = len(df)
  last = FIRST + n - 1
  rng = lambda c: f'${c}${FIRST}:${c}${last}'

  # Column plan: (group, header, key, number format, width)
  columns = [('Team', 'Year', 'year', '0', 7), ('Team', 'Team', 'team', '@', 24)]
  columns += [('Spending ($)', LABELS[p], p, DOLLARS, 13) for p in POSITIONS]
  columns += [('Spending ($)', 'Total (8 groups)', 'total_amount_spent', DOLLARS, 14)]
  columns += [('Wins', 'Wins', 'total_wins', '0', 7),
              ('Wins', 'Games', 'games_played', '0', 7),
              ('Wins', 'Win %', 'win_pct', PCT, 8)]
  columns += [('Share of Team Spending', LABELS[p], f'{p}_share', PCT, 10) for p in POSITIONS]
  columns += [('Z-score vs. Season Average', LABELS[p], f'{p}_z', Z, 10) for p in POSITIONS]
  columns += [('Z-score vs. Season Average', 'Total', 'total_spent_z', Z, 10)]
  columns += [('Flags', 'Extreme Spend', 'has_extreme_spend', '@', 10),
              ('Flags', 'Low Roster Count', 'roster_count_low', '@', 10)]
  columns += [('Roster Counts', 'All Players', 'roster_total_players', '0', 9)]
  columns += [('Roster Counts', LABELS[p], f'roster_{p}_count', '0', 9) for p in POSITIONS]
  letter = {key: col(i + 1) for i, (_, _, key, _, _) in enumerate(columns)}

  # Row 1: group bands, row 2: column headers
  start = 1
  for i, (group, *_rest) in enumerate(columns + [(None,)], start=1):
    if i > len(columns) or group != columns[start - 1][0]:
      g = columns[start - 1][0]
      ws.merge_cells(start_row=1, start_column=start, end_row=1, end_column=i - 1)
      header_cell(ws.cell(1, start), g, GROUP_FILLS[g])
      start = i
  for i, (group, head, key, fmt, width) in enumerate(columns, start=1):
    header_cell(ws.cell(2, i), head, GROUP_FILLS[group])
    ws.column_dimensions[col(i)].width = width
  ws.row_dimensions[2].height = 30

  stats_rows = "'Season Stats'!$A$4:$A$13"
  for r, rec in enumerate(df.itertuples(index=False), start=FIRST):
    rec = rec._asdict()
    L = letter
    formulas = {
        # Total is the sum of the 8 position groups.
        'total_amount_spent': f'=SUM({L["defensive_backs"]}{r}:{L["offensive_line"]}{r})',
        'win_pct': f'={L["total_wins"]}{r}/{L["games_played"]}{r}',
    }
    for i, p in enumerate(POSITIONS + ['total_amount_spent']):
      mean_c, sd_c = col(2 + 2 * i), col(3 + 2 * i)
      key = 'total_spent_z' if p == 'total_amount_spent' else f'{p}_z'
      formulas[key] = (
          f'=({L[p]}{r}-INDEX(\'Season Stats\'!${mean_c}$4:${mean_c}$13,'
          f'MATCH($A{r},{stats_rows},0)))'
          f'/INDEX(\'Season Stats\'!${sd_c}$4:${sd_c}$13,MATCH($A{r},{stats_rows},0))'
      )
      if p != 'total_amount_spent':
        formulas[f'{p}_share'] = f'={L[p]}{r}/{L["total_amount_spent"]}{r}'
    z_refs = ','.join(f'ABS({L[p + "_z"]}{r})>3' for p in POSITIONS)
    formulas['has_extreme_spend'] = f'=OR({z_refs})'
    formulas['roster_count_low'] = (
        f"={L['roster_total_players']}{r}<'Season Stats'!$C$17")

    for i, (_, _, key, fmt, _) in enumerate(columns, start=1):
      cell = ws.cell(r, i, formulas.get(key, rec[key]))
      cell.number_format = fmt
      cell.font = Font(name=FONT, color='000000' if key in formulas else '0000FF')
      cell.border = BORDER
      if key in ('has_extreme_spend', 'roster_count_low'):
        cell.alignment = Alignment(horizontal='center')

  data = f'A{FIRST}:{col(len(columns))}{last}'
  # Light banding on every other row
  ws.conditional_formatting.add(
      data, FormulaRule(formula=[f'MOD(ROW(),2)=0'], fill=BAND_FILL))
  # Red-white-green scale on z-scores, red fill on TRUE flags
  z_first, z_last = letter['defensive_backs_z'], letter['total_spent_z']
  ws.conditional_formatting.add(
      f'{z_first}{FIRST}:{z_last}{last}',
      ColorScaleRule(start_type='num', start_value=-3, start_color='F8696B',
                     mid_type='num', mid_value=0, mid_color='FFFFFF',
                     end_type='num', end_value=3, end_color='63BE7B'))
  ws.conditional_formatting.add(
      f'{letter["win_pct"]}{FIRST}:{letter["win_pct"]}{last}',
      ColorScaleRule(start_type='num', start_value=0, start_color='F8696B',
                     mid_type='num', mid_value=0.5, mid_color='FFFFFF',
                     end_type='num', end_value=1, end_color='63BE7B'))
  for key in ('has_extreme_spend', 'roster_count_low'):
    c = letter[key]
    ws.conditional_formatting.add(
        f'{c}{FIRST}:{c}{last}',
        FormulaRule(formula=[f'{c}{FIRST}=TRUE'], fill=FLAG_FILL, stopIfTrue=True))

  ws.freeze_panes = f'C{FIRST}'
  ws.auto_filter.ref = f'A2:{col(len(columns))}{last}'

  notes = {
      'total_amount_spent': 'Sum of the 8 position groups. Leaves out kickers, '
                            'punters, long snappers and fullbacks.',
      'games_played': '16 games through 2020, 17 from 2021. Buffalo and '
                      'Cincinnati played 16 in 2022 (cancelled game).',
      'win_pct': 'Wins / Games. Ties count as losses because the scraper did '
                 'not save ties (10 tied games across the decade).',
      'has_extreme_spend': 'TRUE when any position is more than 3 standard '
                           'deviations from its season average. Kept, not removed.',
      'roster_count_low': "TRUE when All Players is below the IQR cutoff on "
                          "'Season Stats'. All 5 flagged rows are from 2016.",
  }
  for key, text in notes.items():
    ws[f'{letter[key]}2'].comment = Comment(text, 'Cleaning notes')
  return letter, last


def build_season_stats(wb, years, letter, last):
  ws = wb.create_sheet('Season Stats')
  ws['A1'] = 'League average and standard deviation by season'
  ws['A1'].font = Font(name=FONT, bold=True, size=13)
  ws['A2'] = ('Used by the z-score columns on Clean Data: '
              'z = (team value - season mean) / season SD')
  ws['A2'].font = Font(name=FONT, italic=True, color='595959')

  header_cell(ws.cell(3, 1), 'Year', '404040')
  ws.column_dimensions['A'].width = 8
  cd = "'Clean Data'!"
  year_rng = f'{cd}$A$3:$A${last}'
  for i, p in enumerate(POSITIONS + ['total_amount_spent']):
    m, s = 2 + 2 * i, 3 + 2 * i
    name = LABELS.get(p, 'Total')
    header_cell(ws.cell(3, m), f'{name}\nMean', '2E5597')
    header_cell(ws.cell(3, s), f'{name}\nSD', '2E5597')
    ws.column_dimensions[col(m)].width = 13
    ws.column_dimensions[col(s)].width = 13
    src = f'{cd}${letter[p]}$3:${letter[p]}${last}'
    for r, y in enumerate(years, start=4):
      mean = ws.cell(r, m, f'=AVERAGEIFS({src},{year_rng},$A{r})')
      ws.cell(r, s, f'=SQRT(SUMPRODUCT(({year_rng}=$A{r})*({src}-{col(m)}{r})^2)'
                    f'/(COUNTIF({year_rng},$A{r})-1))')
  # Wins sanity check columns
  wcol = 2 + 2 * 9
  wins_rng = f'{cd}${letter["total_wins"]}$3:${letter["total_wins"]}${last}'
  games_rng = f'{cd}${letter["games_played"]}$3:${letter["games_played"]}${last}'
  for j, (head, f) in enumerate([
      ('Teams', f'=COUNTIF({year_rng},$A{{r}})'),
      ('League Wins', f'=SUMIFS({wins_rng},{year_rng},$A{{r}})'),
      ('Games Played', f'=SUMIFS({games_rng},{year_rng},$A{{r}})/2'),
      ('Implied Ties', f'={col(wcol + 2)}{{r}}-{col(wcol + 1)}{{r}}'),
  ]):
    c = wcol + j
    header_cell(ws.cell(3, c), head, '548235')
    ws.column_dimensions[col(c)].width = 11
    for r in range(4, 4 + len(years)):
      ws.cell(r, c, f.format(r=r))
  ws.cell(3, wcol + 3).comment = Comment(
      'Every game produces one win unless it ends in a tie, so '
      'games - wins = number of tied games.', 'Cleaning notes')

  for r, y in enumerate(years, start=4):
    ws.cell(r, 1, y).font = Font(name=FONT, bold=True, color='0000FF')
    for c in range(2, wcol + 4):
      cell = ws.cell(r, c)
      cell.font = Font(name=FONT)
      cell.number_format = DOLLARS if c < wcol else '0'
    for c in range(1, wcol + 4):
      ws.cell(r, c).border = BORDER
      if r % 2 == 0:
        ws.cell(r, c).fill = BAND_FILL
  ws.row_dimensions[3].height = 30

  # Roster-count cutoff (Tukey rule: Q1 - 1.5 * IQR)
  roster = f'{cd}${letter["roster_total_players"]}$3:${letter["roster_total_players"]}${last}'
  ws['A15'] = 'Roster count cutoff'
  ws['A15'].font = Font(name=FONT, bold=True, size=12)
  for r, (label, f) in enumerate([
      ('Q1 (25th percentile)', f'=QUARTILE({roster},1)'),
      ('Low cutoff = Q1 - 1.5 x IQR', f'=C16-1.5*(QUARTILE({roster},3)-C16)'),
  ], start=16):
    ws.cell(r, 1, label).font = Font(name=FONT)
    cell = ws.cell(r, 3, f)
    cell.font = Font(name=FONT, bold=True)
    cell.number_format = '0.0'
  ws.freeze_panes = 'B4'


def build_log(wb):
  ws = wb.create_sheet('Cleaning Log')
  ws.column_dimensions['A'].width = 120
  header_cell(ws['A1'], 'Checks run by clean_nfl_data.py', '1F3864')
  ws['A1'].alignment = Alignment(horizontal='left')
  lines = (HERE / 'cleaning_log.txt').read_text(encoding='utf-8').splitlines()
  for r, line in enumerate(lines, start=2):
    cell = ws.cell(r, 1, line)
    bold = line[:2].strip().rstrip('.').isdigit()
    color = ('006100' if '[PASS]' in line else
             'C00000' if '[FAIL]' in line else '000000')
    cell.font = Font(name=FONT, bold=bold, color=color)


def main():
  df = pd.read_csv(HERE / 'nfl_spending_clean.csv')
  df = df.sort_values(['year', 'team']).reset_index(drop=True)
  wb = Workbook()
  letter, last = build_clean_data(wb, df)
  build_season_stats(wb, sorted(df['year'].unique()), letter, last)
  build_log(wb)
  wb.calculation.fullCalcOnLoad = True
  out = HERE / 'nfl_spending_clean.xlsx'
  wb.save(out)
  print(f'Saved {out}')


if __name__ == '__main__':
  main()
