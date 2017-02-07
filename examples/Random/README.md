# Random Feeds Example

#### Table of contents
1. [What it does](#what-it-does)
2. [How it works](#how-it-works)
2. [Dependencies](#Dependencies)
2. [Running the example](#Running)


## What it does

Creates a thing with various data feeds:

1. Random number
2. Random alphabet letter (upper and lower case)
3. Alphabet A-Z (upper and lower case)
3. Sawtooth wave
3. Sine wave

## How it works

1. Creates a thing
2. Creates all the feeds
3. In the `run()` function it repeatedly:
    - Calls each of the `run_<feed>` functions to allow them to generate their new value dependent on their timing
    - Waits for a second

## Dependencies
None

## Running

If you look in [run.sh](../../src/run.sh) in  you'll see the line that sets the PYTHONPATH and runs the
random example.
```bash
PYTHONPATH=../3rd:../examples python3 -m Ioticiser ../cfg/example_random.ini
```
