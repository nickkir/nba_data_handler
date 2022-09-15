# nba_data_handler
Project for downloading, parsing and concatenation of public NBA data

A lot of my personal projects require publiccly available NBA data. These scripts are built on top of `nba_api`, which can be found [here](https://github.com/swar/nba_api/blob/master/README.md).

## Script types
There are basically three types of scripts: scripts for downloading data, scripts for concatenating data, and scripts for parsing data. There are also some models that implement convenient functionality. 

### Data downloading scripts
These scripts are pretty straightforward: they download data in its raw form, and save them into a specified directory. In general, these scripts keep track of which API requests have been made, so if for some reason execution is halted, upon re-running, previously saved data will not be requested.
