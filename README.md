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
| `analysis_simple.ipynb` | Notebook with the cleaning, summary statistics and analysis |
| `analysis_simple.pdf` | The report: the notebook's code, results and findings as a PDF |

## Cleaning Summary
- No missing values, no duplicate rows, and all 32 teams in every season.
- **Win %** (`win_pct`) puts 16-game seasons (through 2020) and 17-game seasons (2021 on) on the same scale.
- **Spending share** (`<position>_share`) and **z-score within the season** (`<position>_z`) adjust for spending growing about 70% over the decade.
- Unusually large spending is **flagged, not removed** (`has_extreme_spend`), because those big contracts are what the project studies.
- Unusually small 2016 roster counts are flagged (`roster_count_low`).

## Results
The full report with code and charts is in `analysis_simple.pdf`. In short:

**Where the money goes.** On average, teams spend the most on the defensive line (23% of spending on the 8 position groups), the offensive line (20%) and defensive backs (17%). They spend the least on tight ends and running backs (5% each). The average win % is 49.8%, ranging from 0% to 88%.

**Does spending more go with winning more?** Yes, but only a little. Teams that spend more than other teams that season tend to win more. The correlation is r = 0.26, a weak positive relationship, and the results are widely scattered.

**Which positions matter most?** Every position's spending has a weak relationship with winning, and all of them are weaker than total spending.

| Position | Correlation with win % (r) | p-value |
|---|---|---|
| Tight end | 0.124 | 0.026 |
| Quarterback | 0.113 | 0.043 |
| Defensive line | 0.108 | 0.054 |
| Defensive backs | 0.082 | 0.141 |
| Wide receiver | 0.057 | 0.312 |
| Offensive line | 0.044 | 0.431 |
| Running back | 0.011 | 0.839 |
| Linebackers | 0.008 | 0.886 |

Only tight end and quarterback spending are statistically significant (p < 0.05). Defensive line spending just misses.

### Findings
1. **Spending more overall helps a little** (r = 0.26).
2. **No single position buys wins.** Quarterback and tight end spending have the strongest links to winning, but even those are weak (r ≈ 0.11-0.12).
3. **The rest comes from things money doesn't measure**, such as coaching, drafting and luck.

**Why it matters:** with a hard salary cap, teams constantly debate where to spend. This data suggests that where the money goes matters less than spending it on good players.

### Limitations
- Correlation is not causation: good teams often pay their players *because* they won.
- Stars on cheap rookie contracts make some great teams look like low spenders.
- Ties count as losses in win %, because the data didn't include ties (10 games across the ten seasons).

## How to Run
```
python scrape_nfl_data.py
python clean_nfl_data.py nfl_positional_spending_2016_2025.csv
python make_excel.py
```
Requires `pandas`, `requests` and `openpyxl`.
