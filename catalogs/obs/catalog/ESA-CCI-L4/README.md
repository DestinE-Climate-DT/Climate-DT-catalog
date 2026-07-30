## ESA-CCI-L4 information

Current AQUA supported dataset is v3.0.1.

Data are available from CDS at https://cds.climate.copernicus.eu/datasets/satellite-sea-surface-temperature?tab=download by fecthing the combined product L4. 

This covers regularly updated data from CDS which extend the CEDA archives which was available until 2024-07.

License can be found here: https://artefacts.ceda.ac.uk/licences/specific_licences/esacci_sst_terms_and_conditions_v2.pdf.

Only monthly average are available in aqua.

Two sources are available:
- native-monthly: Spatial resolution is 0.05 deg. 
- r100-monthly: Spatial resolution is 1 deg, interpolated from native data with CDO remapcon 

# How to update

> Please note that the script uses an old folder structure and some rearrangament might be required if you want to download the data again

A nice AI-based script to retrieve and create the monthly average separated per variable is available in the folder `retrieve_c3s.py`, which superseed an older script used to download the data from CEDA directly. 
It is a bit of an overkill but should do everything required.