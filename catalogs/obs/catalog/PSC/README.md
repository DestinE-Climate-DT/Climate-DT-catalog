# The Polar Science Center (PSC) datasets

This readme document is an informal log of the steps and procedures followed to download and pre-process the sea ice data.  

At first, we give a brief extrapolation of the most relevant information collected from the online pages which provide and describe the data. Then are presented the steps for downloading the data and pre-process them.


## Introduction on GIOMAS (Global Ice-Ocean Modeling and Assimilation System) model
GIOMAS Global Sea Ice Data [page LINK](https://psc.apl.washington.edu/zhang/Global_seaice/data.html), is global sea ice data for studying the variability and change of the polar climate, which consists of a global Parallel Ocean and sea Ice Model 
([POIM, Zhang and Rothrock 2003](http://psc.apl.washington.edu/zhang/Pubs/POIM.pdf)) with data assimilation capabilities. The POIM is formulated in a generalized orthogonal curvilinear coordinate (GOCC) system. Satellite sea ice concentration data are assimilated in GIOMAS using the Lindsay and Zhang (2005) assimilation procedure. The procedure is based on 'nudging' the model estimate of ice concentration toward the observed concentration in a manner that emphasizes the ice extent and minimizes the effect of observational errors in the interior of the ice pack.  

The dimension of the model is 360x276.  

While in the southern hemisphere the model grid is based on a spherical coordinate system. In the northern hemisphere the model grid is a stretched GOCC grid with the northern grid pole displaced into Greenland.  
 This allows the model to have its highest resolution in the Greenland Sea, Baffin Bay, and the eastern Canadian Archipelago, and therefore a  good connection between the Arctic Ocean and the Atlantic Ocean via the Greenland-Iceland-Norwegian (GIN) Sea and the Labrador Sea. The model was driven by the NCEP/NCAR reanalysis data.

 For a more detailed report and information see: [LINK Description of GIOMAS](https://psc.apl.washington.edu/zhang/Global_seaice/data.html).

 While GIOMAS cover the whole globe, PIOMAS is another model which covers the Northern Hemisphere ocean north of ~45° N.

 ## Introduction on PIOMAS (Pan-Arctic Ice-Ocean Modeling and Assimilation System) model

The Pan-Arctic Ice-Ocean Modeling and Assimilation System (PIOMAS) is a coupled ice‐ocean model developed at APL/PSC, used to calculate of some key ice and ocean variables such as the Arctic Sea Ice thickness Reanalysis. It is a numerical model with components for sea ice and ocean and the capacity for assimilating some kinds of observations, whose grid emphasizes the Arctic Ocean. Sea ice concentration information from the NSIDC near-real time product are assimilated into the model to improve ice thickness estimates. The pan-Arctic ocean model is forced with input from a global ocean model at its open boundaries located at 45 degrees North. PIOMAS is one-way nested inside the global model and uses monthly GIOMAS output for open boundary conditions along ~43° N.

The dimension of the model is 360x120.  

The current primary version of PIOMAS is v2.1. 

For more info on PIOMAS 
- see §2 at: [Schweiger et al., 2011](https://psc.apl.uw.edu/wordpress/wp-content/uploads/schweiger/pubs/Schweiger-2011-Uncertainty%20in%20model.pdf)  
- or see: [LINK Description of PIOMAS](https://psc.apl.uw.edu/research/projects/arctic-sea-ice-volume-anomaly/)

| Dataset comparison | Grid type              | Grid size   | Spatial coverage | Typical horizontal resolution                                 |
|---------|------------------------|-------------|------------------|---------------------------------------------------------------|
| PIOMAS  | Generalized curvilinear | 360 × 120   | 45° N–90° N      | ~22 km mean in Arctic/Barents/GIN/Baffin Bay                  |
| GIOMAS  | Generalized curvilinear | 360 × 276   | Global           | ~0.8° × 0.8° (~60 km) (reported average)                      |

---

## Download GIOMAS data:

On LUMI directory: `/pfs/lustrep3/appl/local/climatedt/data/AQUA/datasets/PSC/`

Folder created as: `new/GIOMAS/heff`, then tried to connect with different methods, one that worked well is `sftp`.

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

## Download PIOMAS data:

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


---------
Last updated by Emanuele Tovazzi, CNR, Sep 2025
