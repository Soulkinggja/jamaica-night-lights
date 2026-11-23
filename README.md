# Jamaica night lights recovery tracker

How fast each parish got its lights back after Hurricane Melissa (landfall 28 October 2025),
measured from NASA Black Marble satellite images of Jamaica at night.

**Live app: https://jamaica-night-lights.streamlit.app**

## What it measures

* Each parish's night light, every day from September 2025 to February 2026, as a share of
  its normal level before the storm (its median from 1 September to 26 October 2025).
* Days until each parish was back to 80% and 90% of normal, and the total light lost.
* How light loss lines up with the World Bank's estimate of damage by parish.

## Data

| Series | Source |
|---|---|
| Daily night lights, 500 m, moonlight and atmosphere corrected, cloud gaps filled | NASA Black Marble VNP46A2 |
| Monthly night lights composite | NASA Black Marble VNP46A3 |
| Parish boundaries | geoBoundaries, CC BY 4.0 |
| Damage by parish | World Bank GRADE rapid damage estimate, Hurricane Melissa |

## How it runs

NASA's files need an Earthdata login, so the pipeline runs in GitHub Actions with a NASA token
stored as the repository secret `NASA_TOKEN`:

1. `src/fetch.py` downloads the tiles with [blackmarblepy](https://github.com/worldbank/blackmarblepy)
   and sums light over each parish with exactextract.
2. `src/analysis.py` builds the recovery measures in `data/processed/`.
3. The workflow commits the results, and the Streamlit app reads them.

The workflow runs on the 3rd of each month and can be started by hand from the Actions tab.

## Limits

* Gap filling carries light from the last clear night into cloudy ones, so short dips can be
  understated.
* Night light measures power and activity, not damage to homes. Generators and solar can light
  an area before the grid is back.

## Related

* [Jamaica remittances tracker](https://github.com/Soulkinggja/jamaica-remittances) and the working
  paper [Diaspora as Insurance](https://doi.org/10.5281/zenodo.24473011), which found remittances
  reached the hardest hit parishes late.

Built by Devin McIntosh.
