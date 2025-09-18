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
... Multiple years covering from heff.H1979 to 
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

# Post-process the data
