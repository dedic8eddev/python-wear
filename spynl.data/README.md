# Spynl Data

## spynl_schemas

Includes all data schemas. In these schemas you can also find the code that is used to generate 
foxpro events. These schemas are used both in spynl and in mongo-scripts (e.g. for syncing 
processes).

## spynl_dbaccess

A layer around pymongo that takes care of, among other things, setting the correct settings on the
database, adding created and modified timestamps and setting readpreference.

## Installation and database connections

This repo is meant to be developed as a submodule of spynl.app, so follow the installation 
procedure of spynl.app. It is also used as a submodule in mongo-scripts, but the cli functionality 
to tag spynl.data lives in spynl.app.

## Code style

The gitlab pipeline (see .gitlab-ci.yml) enforces the codestyle. It will not change the code 
autmatically, but instead the pipeline will fail. For information about the codestyle, see the 
README in spynl.app.


| | |
|-|-|
|**NOTE:**| Be sure to also regularly update spynl.data in the mongo-scripts repo, especially if  data models are changed for any of the syncs (at time of writing, retail/wholesale customers and packing lists) |
