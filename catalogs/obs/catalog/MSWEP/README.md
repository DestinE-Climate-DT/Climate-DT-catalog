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

### Rechunking

The original data have a chunking also in space which is not adequate for AQUA. All netcdf data (and zarr consequently) were preprocessed, rechunking them with the script `scripts/rechunk.sh`.


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





