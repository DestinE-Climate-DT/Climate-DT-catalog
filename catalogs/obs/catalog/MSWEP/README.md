# MSWEP v3.16 information

Along with a new algorithm, MSWEP V3 incorporates new data sources, reduces drizzle overestimation, and minimizes peak underestimation compared to V2.
It is described by this paper: 10.48550/arXiv.2602.01436.

### Download data

For the v3 dataset download, a script named `download.sh` is provided in the `scripts` folder. It will download the data from the MSWEP Google Drive and store it a chosen location.
Time frequency and type of data (NRT or Past) can be selected while using the script. Please check the script for more details.

### Final note

According to the MSWEP team:

> We identified spurious precipitation trend artifacts in V3.15/V3.16 associ-
> ated with IMERG and GSMaP. Both datasets exhibit a systematic increase in precipitation from
> 2015 onward, likely related to the transition to GPM; as a result, MSWEP V3.15/V3.16 shows ar-
> tificially low precipitation during 2000–2015 relative to the preceding and subsequent periods.
> In the next MSWEP version, we will likely replace IMERG and GSMaP with CMORPH-CDR, which
> does not show this behavior. This issue affects both the uncorrected and gauge-corrected
> historical products (Past_nogauge and Past) of V3.15/V3.16. For users who require reliable
> trend estimates, we recommend using V2.80 for 1979–2021 until the issue is resolved

For this reason we leave download scripts, but we are still relying on the v2.8 dataset for AQUA.

# MSWEP v2.8 information

MSWEP is a global precipitation product with a 3‑hourly 0.1° resolution available from 1979 to ~3 hours from real-time. 
The product is unique in that it merges gauge, satellite, and reanalysis data to obtain the highest quality precipitation estimates at every location.

The currently available dataset is a merge of the MSWEP "Past" archive including gauge correction (197901-202011) plus
the "NRT" (near-real time) archive (202012-present). The two datasets are compatible and one is the continuation 
of the other. "monthly", "daily" and "3hourly" sources are currently available. 
In order to keep only full years as reference, the data currently extend only till 2024-12-31.

The default sources ("monthly", "daily", "3hourly") are in zarr format and a "monthly-netcdf" source in netcdf format is available.
The nectdf files are grouped on a yearly basis.

### Missing data

Since on 1979-0-01 the first three steps of the day were missing (0, 3 and 6), and this prevented the dataset to have the entire month of January in 1979, we reconstructed the missing day 1979-01-01 and cosequently the missing month 1979-01 by averaging the available data on 1979-01-01 (from 9 to 21) and afterward recomputing the monthly average. Units were fixed appropriately.

The reconstruction is documented in the script `scripts/reconstruct.sh`

Since the month of December of 2020 is missing from the 'Past' archive, these data were filled from the NRT dataset which starts in December 2020.

The NRT file `2023132.21.nc` is broken and was substituted with `2023132.18.nc`.

### NRT 3 hourly data

Starting in April 2020 the NRT data contain also two additional variables ("combination" and "cumulative_weight") so that precipitation needs to be selected to merge them with other dates. 

Another particularity is the fact that while the "Past" 3-hourly data are integer multiples of 0.0625 mm/3hr, the NRT data have full precision. For efficiency and to make them comaptible with the "Past" data, their precision is truncated to make them multiples of 0.0625.

### Rechunking

The original data have a chunking also in space which is not adequate for AQUA. All netcdf data (and zarr consequently) were preprocessed, rechunking them with the script `scripts/rechunk.sh`.
For monthly NRT data, needed for routine data extension, there is a dedicated script `scripts/rechunk_nrt_monthly.sh` which can be used to generate the rechunked files from the original NRT netcdf files and takes care also of setting the correct time axis.

### Validation of new data extension

In order to validate the new data extension, we suggest to create also years already available and to use the cdo command `cdo diff file_old.nc file_new.nc` to check that the new files are identical to the old ones.

### Zarr

Conversion to zarr can be achieved easily using the [nc2zarr utility](https://github.com/bcdev/nc2zarr) or similar tools.
We provide a sample configuration file for `nc2zarr`to be used as follows:

````
nc2zarr -vv -s name -c scripts/monthly.yaml
````

### How to update

The dataset is dowloaded from MSWEP from Google Drive using `rclone`.
It is necessary to contact the maintainers following the "Apply" link on [their web page](https://www.gloh2o.org/mswep/) to
get access to a GoogleDrive with the data.

The full commands are for example:
````
rclone sync -v  --drive-shared-with-me GoogleDrive:/MSWEP_V280/NRT/Monthly/ /YOURDIR/Past/monthly
rclone sync -v  --drive-shared-with-me GoogleDrive:/MSWEP_V280/Past/Monthly/ /YOURDIR/NRT/monthly
````
typically only the second one will be needed, since the "Past" archive does not change. Similarly for `Daily` and `3hourly` data.
You will then need to postprocess the data to generate the rechunked netcdf files as described above.
