# choco-updater :chocolate_bar:
Chocoupdater is a Python script to update your local choco repository

## Requirements
```
certifi                2020.12.5
chardet                3.0.4
colored                1.4.2
colorama               0.4.4
idna                   2.10
lxml                   4.6.2
pip                    20.3.1
protobuf               3.14.0
requests               2.25.0
setuptools             51.0.0
six                    1.15.0
soupsieve              2.0.1
termcolor              1.1.0
urllib3                1.26.2
wheel                  0.36.1
```

## Usage
+ mode : __check__
   + From a package list defined in database tbl 'package'  
    the script makes HTTP GET to Chocolatey community API
    just to check latest version of each package and update database.
+ mode : __upgrade__
   + Runs pending updates then set as updated 
+ mode : __init__
   + migrate query structure in local sqlite3 db
   + seed query structure in local sqlite3 db
+ mode : __status__
   + show list of upgradable packages


```
python xml-parser.py init|check|status|upgrade
```
