# The CERES datasets

CERES (Clouds and the Earth's Radiant Energy System, 
[https://ceres.larc.nasa.gov/](https://ceres.larc.nasa.gov/)) provides critical observations of 
Earth's radiation budget, measuring both solar-reflected and Earth-emitted radiation from the 
top of the atmosphere to the surface.

## Data Download

The datasets are available for download at: [https://ceres.larc.nasa.gov/Data/#](https://ceres.larc.nasa.gov/Data/#)

## AQUA Implementation

The AQUA team currently utilizes the following CERES datasets:

- **EBAF-Surface** (`ebaf-sfc421`): Energy Balanced and Filled surface radiation data,
  covering March 2000 to March 2026
- **EBAF-TOA** (`ebaf-toa421`): Energy Balanced and Filled Top-of-Atmosphere radiation data,
  covering March 2000 to May 2026

The two series end in different months on purpose: NASA releases EBAF-TOA ahead of
EBAF-Surface, so at any given time the Surface product lags by a couple of months.

The current implementation uses **version v4.2.1**, which is the most recent version available, 
although previous versions are also accessible.

### Other Available Datasets

**SYN1deg** ([https://ceres.larc.nasa.gov/documents/DQ_summaries/CERES_SYN1deg_Ed4A_DQS.pdf](https://ceres.larc.nasa.gov/documents/DQ_summaries/CERES_SYN1deg_Ed4A_DQS.pdf)): 
Synoptic radiative fluxes and clouds computed hourly on a 1-degree grid, combining CERES and 
geostationary satellite data. Our copy stops at the end of 2021 (1 January 2001 to
31 December 2021) and has not been extended since.

### Download Process

Due to the apparent absence of programmatic download options (e.g., `wget`), the AQUA team 
downloaded the data manually through the web interface. 

Given the 2GB maximum download limit, the EBAF-Surface data covering March 2000 to March 2026
was downloaded in two separate batches and subsequently merged using `cdo mergetime`. This
two-step process was only necessary for the Surface data, as the EBAF-TOA dataset for the
entire time period remained under the 2GB threshold.

---------
Last updated by Marco Cadau, Politecnico di Torino, Sep 2026