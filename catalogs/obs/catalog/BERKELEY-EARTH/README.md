## Berkeley Earth data

### Data Processing Overview

The `retrieve_process` function transforms raw Berkeley Earth 1x1 deg global land-ocean temperature data into a gap-filled, analysis-ready AQUA-compatible dataset. 

Berkeley Earth provides global temperature data as monthly anomalies relative to a climatological baseline, stored alongside monthly climatological averages. The processing pipeline first reconstructs absolute temperatures by adding these anomalies to their corresponding monthly climatology. Since the original time axis uses decimal years (e.g., 1850.042 for mid-January 1850), we convert this to standard monthly timestamps starting on the first of each month.

To focus on the modern climate period, the dataset is trimmed to include only data from 1979 onwards, which also reduces the issues with missing value. Finally, remaining data gaps are filled using CDO's fillmiss (based on bilinear interpolation) which estimates missing values from neighboring grid points.

The result is a complete monthly 1x1 deg temperature dataset spanning 1979 to present for surface temperature, suitable for climate analysis within AQUA without the complications of missing data or format inconsistencies.