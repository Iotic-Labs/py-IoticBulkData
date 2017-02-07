# San Francisco Air quality

#### Table of contents
1. [What it does](#what-it-does)
2. [How it works](#how-it-works)
2. [Dependencies](#Dependencies)
2. [Running the example](#Running)

## What it does

Creates air quality points from San Francisco Bay area to share the data in Iotic space. It gets the information from [AirNow](https://docs.airnowapi.org/) and sends new feedback every 30 minutes.

## How it works

The application conects with an external API and get all the data in JSON format.

1. Gets all the air quaility points with its data in a defined area
2. Creates thing's basic metadata
3. Creates thing's feed for each measure
4. Updates each feed every 30 minutes


## Dependencies

For using AirNow API we have to [registre](https://docs.airnowapi.org/account/request/) and get an app-key


This example uses

1. [requests](https://pypi.python.org/pypi/requests)

It's up to you how you install these and set your PYTHONPATH to access them.  I did from the root of this repo by...
```bash
pip3 install -t examples_private/AQI/3rd -r examples_private/AQI/requirements.txt
```

## Running

...and if you look in the run.sh in src you'll see the line that sets the PYTHONPATH to it
```bash
echo "Run Air quality bulk data"
PYTHONPATH=../3rd:../examples_private/AQI/3rd:../examples_private -m Ioticiser ..examples_private/cfg/cfg_air_quality.ini

```
