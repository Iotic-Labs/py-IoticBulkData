# DEFRA Seabirds example

#### Table of contents
1. [What it does](#what-it-does)
2. [How it works](#how-it-works)
2. [Dependencies](#Dependencies)
2. [Running the example](#Running)

## What it does

Takes seabird count data from the DEFRA "magic" data.  Creates an Iotic Thing for each of the locations in the file
with a feed of counts, one per species.

## How it works

Downloads the zip and unzips it into the local `data` directory and then uses pyshp shapefile module to read the
contents of the "shape" data.

Shape data is split (roughly) into

1. *Records* one for each location - create an Iotic Thing for each one
2. *Fields* the key/value key names - create and Iotic Value for each one
3. *Shapes* the geo-location data.  Can be complex, but in this example they are only one lat/long pair.  Use each one

to create the lat/long metadata for its corresponding record.

`note` the locations in the file are in Great Britain Ordnance Survey's OSGB36 standard of Eastings and Northings.
These coordinates need to be converted into latitude and longitude in the file [GeoConvert.py](GeoConvert.py)

## Dependencies
This example uses

1. [requests](https://pypi.python.org/pypi/requests)
2. [pyshp](https://pypi.python.org/pypi/pyshp)

It's up to you how you install these and set your PYTHONPATH to access them.  I did from the root of this repo by...
```bash
pip3 install -t examples_private/DEFRA/3rd -r examples_private/DEFRA/requirements.txt
```

## Running

...and if you look in the run.sh in src you'll need a line that sets the PYTHONPATH to it
```bash
PYTHONPATH=../3rd:../examples_private/DEFRA/3rd:../examples_private:. python3 -m Ioticiser ../examples_private/cfg/cfg_example_seabirds.ini
```
