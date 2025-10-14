# ERA5 information

Two dataset are avalaible:
- arco-era5: Complete dataset offered by Google via cloud storage. Currently not maintained, for testing purposes
- era5: official AQUA ClimateDT ERA5 compact repo. it includes monthly data from 1940 to 2024 of a subselection of variables.

For monthly data the dafault format is netcdf. A `monthly-zarr` zarr source is also available, which may be considerably faster for some applications.

## How to update

ERA5 dataset is dowloaded from CDS making use of a simple tool python tool `CDS retriever`. 
It requires ECMWF api to be installed, please check the documentation: https://github.com/oloapinivad/CDS-retriever
The tool can be run in `update` mode so that when a new complete year is available, it can be retrieved in a single shot. 

Given that folder structure is slightly different than the one used automatically, a wrapper is prepared here `wrapper_cds.sh`: 
this basic tool will loop on the variable availalble, will launch the download and cat the files to create a new updated one
Manual removing of old files has to be done before finalizing the update. Please double check with attention what is done, and the proper folders since 
it is not a straightforward operation

Please check the property of the `CDS retriever` configuration file  and the path location. Original updated have been done on Levante DKRZ.

Always double check  timestamp of fluxes variables, since they might need to be aligned to 00:00:00 to avoid issue with xarray.  

## Conversion to zarr

A `nc2zarr` configuration file is avalable in the `scripts` subdirectory. Please refer to the AQUA documentation for instructions.

---------
Last updated by 
- Paolo Davini, CNR, Sep 2025
- Jost von Hardenberg, PoliTO, Oct 2025
