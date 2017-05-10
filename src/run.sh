#!/bin/bash

#remove the old stash json if you want to run from scratch.
#rm ../data/isc2_gateway.json

PYTHONPATH=../3rd:../examples python3 -m Ioticiser ../cfg/cfg_examples_isc2.ini
# PYTHONPATH=../3rd:../examples/SFSchools/3rd:../examples python3 -m Ioticiser ../cfg/cfg_examples_schools.ini
