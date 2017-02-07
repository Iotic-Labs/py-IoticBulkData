# BART stations

#### Table of contents
1. [What it does](#what-it-does)
2. [How it works](#how-it-works)
2. [Dependencies](#Dependencies)
2. [Running the example](#Running)

## What it does

Takes all San francisco bay area stations data from [BART](http://api.bart.gov/docs/overview/index.aspx), creates an Iotic Thing for each station and gets the departures estimations to feed.


## How it works

The application conects with an external API and get all the data in XML format.

1. Builds a station object from xml with estimated departure data.
2. With all the objects created it starts to builds Iotic things with feed data.
3. To keep the estimations updated it calls to the API once per minute



## Dependencies

For using BART API we have to [registre](http://api.bart.gov/api/register.aspx) and get an app-key

This example uses

1. [requests](https://pypi.python.org/pypi/requests)

It's up to you how you install these and set your PYTHONPATH to access them.  I did from the root of this repo by...
```bash
pip3 install -t examples_private/BART/3rd -r examples_private/BART/requirements.txt

```

## Running

...and if you look in the run.sh in src you'll need a line that sets the PYTHONPATH to it
```bash
echo "Run bart stations bulk data"
PYTHONPATH=../3rd:../examples_private/BART/3rd:../examples_private python3 -m Ioticiser ..examples_private/cfg/cfg_bart_stations.ini
```
