# US Federal Aviation Administration

#### Table of contents
1. [What it does](#what-it-does)
2. [How it works](#how-it-works)
2. [Dependencies](#Dependencies)
2. [Running the example](#Running)

## What it does

Creates airports points to share weather and delay times in Iotic space. It gets the information from [Federal Aviation Administration](https://www.faa.gov/) and sends new feedback every 60 minutes.

## How it works

The application conects with an external API and get all the data in JSON format.

1. Read the csv file from [openflight](https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat)
2. Gets all the airport points with its data
2. Creates thing's basic metadata
3. Creates thing's feed for delay times
4. Creates thing's feed for weather
5. Updates each feed every 60 minutes


## Dependencies

This example uses

1. [requests](https://pypi.python.org/pypi/requests)

It's up to you how you install these and set your PYTHONPATH to access them.  I did from the root of this repo by...
```bash
pip3 install -t examples_private/usfaa_airports/3rd -r examples_private/usfaa_airports/requirements.txt
```

## Running

...and if you look in the run.sh in src you'll need a line that sets the PYTHONPATH to it
```bash

PYTHONPATH=../3rd:../examples_private/usfaa_airports/3rd:../examples_private python3 -m Ioticiser ../examples_private/cfg/cfg_examples_usfaa.ini

```
