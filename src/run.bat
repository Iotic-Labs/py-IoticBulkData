setlocal

rem remove the old stash json if you want to run from scratch.
rem del ..\data\isc2_gateway.json

set PYTHONPATH=..\examples
python -m Ioticiser ..\cfg\cfg_examples_isc2.ini
endlocal