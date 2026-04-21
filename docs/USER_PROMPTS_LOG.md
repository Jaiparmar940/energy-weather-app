# User prompts log (this Cursor chat session)

Session context: **energy-weather-app** — correlations export, UI, README, data paths, git.

---

Introduction and Research:
Topic Introduction:
Historically, regional energy consumption has been heavily correlated with weather patterns. Grid demand fluctuated with the seasons, with both summer and winter having higher average energy consumption due to heating and cooling demands. However, with the rapid development of AI and its accompanying data centers, we expect to see a drastic change in energy consumption in data center heavy regions due to the intensive energy requirements for these data centers. 

Research Questions:
In light of these expected changes, our project aims to investigate the following research questions:
To what extent has the correlation between weather patterns and grid demand shifted in regions with high data center growth?
How does the accuracy of energy usage prediction models differ between data center heavy regions and non data center heavy regions?
These research questions are substantial because they attempt to answer a question that has not already been definitively answered given how recent and ongoing this change in data center activity as it relates to energy usage is. Both will require work beyond surface-level analysis, as we would be analyzing both the relationship that energy has with weather patterns and with data center usage, and further analyzing what the difference between the two means in each question. 

Additionally, they are feasible questions due to the fact that we already have a dataset in mind that we can use for each question, and the analysis we are doing can be as deep and as unique as we would like it to be, but even if we hit 60% of the depth of analysis that we could possibly go to, we’d still reach a sufficient answer for this project. 

Lastly, they are both definitely relevant questions, as the topic of data centers as it relates to energy usage is one of extreme importance right now for various reasons, namely its sustainability, and understanding this relationship in comparison to an existing energy fluctuation that is in our current system would be both interesting and helpful as context to the sustainability issue. 
Data Sources:
EIA Open Data (https://www.eia.gov/opendata/)
The EIA (Energy Information Administration) is a governmental organization that provides independent statistics and analysis on energy sources and activity within the United States. They maintain a large database of energy-related information which can be easily accessed using an API key. Any member of the public can request an API key and pull data free of charge.

We intend on solely focusing on the demand (load) dataset. This dataset provides real time and historical hourly information on the load of each major ISO (Independent Service Operator) relative to their capacity. Combining this with weather information allows us to see how weather information influences loads in ISOs with high and low datacenter quantities. This allows us to investigate the first posed research question.

We have successfully been able to request an API key and pull nearly 1 million rows of hourly usage information across 8 major ISOs using a simple python script.

NOAA Weather Data - (https://www.weather.gov/documentation/services-web-api) 
NOAA (National Oceanic and Atmospheric Administration) is a government agency that focuses on the conditions of the oceans, major waterways, and the atmosphere, including forecasting weather, monitoring climate, and managing marine resources. They provide comprehensive information about weather events within the United States and offer an easily accessible database for the public.

We are focusing entirely on the NOAA NCEI Integrated Surface Database (ISD). This dataset provides a long history, hourly station observations (great for load price models) and lots of useful fields such as temp, dew point, wind, pressure, cloud, visibility, precipitation. We would use it by mapping each node/zone to the nearest station(s) (or a weighted blend) and engineer features like Cooling/Heating Degree Hours, humidity/heat index, wind chill, and storm proxies. This dataset is very useful to our project because it provides all significant weather related information at a given location with vast historical information, allowing us to gauge the relationship between weather events and usage (and how it has changed over time).

The government provides this data free of charge and makes it very easy to access with a simple process in requesting an API key which is open to all. Using a python script, we have been able to pull over 100,000 rows of hourly weather data for the major ISOs in the United States. We therefore should not run into any problems when it comes to getting data for a specific location. 

PJM Interconnection - Dataminer (https://dataminer2.pjm.com/)
The PJM dataminer is a comprehensive ISO database containing usage, pricing, projection, and generation information about the grid in the PJM (Northeast) ISO region. We focus on PJM particularly because it is the region with the highest concentration of databases in the US and therefore has the highest likelihood of curtailment due to non-weather related signals. This resource supplements the usage data provided by the EIA, however it provides a much greater level of detail. The EIA only provides 1 hour usage history and day ahead projected prices, while this database produces 5 minute real time pricing and load information. Additionally, the EIA only contains overall usage across the entire ISOs, while Dataminer gives us pricing information (known as LMPs or Locational Marginal Pricing) down to the node (think substation, hospitals, major database, or small power delivery location). 

For the analysis pipeline we actually use **PJM day-ahead full-system LMP** (parquet: nodal `total_lmp_da` by `pnode_id` and timestamp), **cleaned yearly load-forecast** parquets for system/subregional load, and **exported node metadata** (zones, coordinates). DA LMP gives a nodal price series we can align to weather; load remains forecast/coarser than a single bus, so node-level “DC-heavy vs not” comparisons lean on LMP. **Real-time 5-minute LMP, instantaneous real-time load, and generation by fuel type are not used** in the current preprocessing scripts.

Accessing the database requires approval from PJM which was successfully requested, however, the site does not use a traditional API key. We have instead written a script which emulates the request made to display the pricing/load information shown on the web browser by making the same request via cURL. We have been able to successfully obtain over 2 million rows of data by making these requests via a simple python script, which times the requests to deliberately respect the usage limits. 


data from PJM has already been pulled for around 6 years and can be accessed here: "C:\Users\Jaipa\OneDrive\Desktop\GridIntelligence-1\Data". weather data will need to be sourced from NOAA and EIA data will also need to pulled (we can skip this if PJM data is sufficient)

Lets make a react webapp which investigates tis hypothesis and shows comprehensive data to explore the tested relationship and how it may have evolved over time

2. explore the data in C:\Users\Jaipa\OneDrive\Desktop\GridIntelligence-1\Data to understand what data we currently have, integrate that data into this project, and write script to pull whatever data is still needed

3. the graph for top absolute correlations lists the same correlation value across all nodes tested. lets add the node ID to the table and the graph info that shows up when we hover over a segment

4. rescale the graph to fit better

5. can we make the graph customizable such that we can select what nodes and what variables we want to test the correlations of (select all that apply)

6. Above filters write a short dictionary that explains what each variable represents

7. make the formatting of the definitions more visually appealing

8. get rid of header text: Exploring how the relationship between weather and grid demand/pricing has evolved in data-center-heavy versus non–data-center-heavy regions.

9. why is the y axis of the correlation plot listing node ID instead of correlation values

10. lets start with the time aspect. sure we can see correlations but we arent seeing how that correlation shifts over time. we need to add a feature that does that to this app

11. are we able to identify which of the nodes we have data for are data center heavy regions? also make the table with the node correlations for all tested odes collpasable showing only a few entries and collapsing tghe rest

12. move the correlations over time section above the collapsable list of correlations. for both, apply the top filter for nodes and variables to reduce amount of data displayed. instead of specifying on the node in the filter if it is dc heavy, make that a seperate filter

13. write a single script that can (while updating status on its progress) pull all of the missing weather data that this project requires from the year range trhatg we have energy data for

14. add another filter for the year range. add a section which does a quantitiative analysis of the correlation change over time

15. lets try a different metric for the quantitative change. the goal is to see if weather is becoming a more or less useful indicator of usage or price at a node

16. put Largest decreases in |correlation| below the largest increase instead of side by side

17. both folder still exist. because the data is too large, i would upload it to something like box so that my team can download it and easily insert it into their folders, however, having two folders of the same name complicates things.

18. we had the data, then when i said the line below it wont load into the app, there should be no reason to redo the correlations or pull the data agin: 

so we have two data folders, one in public and one in the app itself. im guessing we excluded both. can we not consolidate this?

19. we need a combination of non dc heavy and dc heavy. update the script accordingly and give the command

20. The current script to produce correlations to display in the correlations page does not produce correlations for non data center heavy nodes despite setting the ratio to 0.5.

21. The models tab used to have data, what happend to it.

22. Did this command … and ran sync after each time i did for every year, but for some reason, only the latest correlation calculation year displays in the correlations page.  
   *(Referenced terminal command: `python scripts\build_analysis_exports.py` with `--year`, `--balanced-dc`, `--dc-ratio 0.5`, etc.)*

23. Give the full updated command.

24. Can we make the regions loaded more clean (maybe collapsable list).

25. When hovering over the graph for correlations over time, the text from the legend of the graph overlays the window that gives the correlation values.

26. Push and commit.

27. Update the readme to describe how to get the data file and sync, which is located in box here: [Duke Box link]. Commit and push.

28. Will this still work without the info in `C:\Users\Jaipa\OneDrive\Desktop\GridIntelligence-1\Data`.

29. So there is data from that folder that is being referenced? If so, can we copy that to the data folder here and remove the hardcoded link?

30. Copy the needed data now.

31. I don’t want to have to include all of the PJM files. Since we have already computed the correlations, do they really need that info to make the app work if it can only reference the stuff in the data folder?

32. So let’s update the readme accordingly and state that it is necessary to pull data from PJM to recompute correlations and we are using precomputed correlations to avoid excessive data uploads.

33. I don’t want there to be any mention of gridintelligence-1. Let’s instead make a subfolder called pjm data and have the computed correlations reference that within the local data folder.

34. So what files are needed to make the app work without downloading any other data? Are they small enough that we can just commit them?

35. Make the update, then update the readme to explain how to get all of the data (they need to download the data folder from the box link and replace it in the local directory) commit and push.

36. Generate a log for all of the prompts I wrote here.

---

RQ2 implementation update (weather-heavy model comparison):

- Added `scripts/train_rq2_models.py` to train/evaluate 6 models (LinearRegression, Ridge, Lasso, RandomForest, GradientBoosting, ExtraTrees).
- Uses weather-heavy features (`temp_c`, `dew_c`, `rh_pct`, `wind_ms`, `slp_hpa`, `precip_mm`, `cdh`, `hdh`) with time features and compares:
  - `weatherOnly`
  - `weatherPlusDc`
- Runs dual targets:
  - `lmp` (`total_lmp_da`)
  - `load` (`forecast_load_mw`)
- Writes app-ready metrics to `data/exports/model_performance.json` with bucket labels `dc` and `nonDc`, plus `modelName`, `nSamples`, and `split`.
- Regeneration command used:
  - `python scripts/train_rq2_models.py --years 2023 2024 --limit-nodes 4 --balanced-dc --dc-ratio 0.5 --max-da-files-per-year 6 --test-start-year 2024`
  - `npm run sync:data`
- Result summary from current export:
  - 84 metric rows
  - targets: `lmp`, `load`
  - buckets: `dc`, `nonDc`
  - model names: 6

PJM node categorization revision (new technique):

- Replaced prior zone-based assumption with explainable scoring system in `scripts/dc_region_scoring.py`.
- Added configurable PJM regions by tier with county/city fuzzy matching + centroid/radius logic:
  - Tier 1: Northern Virginia (DOM / Ashburn area)
  - Tier 2: PPL Susquehanna/Berwick, AEP Columbus, COMED Chicago suburbs
  - Tier 3: Indiana footprint and Western PA/WV clusters
- New output fields per node:
  - `dataCenterLikelihoodScore`
  - `confidenceScore`
  - `classificationLabel` (`high_likelihood` / `medium_likelihood` / `low_likelihood`)
  - `reasonCodes`
  - `matchedRegion`
  - `intermediateFeatures`
- Export script now writes `data/exports/node_dc_scoring_debug.json` for auditable debugging.
- Correlation bucketing now uses score-driven labels (`high`/`medium` -> `dc`, else `nonDc`) instead of static zone assumptions.
- Models retrained using new categories and exported to `data/exports/model_performance.json`.
- Correlations UI filter updated to support likelihood label filtering in addition to DC/non-DC.
