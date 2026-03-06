#!/usr/bin/python
#
# Francois Massonnet
# May 2017
# Adapted in Sep 2025 to update the data up to 2024 by Emanuele Tovazzi
#
# Script to convert GIOMAS sea ice thickness, distributed as binary files,
# into NetCDF files compliant with the TECLIM format
#
# Documentation on GIOMAS can be found here:
# https://psc.apl.washington.edu/zhang/Global_seaice/data.html
#
# The approach to reading binaries is inspired from this post:
#
# http://stackoverflow.com/questions/8710456/reading-a-binary-file-with-python

import numpy as np
import struct
import gzip
from netCDF4 import Dataset, date2num
import csv
import os
import sys
import datetime


def compute_monthly_time_bounds(dates, units, calendar="gregorian"):
    """
    Compute monthly time bounds for a list of datetime objects.

    Parameters
    ----------
    dates : list of datetime.datetime
        Datetime objects representing the reference time (usually 1st of each month).
    units : str
        Units string for conversion with date2num (e.g., "days since 1979-01-01").
    calendar : str
        Calendar type (default: "gregorian").

    Returns
    -------
    numpy.ndarray
        Array of shape (len(dates), 2) with start and end bounds for each time step.
    """
    bounds = []
    for dt in dates:
        # Start = current month
        start = dt

        # End = first day of next month
        if dt.month == 12:
            end = datetime.datetime(dt.year + 1, 1, 1)
        else:
            end = datetime.datetime(dt.year, dt.month + 1, 1)

        bounds.append([
            date2num(start, units=units, calendar=calendar),
            date2num(end, units=units, calendar=calendar)
        ])
    return np.array(bounds)


######## Global PARAMS ########
# First and last year defining the period to process
yearb = 1979
yeare = 2024

# Location of the input binary files (the "heff.HYYYY.gz"), grids, and output dir
sourcedir = "../../heff/gz_from_site/binary"
griddir   = "../../grids"
outdir    = "./output"

# GIOMAS - Grid dimensions (should not change)
ny = 276
nx = 360
nt = 12  # Number of time steps in one file. Here, monthly --> 12

# ------------------
# END SET PARAMETERS
# ------------------
nyear = yeare - yearb + 1

list_files = []

# 1. Deal with sea ice thickness
# ------------------------------
sithick = np.empty((nt * nyear, ny, nx))
sithick[:] = np.nan

for year in np.arange(yearb, yeare + 1):
  print(year)
  filein = sourcedir + "/" + "heff.H" + str(year) + ".gz"

  list_files.append(filein)

  # 1. Open the binary object
  with gzip.open(filein, mode = 'rb') as file:
    fileContent = file.read()

  # 2. Read as float ("f"). Each entry is a string of four letters
  a = struct.unpack("f" * (len(fileContent) // 4), fileContent)

  # 3. Reshape
  sithick[(year - yearb) * nt:(year - yearb) * nt + nt, :, :] = np.reshape(a, (nt, ny, nx))


# 2. Deal with lon, lat
# ---------------------
# Information on lon and lat is stored in an ASCII file with 10 columns
# and 19872 rows: the first 9936 for longitudes of scalars, the last 9936
# for latitudes of scalars.
#
# This makes 10 * 9936 = 99360 = 360 * 276 points

filein = griddir + "/" + "grid.dat"
print("Open: ", filein)

tmp = list()
with open(filein, 'r') as f:
    reader = csv.reader(f, delimiter = " ")
    for row in reader:
        tmp.append([float(r) for r in row if r != ''])

a = np.array([item for sublist in tmp for item in sublist])

lon = np.reshape(a[:ny * nx], (ny, nx))
lat = np.reshape(a[ny * nx:], (ny, nx))

# 3. Deal with grid cell area
# ---------------------------
# Information on cell edge length is stored in an ASCII files with 10 columns
# and 69552 = 7 * 9936 rows, following the same logic as for lon, lat
# Inspired from ftp://pscftp.apl.washington.edu/zhang/PIOMAS/utilities/read_360_120.f
# we know that the edge lengths for scalars are the third and fourth blocks

tmp = list()
filein = griddir + "/" + "grid.dat.pop"
with open(filein, 'r') as f:
    reader = csv.reader(f, delimiter = " ")
    for row in reader:
        tmp.append([float(r) for r in row if r != ''])

a = np.array([item for sublist in tmp for item in sublist])

htn = np.reshape(a[2 * (ny * nx): 3 * (ny * nx)], (ny, nx)) # Python numbering starts at zero!
hte = np.reshape(a[3 * (ny * nx): 4 * (ny * nx)], (ny, nx))
# Edge lengths are in km, we convert in meters
areacello = htn * 1000.0 * hte * 1000.0

# 4. Deal with ocean mask
# -----------------------
# Information on land sea mask is stored in an ASCII File with 276 rows. Each row
# contains 720 characters. We can ignore even characters (0, 2, ...). Odd characters
# greated than zero mean ocean, else land
tmp = list()
filein = griddir + "/" + "io.dat_360_276.output"
with open(filein, 'r') as f:
    reader = csv.reader(f)
    for row in reader:
      for j in np.arange(1, nx * 2, 2):
        if int(row[0][j]) > 0:
          tmp.append(1)
        else:
          tmp.append(0)

mask = np.reshape(tmp, (ny, nx))

# 5. Save as NetCDF
# -----------------
# GCCS = Generalized curvilinear coordinate system (grid of PIOMAS)
fileout = outdir + "/"  + "sithick_r1i1p1_mon_" + str(yearb) + "01-" + str(yeare) + "12_GCCS" + str(nx) + "x" + str(ny) + ".nc"

print("Creating: ", fileout)

# Create file
f = Dataset(fileout, mode = "w")

# Create dimensions
time = f.createDimension('time', None)
y   = f.createDimension('y', ny)
x   = f.createDimension('x', nx)
# Add time bounds dimension and variable
f.createDimension('bnds', 2)

# Create variables
times = f.createVariable('time', np.int32, ('time',))
""" Old block from original script - kept for reference with the original code
times[:] = range(nt * nyear)
#times.units = "months since " + str(yearb) + "-" + str(01) + "-" + str(15)
times.units = "months since " + str(yearb) + "-" + str(1).zfill(2) + "-" + str(15).zfill(2)
"""
# Define time units and calendar
time_units = "days since 1979-01-01 00:00:00"
calendar = "gregorian"

# Generate datetime objects for the 1st of each month
dates = [datetime.datetime(year, month, 1)
         for year in range(yearb, yeare + 1)
         for month in range(1, 13)]

# Convert to numeric days since 1979-01-01
times[:] = date2num(dates, units=time_units, calendar=calendar)

# Set attributes
times.units = time_units
times.calendar = calendar
times.long_name = "time"
times.standard_name = "time"
times.axis = "T"

# Time_bounds variable
time_bnds = f.createVariable('time_bnds', np.float64, ('time', 'bnds'))
time_bnds[:, :] = compute_monthly_time_bounds(dates, time_units, calendar)
times.bounds = "time_bnds"

# Sea ice thickness
h = f.createVariable('sithick', np.float32, ('time', 'y', 'x'))
h.units = "m"
h.long_name = "Sea ice thickness"
h.standard_name = "sea_ice_thickness"
h[:] = sithick

# Longitude
lons = f.createVariable('longitude', np.float32, ('y', 'x'))
lons.units = "degrees_east"
lons.long_name = "longitude"
lons.standard_name = "longitude"
lons.axis = "X"
lons[:] = lon

# Latitude
lats = f.createVariable('latitude', np.float32, ('y', 'x'))
lats.units = "degrees_north"
lats.long_name = "latitude"
lats.standard_name = "latitude"
lats.axis = "Y"
lats[:] = lat

# Cell area
cellarea = f.createVariable('areacello', np.float32, ('y', 'x'))
cellarea.units = "m2"
cellarea.long_name = "Ocean grid-cell area"
cellarea.standard_name = "cell_area"
cellarea[:] = areacello

# Sea fraction mask
sftof  = f.createVariable('sftof', np.float32, ('y', 'x'))
sftof.units = "1"
sftof.long_name = "Sea fraction (0=land, 1=ocean)"
sftof.standard_name = "sea_area_fraction"
sftof[:] = mask

# ---- Global attributes ----
f.Description = "model/reanalysis output"
f.Model = "Global Ice-Ocean Modeling and Assimilation System (GIOMAS)"
f.Reference = "Zhang, J., and D.A. Rothrock, Modeling global sea ice with a thickness and enthalpy distribution model in generalized curvilinear coordinates, Mon. Wea. Rev., 131(5), 681-697, 2003"
f.setncattr("raw_data", ", ".join(os.path.basename(fi) for fi in list_files))
f.file_created = "Created " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
f.Conventions = "CF-1.8"
f.setncattr("script_used", os.path.basename(sys.argv[0]))
f.processing_info = "grid.dat, grid.dat.pop, and io.dat_360_276.output can be obtained at: https://psc.apl.washington.edu/zhang/Global_seaice/data.html"

# Close
f.close()
