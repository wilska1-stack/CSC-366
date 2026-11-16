# Does Money Win Games? Positional Spending vs. Success Across the NFL (2016-2025)

## Research Question
Which positional groups does NFL spending affect most when it comes to winning? For example, does a team that spends heavily on quarterbacks or the offensive line win more over time than a team that spends heavily on the defensive backs?

Teams work under a salary cap and have to decide where to put limited money. If some positions show a stronger link between spending and wins, those positions give teams the best return. If spending barely correlates with wins, that tells us something too: how much a team spends matters less than how it spends it.

## Data Sources
| Source | What it gives us |
|---|---|
| [Over the Cap](https://overthecap.com/positional-spending) | Cap spending for all 32 teams each season, by position group |
| [ESPN NFL API](https://site.api.espn.com/apis/v2/sports/football/nfl/standings) | Regular-season win totals for each team and season |
| [nflverse](https://github.com/nflverse/nflverse-data) | Player rosters, used for roster counts by position group |

The proposal planned to use Spotrac for spending. The scraper uses Over the Cap instead, which publishes the same position-group breakdown for every season.

## Data Structure
One row per team per season: 32 teams x 10 seasons (2016-2025) = 320 rows. Each row has:

- Spending in US dollars on 8 position groups: defensive backs, linebackers, defensive line, quarterback, wide receiver, running back, tight end, offensive line
- Total amount spent (the sum of the 8 groups)
- Total wins
- Roster counts by position group

## Files
| File | What it is |
|---|---|
| `scrape_nfl_data.py` | Scraper that collects the data from the three sources |
| `nfl_positional_spending_2016_2025.csv` | Raw data produced by the scraper |
| `clean_nfl_data.py` | Cleaning step 1: validates the data and adds adjusted columns |
| `nfl_spending_clean.csv` | Cleaned data |
| `cleaning_log.txt` | Every check the cleaning script ran and what it found |
| `make_excel.py` | Cleaning step 2: builds the formatted Excel workbook |
| `nfl_spending_clean.xlsx` | Cleaned data as a formatted Excel workbook |

## Cleaning Summary
- No missing values, no duplicate rows, and all 32 teams in every season.
- **Win %** (`win_pct`) puts 16-game seasons (through 2020) and 17-game seasons (2021 on) on the same scale.
- **Spending share** (`<position>_share`) and **z-score within the season** (`<position>_z`) adjust for spending growing about 70% over the decade.
- Unusually large spending is **flagged, not removed** (`has_extreme_spend`), because those big contracts are what the project studies.
- Unusually small 2016 roster counts are flagged (`roster_count_low`).

## How to Run
```
python scrape_nfl_data.py
python clean_nfl_data.py nfl_positional_spending_2016_2025.csv
python make_excel.py
```
Requires `pandas`, `requests` and `openpyxl`.
