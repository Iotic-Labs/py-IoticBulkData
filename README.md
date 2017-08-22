# Ioticiser Bulk Data

#### Table of contents
1. [What it does](#what-it-does)
2. [How it works](#how-it-works)
2. [Installing](#installation)
2. [The stash](#the-stash)
3. [Writing a Source Module](#writing-a-source-module)
4. [Running your source](#running-your-source)
4. [Limitations](#limitations)
5. [APPENDIX - The Stash API](#the-stash-api)

## Why?

Many IoT things are hidden behind APIs.  These APIs need access credentials, understanding by developers and then
their data needs interpretation. This often leads to linear, one-time use of the APIs.  Not very Iotic.

The Ioticiser for Bulk Data is the tool for the one-off integration of an external API and then pushing the data
 from that API into Iotic Space where it can be understood and reused by anybody.

## What?

### What it does

The Ioticiser is a tool that allows a developer to import an API on the "left" and then, in a module you write,
model the contents of the API as Iotic things in the "middle" and then push the data into Iotic space on the "right"

```
----------------       ---------------
|              |       |             |
| External API | ----> | Your Module | ----> IOTIC SPACE
|              |       |             |
----------------       ---------------
```

It's designed for APIs that contain lots of virtual things and their data, but can also be used for simulations,
monitoring hardware over radio links - anything, really, as long as it can be modelled as
above as a pull from the left and a push to the right.

## How?

### How it works
You write a module and ask the Ioticiser to run it for you using a configuration file such as
(cfg_examples_random.ini)[cfg/cfg_examples_random.ini]
The Ioticiser then imports your module and runs it in its own thread.

The Ioticiser will provide you with a "stash" api in which to store things while your module is working its way
through the API on the "left".  Once you're happy with your stash of stuff, the Ioticiser will use its
workers to update Iotic Space for you and let you get on with doing more of the API, sleeping until the next
 time or just finishing and waiting to be scheduled again.

### Installation

Download or clone the code from the repo.

#### Dependencies

To run the Ioticiser you'll need the py-IoticAgent

    1. [IoticAgent](https://pypi.python.org/pypi/py-IoticAgent/)

It's up to you how you install these and set your PYTHONPATH to access them.  I did from the root of this repo by
using the requirements.txt file to install the dependencies in the 3rd directory...
```bash
pip3 install -t 3rd -r requirements.txt
```
You can see how to [run your code](#running-your-source) later.

#### The Stash
The stash has two parts:

1. [The thing stash](#the-thing-stash)
2. [The key-value stash](#the-key-value-stash)

It's available to your module via the `self._stash` object


##### The thing stash
This is where you can create things, feeds and values and share data.  It works very similarly to the py-IoticAgent IOT
API but the Ioticiser's worker(s) don't action what you've done until you release each individual thing.

```
----------------       ---------------       --------------
|              |       |             |       |             |
| Your Module  | ----> |   Stash     | ----> |  Worker(s)  | ----> IOTIC SPACE
|              |       |             |       |             |
----------------       --------------        ---------------
```

##### The key-value Stash
This allows you to store things in your stash using the simple, key-value pair model.  It's useful for storing
 variables for the next time you're scheduled.  For example storing the last time your
 API was updated so you don't bother re-processing old data.
`Note` that all values in the stash are treated as strings, so remember to stringify and un-stringify them

More details on the stash API are in the [appendix](#the-stash-api)


### Writing a Source Module
A "Source" is the collective noun for all the things from an individual API.
We've written three examples for you as guidelines - Each has a different style

##### Our Worked Examples

`Note` - These are examples to show you how to run the the Ioticiser.  We already run them, so please don't run
them yourself.

1. [Random](examples/Random) - this is the simplest. It creates one thing and various feeds on it for random numbers,
 letters of the alphabet etc.  There's no "API" on the left - it's just simulated data
2. [SF Schools](examples/SFSchools) - this reads an API of school information for schools around the Bay Area,
San Francisco

#### Write a config file for your source
The config file contains parameters and file locations, etc. in the the well-known `ini` format.

##### config `[main]`
The `[main]` section is for the Ioticiser, where you specify where you want it to persist your stash
data (`datapath`) and the name of the sources you want to run (`sources`).

##### config `[<source>]`
The `[<source>]` section is for your module.  In here you can specify any key/value pairs you want.
It is _your responsibility_ to validate anything you put in here.  T
he only thing the Ioticiser needs to know is the number of `workers`  you want to action your activities.

##### example
```ini
[main]
datapath = ../data
; Names of config sections must be separated with \n\t
sources =
    SFopendata_schools

[SFopendata_schools]
; Required config options
import = SFSchools.SchoolsPublisher
agent = ../cfg/sfopendata_schools.ini
; Optional config passed to Source


; Set app key to get unlimited request
;app_key=my_app_key

; Time to update the values
refresh_time = 3600

; total Workers, default = 1
workers = 4
```

#### Create a directory in [examples](examples) (or anywhere else you like) for your module
put an `__init__.py` in it to make it a module

#### Write your module object
##### Inheritance and instantiation
Your object has to inherit from SourceBase and call `super()` at the beginning of `__init__()`
```python
class Random(SourceBase):
    def __init__(self, stash, config, stop):
        super(Random, self).__init__(stash, config, stop)
```

##### Thread `run()` method
This is the main entry point to your thread.  You can choose to run in either

1. `Continuous mode` - where you wait for the `stop` event to be set
2. `Single-shot mode` - where you ignore `stop` and just run.

###### Continuous mode:
Example from [Schools.py](examples/SFSchools/Schools.py)
```python
    def run(self):
        lasttime = 0
        while not self._stop.is_set():
            nowtime = monotonic()
            if nowtime - lasttime > self.__refresh_time:
                lasttime = nowtime
                self.get_schools_from_API()
            self._stop.wait(timeout=5)
```
This code compares the time now with the last time it ran and only runs `get()` if they differ
by the specified interval.  It then waits for a 5 second pause and does it all again.

###### Single shot mode
Example (fabricated)
```python
    def run(self):
        if self.__get_some_data():
            self.__publish_some_stuff()
        else:
            logger.info("Nothing to do - new data not available")

        logger.info("Finished")
```
In this fabricated example:  `__get_some_data()` returns true when the data is newer than the last time it ran.
This could be in a year's time.  We'd expect this kind of source to be scheduled using Cron rather than using python
timing as in the previous example

### Running your source
There's a [run script](src/run.sh) to run the Ioticiser Module.
Change the line to make sure PYTHONPATH includes all your dependencies and point the Ioticiser at your `.ini` file
```bash
#!/bin/bash
PYTHONPATH=../3rd:../examples/SFSchools/3rd:../examples python3 -m Ioticiser ../cfg/cfg_examples_schools.ini
```

### Limitations
1. The Ioticiser does not detect if things you created last time you ran your module have been deleted,
so it won't delete them for you.


### APPENDIX 1
#### The Stash API

The stash API is a lighter mimic of the IOT api in the Iotic Agent. [Documentation](https://iotic-labs.github.io/py-IoticAgent/)

The reason it exists is that you can create things and feeds /in the stash/ and when you release your stash thing,
the Ioticiser will go away and make your changes real in Iotic Space, allowing you to continue processing the API.

#### Key differences between Stash API and Agent API

##### Implicit vs Explicit Point.share()

The Stash API adds kwarg data to Point.create_value.  These are stashed and finally shared as a dictionary.  To add a *specific* time to the values the share function can be called with time only.
Calling the share function is optional when create_value(data=) is used *and* you're happy to share with datetime.utcnow().

```python
    feed.create_value("value", vtype=Datatypes.INTEGER, description="random number",
                      data=random.randint(0, 10))
    feed.share(time=reading['time'])
```

```python
    feed.create_value("value", vtype=Datatypes.INTEGER, description="random number")
    feed.share(data={"value": random.randint(0, 10)}))
```

more details on create value and share are [here](#create-values-on-a-feed-and-share-data)


##### No Follow/Attach

Feed Follow and Control Attach are not currently supported by the Stash API.


##### Create a `Thing`

###### Parameters
```python
   create_thing(lid):
```
|parameter|type|optional|comment|
|---|---|---|---|
|`lid`|string|no|Local Id of your thing|

###### Returns
a `Stash.Thing` instance

###### Example
Using code from [Schools.py](examples/SFSchools/Schools.py#L216) as an example (annotated)

```python
    with self._stash.create_thing(thing_name) as thing:  # Create a stash thing
        self._set_thing_attributes(school, thing)        # Set its attributes
        self._set_thing_description(school, thing)       # Description, etc.
        self._set_thing_points(school, thing)            # Add the feeds
```
Using the python `with` syntax allows you to build up everthing you want about your thing.  When you exit the `with`,
 the workers you've allocated to Ioticiser will go away and perform your updates for you.


##### Create a `feed` (or `control`)

###### Parameters
```python
    create_feed(pid)
    create_control(pid)
```
|parameter|type|optional|comment|
|---|---|---|---|
|`pid`|string|no|Local Point Id of your feed or control.  Note `Feed`s and `Control`s are sub-classes of `Point`, hence point_id|

###### Returns
a `Stash.Point` instance

###### Example
```python
self.__feed = self.__thing.create_feed("my_point")
```

##### Set the metadata for a `thing`, `feed` or `control`
These functions allow easy setting of metadata for the things you create.  `set_location()` only applies to `Thing`s
###### Parameters
```python
    set_label(label, lang=None)
    set_description(description, lang=None)
    create_tag(taglist)
    # Note Thing only
    set_location(lat, long)
```
|parameter|type|optional|comment|
|---|---|---|---|
|`label`|string|no|Short description for your thing, feed, etc - max 64 chars|
|`description`|string|no|Long description for your thing, feed, etc - max 256 chars|
|`taglist`|list of strings|no|List of tags for your thing, feed, etc. Each tag has min 3, max 16 chars no embedded spaces|
|`lat`|float|no|Latitude of your thing in WGS84 coordinates|
|`long`|float|no|Longitude of your thing in WGS84 coordinates|
|`lang`|string|yes|2-char language code, e.g. "de".  If `lang=None` then use the container default language (recommended)|

###### Returns
None of these functions return anything

###### Examples
```python
    thing.set_label(label, lang=LANG)
    thing.set_description(THING_DESCRIPTION, lang=LANG)
    thing.set_location(lat, lon)
    thing.create_tag(['School', 'SanFrancisco', 'OpenData'])
```

##### Create Values on a `feed` and share data
These functions allow you to set metadata for individual data points in a feed. Once these Value functions have
been called, you can call share, but it's not necessary if you've passed data to the `create_value()` function and
are happy to share with the current time
###### create_value() Parameters
```python
    create_value(label,
                 vtype=TYPE,
                 lang=LANG,
                 description=DESC,
                 unit=UNIT,
                 data=DATA)
```
|parameter|type|optional|comment|
|---|---|---|---|
|`label`|string|no|Name of the value (used as the json key)|
|`vtype`|string|no|value type from Datatypes.py, e.g. Datatypes.DECIMAL|
|`lang`|string|yes|2-char language code, e.g. "de".  If `lang=None` then use the container default language (recommended)|
|`description`|string|no|Text description of the value e.g. "External temperature"|
|`unit`|url|no|unit of the value from Units.py e.g. Units.CELSIUS - or (advanced) the correct URI from a units ontology e.g. "http://purl.obolibrary.org/obo/UO_0000301" is micrograms per liter|
|`data`|n/a|no|the data to share for this value (or use share(data=xxx))|

###### share() Parameters

It's only necessary to call `share()` if
- you want a different timestamp from the current time - for example if your data has a reading time which is different from now.
- you want to share some data, but you didn't use the `data=` keyword argument in the `create_value()` call

In cases such as the example below, the data for the `power` value is assigned in the call, and you're happy to share
with time of datetime.utcnow() (the default), then there's no need to call share at all, it'll be done for you.

`note` If you call share with no aguments, it will raise a ValueError

```python
    share(time=TIME
          data=DATA)
```
|parameter|type|optional|comment|
|---|---|---|---|
|`time`|timestamp|yes|Name of the value (used as the json key)|
|`data`|n/a|yes|the data to share for this *value*|


###### Examples
Implicit share

```python
    feed.create_value('power',
                      vtype=Datatypes.INT,
                      description='Power consumption in Watts',
                      unit=Units.WATT,
                      data=reading['power'])
```

Explicit share
```python
    feed.create_value('power',
                      vtype=Datatypes.INT,
                      description='Power consumption in Watts',
                      unit=Units.WATT)
    feed.share(data={'power': reading['power']})
```



###### Returns
Neither of these functions return anything


##### Store a key-value pair
These 2 functions allow you to store a key-value pair in your stash persistently - i.e. they will be available in
the stash the next time your code runs.

`Note`:  When you're testing, you're likely to be running with limit_things set to a smallish number and to
to be deleting your things before your next test.  In this case, remember to delete your stash `json` files
or you might get unpredicable results.
The files are in the `data/` directory and are called `<your_module>*.json`

###### Parameters
```python
    get_property(key):
    set_property(key, value=None):
```
|parameter|type|optional|comment|
|---|---|---|---|
|`key`|string|no|The key-name of the thing you want to save|
|`value`|`string` or `int`|no|the value you want to save|

###### Returns
1. `get_property` returns the value you saved or `None` if the key doesn't exist
1. `set_property` returns the nothing, but raises `ValueError` if your value is not a `string` or `int`

###### Example

```python
#save
self._stash.set_property("Last-Modified", str(self.__last_mod_time))
#retrieve
last_mod_str = self._stash.get_property("Last-Modified")
```
