# The EN4 datasets

EN4 is a oceanic data set from the Met Office Hadley Centre. EN4 official documentation is 
available [here] (https://www.metoffice.gov.uk/hadobs/en4/EN.4.2.2_Product_User_Guide_v1.0.pdf)

Data are downloaded from the AQUA team from 1950 to 2024, and the AQUA ocean diagnostics set 
widely utilises the following variables on the analysis:

- Sea water salinity (`so`) and its uncertainty (`so_uncertainty`)
- Sea water potential temperature (`thetao`) and its uncertainty (`thetao_uncertainty`)

Variable names follow the CMOR standard.

The resulting netcdf data have been converted to a zarr store using nc2zarr and the configuration file `scripts/en4-monthly.yml`.
Both zarr (the dafault `monthly` source) and netcdf (`monthly-netcdf`) sources are available.

We provide a script, named `EN4_management.sh` in the `scripts` folder, where the data timeseries 
can be extended after 2024. The `bash` script is structured ad follows: 

### Script structure

The script performs the following operations:

1. **Grid configuration**: Uses `EN4_target_grid.txt` (located in the same directory) to regrid 
   new data to match existing data grid
2. **Data download**: Downloads annual ZIP files from Met Office for specified years
3. **Variable processing**: For each monthly file, extracts and processes `so` and `thetao` 
   (with uncertainties)
4. **Post-processing**: Renames variables, removes problematic attributes, converts time to float, 
   and applies regridding
5. **Temporal merge**: Combines monthly files into annual datasets
6. **Final merge**: Merges new data with existing historical data
7. **Data transfer**: Moves final files from working directory to the AQUA operational directory 
   on LUMI (`FINAL_DIR`)

### How to use

1. **Edit the script parameters**:
   ```bash
   START_YEAR=2025  # First year to download
   END_YEAR=2025    # Last year to download
   WORK_DIR="/users/cadaumar/en4_download"  # Working directory (adjust as needed)
   ```

2. **Run the script**:
   ```bash
   bash Climate-DT-catalog/catalogs/obs/catalog/EN4/scripts/EN4_management.sh
   ```

3. **Output files**: The script generates:
   - `so_EN4_YYYY_YYYY.nc` - New salinity data
   - `thetao_EN4_YYYY_YYYY.nc` - New temperature data
   - `so_EN4_complete_YYYYMMDD.nc` - Complete merged salinity dataset
   - `thetao_EN4_complete_YYYYMMDD.nc` - Complete merged temperature dataset

4. **Verify and backup** (IMPORTANT):
   - Check that new files are correct (use the coordinate comparison section in the script)
   - **Before replacing operational files**, create a backup:
     ```bash
     cd /pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/EN4
     mkdir -p backup
     cp so-1950_2024.nc backup/
     cp thetao-1950_2024.nc backup/
     ```
   - Rename the new complete files to match the operational naming scheme:
     ```bash
     mv so_EN4_complete_YYYYMMDD.nc so-1950_2025.nc  # Update end year
     mv thetao_EN4_complete_YYYYMMDD.nc thetao-1950_2025.nc
     ```

### Important notes

- **Complete years only**: The script processes only complete years (all 12 months must be 
available)
- **Automatic validation**: If any monthly file is missing, the entire year is skipped
- **Grid consistency**: New data is automatically regridded to match the existing grid
- **Uncertainties required**: Both main variables and their uncertainties must be present in 
source files
- **Two-stage processing**: Data is first downloaded and processed in `WORK_DIR`, then moved to 
`FINAL_DIR` only after successful processing
- **Always backup**: Create backups before replacing operational datasets

### Requirements

- `cdo` (Climate Data Operators)
- `nco` (NetCDF Operators: `ncatted`, `ncrename`, `ncap2`, `ncdump`)
- `wget`, `unzip`
- Sufficient disk space in working directory (~1GB per year)

---------
Last updated by 
- Marco Cadau, Politecnico di Torino, Oct 2025
- Jost von Hardenberg, PoliTO, Oct 2025
