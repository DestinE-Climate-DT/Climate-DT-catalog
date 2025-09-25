## MSWEP v2.8 information

MSWEP is a global precipitation product with a 3‑hourly 0.1° resolution available from 1979 to ~3 hours from real-time. The product is unique in that it merges gauge, satellite, and reanalysis data to obtain the highest quality precipitation estimates at every location.

The currently available dataset is:

- past-nrt: this is actually a merge of the MSWEP "Past" archive including gauge correction (197901-202011) plus
            the "NRT" (near-real time) archive (202012-present). The two datasets are compatible and one is the continuation 
            of the other. "monthly", "daily" and "3hourly" sources are currently available. In order to keep only full years as reference the data currently extend till 2024-12-31.


# How to update

The dataset is dowloaded from MSWEP from Google Drive using `rclone`.
It is necessary to contact the maintainers following the "Apply" link on [their web page](https://www.gloh2o.org/mswep/) to
get access to a GoogleDrive with the data.

The full commands (merging Past and NRT) are for example:
````
rclone sync -v  --drive-shared-with-me GoogleDrive:/MSWEP_V280/NRT/Monthly/ /pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/MSWEP/v2.8/netcdf/Past-NRT/monthly
rclone sync -v  --drive-shared-with-me GoogleDrive:/MSWEP_V280/Past/Monthly/ /pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/MSWEP/v2.8/netcdf/Past-NRT/monthly
````
typically only the sond one will be needed, since the "Past" archive does not change. Similarly for `Daily` and `3hourly` data.

Conversion to zarr can be achieved easily using the [nc2zarr utility](https://github.com/bcdev/nc2zarr) or similar tools.




