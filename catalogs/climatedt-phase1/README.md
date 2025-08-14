# ClimateDT Phase1 production catalog

This catalog contains the data for the ClimateDT Phase1 production.
The data are stored on Lumi HPC and on the Data Bridge (Lumi or MN5).
All the experiment are written on FDB.

Please be aware that not for all the experiment a detailed check wether the data are still on the Data Bridge or on Lumi HPC has been done.
If you encounter a possible issue, please open an issue in the Climate-DT-catalog repository.

The updated status of the Data Bridge transfer is available at the following link:
https://confluence.ecmwf.int/display/DDCZ/Data+portfolio+errata+for+Climate+DT+Phase+1
If you see that the data are not up to date with the website, please open an issue in the Climate-DT-catalog repository.

At the current stage only the Data Bridge on Lumi HPC is accessible with AQUA.
If you want to access locally the climatedt data, please remember to use the `engine='polytope'` argument in the Reader.

The 3 member ensembles for the IFS-FESOM storyline simulations (that cover the last 6 months of 2024) are available only on the HPC FDB and specific experiments name, such as `story-2017-T2K-ensemble`, `story-2017-control-ensemble`, and `story-2017-historical-ensemble`, are used to identify them.
In order to access a different realization member, you can use the `realization` kwarg in the Reader.