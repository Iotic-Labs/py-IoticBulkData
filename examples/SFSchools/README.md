# San Francisco Open Data Schools

#### Table of contents
1. [What it does](#what-it-does)
2. [How it works](#how-it-works)
2. [Dependencies](#Dependencies)
2. [Running the example](#Running)

## What it does

Takes all San Francisco's schools data from SF Open Data API, creates an Iotic Thing for each school and publish all the information as feed.

## How it works

The application conects with an external API and get all the data in JSON format.

1. Gets all San Francisco's schools using **APIRequester** class
2. For each schools in the JSON file creates a **School** object
3. Transforms each School in an iotic **Thing**
4. Adds one **Point** to each Thing to share school data
5. The application will be updating the data every one hour

`note` Max amount of requests is set by the API, if you want to get unlimited number of requests you have to use the *Application Token*. For more information visit https://dev.socrata.com/docs/app-tokens.html

## Dependencies

This example uses

1. [requests](https://pypi.python.org/pypi/requests)

It's up to you how you install these and set your PYTHONPATH to access them.  I did from the root of this repo by...
```bash
pip3 install -t examples/SFSchools/3rd -r examples/SFSchools/requirements.txt

```


## Running

...and if you look in the run.sh in src you'll see the line that sets the PYTHONPATH to it
```bash
PYTHONPATH=../3rd:../examples/SFSchools/3rd:../examples python3 -m Ioticiser ../cfg/cfg_sfopendata_schools.ini
```
