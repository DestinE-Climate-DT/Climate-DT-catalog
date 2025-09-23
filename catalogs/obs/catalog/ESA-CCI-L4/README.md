## ESA-CCI-L4 information

Current AQUA supported dataset is v3.0.1.

Retrieved from CEDA archives https://data.ceda.ac.uk/neodc/eocis/data/global_and_regional/sea_surface_temperature/CDR_v3/Analysis/L4/v3.0.1. 
License can be found here: https://artefacts.ceda.ac.uk/licences/specific_licences/esacci_sst_terms_and_conditions_v2.pdf.

Only monthly average are available. For 2022-2023 the dataset is Interim. From 07/2024 no data is available.

Two sources are available:
- native-monthly: Spatial resolution is 0.05 deg. 
- r100-monthly: Spatial resolution is 1 deg, interpolated from native data with CDO remapcon 

# How to update

A nice AI-based script to retrieve and create the monthly average separated per variable is available in the folder `retrieve_esacci.py`
It is a bit of an overkill but should do everything required.