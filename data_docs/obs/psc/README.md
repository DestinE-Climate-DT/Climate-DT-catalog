This readme document is an informal log of the steps and procedures followed to download and process the data.

# PSC - PIOMAS and GIOMAS (Global Ice-Ocean Modeling and Assimilation System)

GIOMAS Global Sea Ice Data [page LINK](https://psc.apl.washington.edu/zhang/Global_seaice/data.html).

## Download Data - GIOMAS:

On LUMI directory: `/pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/PSC/`

I created: `new/GIOMAS/heff`, then tried to connect with different methods, one that worked well is `sftp`.

### Connect with `sftp`

To connect type: `sftp anonymous@pscfiles.apl.washington.edu`

then use as password: `anonymous`

then `cd ./pscfiles/zhang/Global_seaice`, in this dir you can find many files such as:

```bash
heff.H1985.nc.gz  
heff.H1985.gz
... Multiple years covering from heff.H1979 to heff.H2024
```

- To set the dir where to download the data:

```bash
lpwd
Local working directory: /pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/PSC/new/GIOMAS/heff

sftp> lcd /pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/PSC/new/GIOMAS/heff
```

- To download the data:

```bash
sftp> mget heff.H*.gz
```

This will download both the `.nc` and *binary* versions.
Similar case for `area`:

```bash
sftp> mget area.H*.gz
```

For completeness, it is better to download also the following grids:

```bash
/pscfiles/zhang/Global_seaice/grid.dat  
/pscfiles/zhang/Global_seaice/grid.dat.pop  
/pscfiles/zhang/Global_seaice/io.dat_360_276.output  
```

still using `mget` for this:

```bash
mget grid*
mget io.dat_*
```

It is suggested to double check the content of the grids.

[Note]:  
Since the data are in ASCII format, another solution to get the data is to copy/paste the grid file content that can be found in the 
site online into brand-new created files.

## Download Data - PIOMAS:

Downloaded `heff` data from: `/pscfiles/zhang/PIOMAS/data/v2.1/heff/`

```bash
lcd /pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/PSC/new/PIOMAS`  
mget heff*
```

same was done for `area`.  

To download the grids use `curl` for simplicity:  

```bash
curl -k -O https://pscfiles.apl.washington.edu/zhang/PIOMAS/grid.dat
curl -k -O https://pscfiles.apl.washington.edu/zhang/PIOMAS/grid.dat.pop
curl -k -O https://pscfiles.apl.washington.edu/zhang/PIOMAS/io.dat_360_120.output
```

Otherwise copy/paste the content as for GIOMAS.

# Post-process the data

First, create the dir `grid` with: 
- `grid.dat`
- `grid.dat.pop`
- `io.dat_360_120.output` (for GIOMAS) and `io.dat_360_276.output` (for PIOMAS)  

and the gunzip (.gz) compressed binary files (`gz_from_site/binary/heff.H*.gz`).

Then run the scripts:

- `process_sithick_binary_Giomas.py` for GIOMAS
- `process_sithick_binary_Piomas.py` for PIOMAS

which will produce a NetCDF file with the concatenated monthly averaged data (e.g. `sithick_r1i1p1_mon_197901-202412_GCCS360x120.nc`).

### Set the curvilinear grid to the concatenated files

Now it is necessary to set the curvilinear grid specification to both files.  
We can use CDO for this purpose.

#### GIOMAS

To set the grid:
- `cdo setgrid,grid_giomas.txt sithick_r1i1p1_mon_197901-202412_GCCS360x276.nc sithick_r1i1p1_mon_197901-202412_GCCS360x276_cgrid.nc`

to set the fillNaNs:
- `cdo setctomiss,9999.9 sithick_r1i1p1_mon_197901-202412_GCCS360x276_cgrid.nc sithick_r1i1p1_mon_197901-202412_GCCS360x276_curvgrid.nc`

#### PIOMAS

To set the grid:
- `cdo setgrid,grid.txt sithick_r1i1p1_mon_197901-202412_GCCS360x120.nc sithick_r1i1p1_mon_197901-202412_GCCS360x120_curvgrid.nc`

Note: no `cdo setctomiss,9999.9` command is done for PIOMAS, as this command is not present in the 'old' file history form F. Massonet. We wanted to keep consistent with that pre-processing steps.

Finally, use `cdo sinfo FINAL_FILE.nc` to check that the grid is correctly `curvilinear`
