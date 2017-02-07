# TFL Bikes Example

#### Table of contents
1. [What it does](#what-it-does)
2. [How it works](#how-it-works)
2. [Dependencies](#Dependencies)
2. [Running the example](#Running)


## What it does

Creates a thing for every TFL bike station with a feed of slot and bike availability and total slots.

## How it works

In the `run()` method, it refreshes the data by hitting the api and then sleeps until the refresh time is up.

If it gets the api data it creates an Iotic Thing for each of the `site`s in the returned data.  Then it publishes the
feed with the new values for availability, etc for each site.

## Dependencies
This example uses

1. [requests](https://pypi.python.org/pypi/requests)

It's up to you how you install these and set your PYTHONPATH to access them.  I did from the root of this repo by...
```bash
pip3 install -t examples_private/TFL/3rd -r examples_private/TFL/requirements.txt
```

## Running

...and if you look in the [run.sh](../../src/run.sh) in  you'll see the line that sets the PYTHONPATH to it
```bash
PYTHONPATH=../3rd:../examples_private/TFL/3rd:../examples_private -m Ioticiser ..examples_private/cfg/cfg_tfl_bikes.ini
```
