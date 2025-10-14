## AVISO SSH data

This includes CNES AVISO dataset for sea surface height, currently developed by Copernicus Marine Environment Monitoring Service (CMEMS)

Sea level anomaly is defined as the height of water over the mean sea surface in a given time and region. In this dataset sea level anomalies are computed with respect to a twenty-year mean reference period (1993-2012) using up-to-date altimeter standard

Two version are availalbe:
- vDT2024: Regularly updated; based on 2024 version of Level-2 input data (currently supported by AQUA)
- vDT2021: No longer updated; based on 2021 version of Level-2 input data (old AQUA version, now deprecated)

## Download and processing

Data can be downloaded from the Copernicus webpage, using the CDS API https://cds.climate.copernicus.eu/datasets/satellite-sea-level-global?tab=overview, currently available up to 2023. More recent data can be downloaded directly from CMEMS https://data.marine.copernicus.eu/product/SEALEVEL_GLO_PHY_CLIMATE_L4_MY_008_057/description

Data is provided in daily netcdf files, and to optimize data access this has been postprocessed in zarr file with `nc2zarr` with monthly time chunks. 