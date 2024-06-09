[![pipeline status](https://gitlab.com/softwearconnect/spynl.app/badges/master/pipeline.svg)](https://gitlab.com/softwearconnect/spynl.app/commits/master)
[![coverage report](https://gitlab.com/softwearconnect/spynl.app/badges/master/coverage.svg)](https://gitlab.com/softwearconnect/spynl.app/commits/master)

This repo combines the spynl app with two submodules, the shared data model library spynl.data
and the marshmallow-jsonschema repo used for generating documentation.

[Endpoint documentation](https://softwearconnect.gitlab.io/spynl.app/)

[[_TOC_]]

# Local usage

## Installing spynl

### Linux system dependencies

See the [Dockerfile](Dockerfile) for the apt-get install command.
To be able to install weasyprint in a virtualenv you will additionaly need:
`apt install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 libffi-dev libjpeg-dev libopenjp2-7-dev`

### Mac system dependencies

The weasyprint dependencies for mac are:
`brew install pango libffi`

### Windows system dependencies
- Install [Python](https://www.microsoft.com/store/productId/9NRWMJP3717K)
- Install [GTk](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases) to run WeasyPrint on Windows
- Install [AWS-CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  - install Ubuntu: `wsl --install -d Ubuntu`

### Installation steps Mac/Linux:

1. Clone the repo.
2. Install non-python requirements (see above)
3. Init the submodules, this only needs to be done once:
    1. `git submodule init`
    2.  `git submodule update --remote`
4. Make your virtual environment (use python 3.8 or higher) and **activate** it
    1. `python3 -m venv .venv`
    2. `source .venv/bin/activate`
5. `pip install --upgrade pip setuptools`
6. `pip install -r dev-requirements.txt`
7. `spynl-cli dev translate`
8. `spynl-cli dev versions`
9. `spynl-cli services install-fonts`

### Installation steps Windows:

1. Clone the repo.
2. Install non-python requirements (see above)
3. Init the submodules, this only needs to be done once:
    1. `git submodule init`
    2.  `git submodule update --remote`
4. Make your virtual environment (use python 3.8 or higher) and **activate** it
    1. `powershell Set-ExecutionPolicy RemoteSigned`
    2. `python3 -m venv .venv`
    3. `.\.venv\Scripts\activate`
5. `pip install --upgrade pip setuptools`
6. `pip install -r dev-requirements.txt`
7. Restart the PC and after restarting continue with:
8. `.\.venv\Scripts\activate`
9. `spynl-cli dev translate`
10. `spynl-cli dev versions`
11. `spynl-cli services install-fonts`

the file [scripts/environment](scripts/environment) includes some
useful utilities when sourced.

## Connecting to databases

### Setting up local stack

To be able to run the tests or serve spynl locally, you will have to have a MongoDB and Redshift
database running. This can be done using the local stack functionality of the
[softwear-development repo](https://gitlab.com/softwearconnect/softwear-development).

To set up the local stack refer to the
[README](https://gitlab.com/softwearconnect/softwear-development/-/blob/master/local_stack/README.md).
You will need to follow the instructions to get Docker and to get access to the Gitlab registry,
but if you're only running spynl, there is no need to setup nginx etc.


### Using local stack

You can choose to run the full stack (see the documentation of the local stack) or only start
MongoDB and Redshift:

* with a script:
```bash
./spynl-test-dbs.sh
```

* with docker-compose commands:
``` bash
docker-compose -f /path_to_repo/softwear-development/local_stack/docker-compose.yml down
docker-compose -f /path_to_repo/softwear-development/local_stack/docker-compose.yml pull mongo postgres
docker-compose -f /path_to_repo/softwear-development/local_stack/docker-compose.yml up -d mongo postgres
```

NOTE: at the moment there seems to be a mismatch when running the fullstack, if tests fail, use
the steps above.

## Running tests

To run the tests use:
``` bash
py.test tests
```
If you want to generate coverage files, use the following cli command:
``` bash
spynl-cli dev test
```
This command is also used in the gitlab pipeline.


### Useful test development tools and options

When running py.test the most useful options are
* `--sw`: Run tests stepwise, stop as soon as a test fails and start at that test the next time
          the command is run
* `--lf`: Only run the tests that failed the previous run.
* `-x`:   Stop running as soon as a test fails.
If you install `pytest-xdist` you can add `-n auto` to run the tests more quickly:
``` bash
py.test tests/main tests/api tests/services -n auto
```
The plugin `pytest-deadfixtures` can be used to see if there are any dead fixtures once in a while.

### Generating pdf and excel files

PDF and excel files are normally generated in memory. If you want to look at a file that is
generated during a test you can use the environment variable `DEBUG=true`. For example:

``` bash
# generating test.pdf in the working directory (:: makes it possible to run one specific test
# from a test file)
DEBUG=true py.test tests/services/pdf/test_order.py::test_email_sales_order_pdf
# generating a test.xlsx:
DEBUG=true py.test tests/services/reports/test_article_status.py::test_excel
```

## Code style

The code style is based on [PEP 8](https://www.python.org/dev/peps/pep-0008/). For naming
variables/functions/classes we use the conventions from PEP 8.

Parameters that are used by the frontend are generally in camel case instead of snake case. The
field names in the data models are also often camel case. Snake case is used there for fields that
are internal, or by mistake.

We use three tools to autoformat/style the code. Make sure you set up your editor to use these,
the pipeline will fail if checks from these tools fail.

* [black](https://github.com/psf/black)
* [isort](https://github.com/PyCQA/isort)
* [flake8](https://flake8.pycqa.org/en/latest/)

The configuration for these tools is in setup.cfg and pyproject.toml. For **black** we use the **-S** option, to skip string normalization. If you see the strings all change, undo and run black
with the `-S` option instead.

For strings the following rules apply:
* Use single quotes wherever possible (but if e.g. the string contains a single quote, use double quotes instead of escaping the single quote)
* Use double quotes for docstrings
* Never go beyond 88 characters (We skip string normalization in black, so this you need to take care of yourself)

## Serving spynl locally

To run spynl use:
``` bash
spynl-cli dev serve
```
It will use the development.ini file in spynl.api by default. Use the `-i` option to specify an
ini file. If you use the development.ini, it can be reached at `http://localhost:6543`.

## Translations

We use [Babel](https://babel.pocoo.org/en/latest/) for the translations. The configuration of
babel lives in [setup.cfg](setup.cfg) and [setup.py](setup.py). The translation files can be
found in the [locale](spynl/locale) folder. The binary .mo files are not stored in the repo, so
they need to be generated locally and on the server (see [Installation steps](#installation-steps)
and the [Dockerfile](Dockerfile)). This is done by running:

``` bash
spynl-cli dev translate
```

If you added a new translation string in the code (e.g. `_('some-new-thing-to-translate)`), run
the following command to pick it up:

``` bash
spynl-cli dev translate -r
```

You can then add the proper translations to the .po files in the language subfolders, see
`locale/[language]/LC_MESSAGES/spynl.po`. After adding the translations, you'll need to run
`spynl-cli dev translate` again to update the binaries.

### Translations of sales orders and packing lists

Sales orders and packing lists are translated using a  utility function from spynl.services.pdf.utils.
The translations are in that function. This is done because those documents are translated based
on the language of the customer on the document, instead of that of the logged-in user.
There are also more languages available, and it's easier to add one quickly.

# Spynl Data

spynl.data is managed in this repo as a submodule.

Managing the repo requires a basic knowledge of how git submodules work.
You can refer to the [git book](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
or run `man git-submodules`.

If one or more commits are done to the spynl.data master, they need to be commited in
spynl.app as well. This can easily be done by adding this command to your `.gitconfig`:

``` bash
[alias]
udata = "! git commit -am \"$(git diff --submodule=log | tail -n+2 | awk 'BEGIN {printf \"spynl.data: \"} {printf \"%s \", $3} END {print \"\"}')\""
```

You can use this in spynl.app master, after which you can push:

``` bash
(master)$ git udata
(master)$ git push
```

These projects are put together in a docker image based on Ubuntu and
sent to either our development docker registry or the registry hosted by
Sentia, a third party that manages our production stack.

| | |
|-|-|
|**NOTE:**| Be sure to also regularly update spynl.data in the [mongo-scripts repo](https://gitlab.com/softwearconnect/mongo-scripts), especially if  data models are changed for any of the syncs (at time of writing, retail/wholesale customers and packing lists) |

## Making an MR with changes to both spynl.app and spynl.data

Because the pipeline of an MR tests the code, if the tests depend on the changes in spynl.data,
you need to follow this procedure:

1. Make branches for both spynl.data and spynl.app
2. Make the changes
3. Commit in spynl.data first, push and make an MR
4. Now commit in spynl.app, that way the branch points to the commit in the corresponding
   spynl.data branch. Make an MR.

To merge these two MR's after the review process:

1. Merge the spynl.data MR in gitlab
2. Locally, check out the branch in spynl.app
3. Cd into spynl.data, check out master and pull.
4. Cd back to spynl.app, commit (now spynl.data points to the new master, including the relevant
   changes) and push.
5. Now merge spynl.app in gitlab

# Sentry integration

[Sentry](https://sentry.io/organizations/softwear/issues/?project=59748) is used to log errors. 
Because Sentry limits the amount of events we can see every month, we need to make sure we do 
not log expected errors (e.g. wrong username/password). This is done by setting `monitor` to 
false in the corresponding Exception. (Make sure the exception inherits from 
[SpynlException](spynl/main/exceptions.py#L8))

# Tagging

The command `spynl-cli ops tag` can be used to tag spynl.app and spynl.data. If you pass the
`--push` tag it will automatically push these tags:
```
spynl-cli ops tag --push
```
If you do not use `--push` you will need to push the tags manually.

If you only want to tag spynl.app use:
`spynl-cli ops tag --push --skip-data`

If you only want to tag spynl.data use:
`spynl-cli ops tag --push --skip-app`

## Changelog

There are two cli functions that can be used to generate a changelog:

``` bash
# This command includes the titles of the the tickets, but does not pick up all tickets:
spynl-cli ops changelog
# This command only returns a link to all jira tickets in the version, but does pick up multiple tickets in one commit message, and the tickets included in spynl.data:
spynl-cli ops quick-changelog
```

# CI pipeline

For details about the pipeline see the [gitlab yaml file](.gitlab-ci.yml). The pipeline will run
for all commits. During the pipeline all tests will be run and the code quality will be checked.

## Spynl docker image - pinning libraries

We rarely pin specific versions of libraries, so when the Docker image is created, the newest
versions of the libraries are used. This means that if there are breaking changes, this sometimes
leads to failing tests or, in the case of e.g. setuptools, a failing build. If this happens, the
best thing to do is to compare versions from the last successfull build to those of the build
failed or had sudden failing tests (see the logs of the build job in the pipelines). Then you
can check if pinning the library to the earlier version solves the problem and update the
library at a later point.

There is a dev-release-notes channel on slack that is subscribed to some of the more important
libraries.

## Deployment

Commits to the master branch and tags will trigger a deploy to edge. Tagged commits will be
available to push to test/beta/production. Spynl docker images are connected to Bamboo by
committing to the
[halloumi-config repo](https://gitlab.com/softwearconnect/softwear-halloumi-config). Use Bamboo
to get the build to test/beta/production (see Bamboo documenation). Master commits that are not
tagged will only end up on edge, only tagged versions can be released to test/beta/procuction.

It is possible to build brances to edge, to do this make sure **`deploy-spynl`** is in the commit
message.


# Documentation

## Internal documentation

During the pipeline internal documentation is generated and deployed to
[gitlab pages](https://softwearconnect.gitlab.io/spynl.app/). It uses the static
[index.html](spynl_swagger/index.html) that specifies which swagger cdn to use. The files for
the documenation contents are created in the pipeline with cli functions. You can also run
them locally (if you run them in the top spynl.app directory, they files will automatically
end up in the correct folder), and test it by opening the index file.

``` bash
# generate the spynl.json file that gets the endpoint information from the docstrings:
spynl-cli dev generate-documentation
# generate the api schemas linked to in the docstrings:
spynl-cli api generate-json-schemas
# generate the services schemas linked to in the docstrings:
spynl-cli services generate-json-schemas
```

## External documentation

The documentation of the api gateway also lives in spynl and is generated in the pipeline.
There are folders for [retail](spynl_swagger_external/retail) and
[wholesale](spynl_swagger_external/wholesale). In contrast to the internal documentation, the
file that lists the endpoints is not generated automatically, instead there is a swapi.yaml file
in each folder. The schemas that those files refer to *are* generated during the pipeline:

``` bash
spynl-cli api generate-external-schemas --folder spynl_swagger_external/retail
spynl-cli api generate-external-schemas --folder spynl_swagger_external/wholesale
```

These schemas do not only include schemas for the spynl endpoints, but also those from the
[foxpro endpoints](spynl/api/cli/sww_schemas.py).

## Marshmallow-jsonchema

[Marshmallow-jsonschema](https://gitlab.com/softwearconnect/marshmallow-jsonschema) is a fork of
[marshmallow-jsonschema](https://github.com/fuhrysteve/marshmallow-jsonschema) with changes by us
to make it more suitable for generating json schemas for the swagger documenation. In principle,
it should be possible to add the fork (so the the repo in gitlab softwearconnect) as a dependency,
but we could not get that to work in the pipeline, so now it is a submodule.
 
## Adding documentation to a new endpoint

To add documentation of a new endpoint:

* Add the correct yaml to the docstring of the endpoint
* Make sure the schemas (e.g. dataschema/get parameters) you refer to are generated with the 
  correct filenames in either [api_commands.py](cli/api_commands.py) or 
  [services_commands.py](cli/services_commands.py). For get/add/save endpoints you can use the
  generate_new_style_endpoints loop.

For an example of a standard get/save/add set, see the docstrings in 
[receiving.py](spynl/api/retail/receiving.py) and [inventory.py](spynl/api/retail/inventory.py).
For endpoints with file reponses and json responses defined in the docstring instead of a schema
see [retail_customer_sales.py](spynl/services/reports/retail_customer_sales.py)
 
# Debugging issues

## Debugging pipeline issues

If the pipeline build is not working, see 
[Spynl docker image - pinning libraries](#spynl-docker-image-pinning-libraries).

## Issues reported from production

It the customer is getting a 500, that error should have been logged to 
[Sentry](https://sentry.io/organizations/softwear/issues/?project=59748), and you should be
able to find it if you know the endpoint. The Sentry log has all the information that should 
make it possible to reproduce the error locally (e.g. traceback and post body).

If the customer gets an error message, grepping both the spynl.app and the spynl.data repo should
get you to the error quickly. If you find it in the translations, grep for the message id next.
