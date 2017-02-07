#!/bin/bash

export PYTHONPATH=3rd

INCLUDES="./*/"

echo -e "\n****** Python 3.x ******\n"
../../3rd/python3/static_checks/run.sh ../flake8.cfg ../pylint.rc $INCLUDES

echo -e "\n****** Python 2.x ******\n"
../../3rd/python3/static_checks/run2.sh ../flake8.cfg ../pylint.rc $INCLUDES
