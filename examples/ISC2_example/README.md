# ISC Training example

#### Table of contents
1. [What it does](#what-it-does)
2. [How it works](#how-it-works)
2. [Dependencies](#Dependencies)
2. [Running the example](#Running)

## What it does

Fetches data from the simulated HVAC API and uses Iotic things to share their readings data

## How it works

The application conects with a localhost API and get all the data in JSON format.

1. First hit /list to get a list of simulated HVACs
2. Create an Iotic Thing for each of the HVACs
4. Adds one Feed to each Thing to share readings data
5. Every 10 seconds, hit all of the /readings/{id} api and publish the data for that feed

`note` Max amount of requests is set by the API, if you want to get unlimited number of requests you have to use the *Application Token*. For more information visit https://dev.socrata.com/docs/app-tokens.html

## Dependencies

This example uses

1. [requests](https://pypi.python.org/pypi/requests)

It's up to you how you install these and set your PYTHONPATH to access them.  I did from the root of this repo by...
```bash
pip3 install -t examples/ISC2_example/3rd -r examples/ISC2_example/requirements.txt

```


## Running

...and if you look in the run.sh in src you'll see the line that sets the PYTHONPATH to it
```bash
PYTHONPATH=../3rd:../examples python3 -m Ioticiser ../cfg/cfg_examples_isc2.ini
```
