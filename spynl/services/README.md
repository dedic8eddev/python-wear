# Overview

This module provides basic services which are useful for implementing features.

## PDF

Printing HTML and CSS to pdf and sends it to an email-address.

### Installation Tips:

The weasyprint package can be installed with pip, but there are also dependencies
that cannot be installed with pip.

For Debian/Ubuntu the requirements are:

``` bash
sudo apt-get install \
    libcairo2-dev \
    libpango1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    zlib1g-dev\
    libjpeg-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    gir1.2-pango-1.0 \
    python3-lxml \
    python3-gi \
    shared-mime-info \
    libgirepository1.0-dev
```

### MacOs Installation

This will require the Homebrew package manager https://brew.sh/

Then, install the weasyprint dependencies:

```
$ brew install python3 cairo pango gdk-pixbuf libffi pygobject3
```

Add the following statements to your profile (.bashrc or equivalent):

``` bash
export PKG_CONFIG_PATH=“/usr/local/opt/libffi/lib/pkgconfig”"
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
```

Now try to run the tests, if it doesn't work you might have to link the gi library to
you virtual env. There is a helper function in the spynl-cli for this. Depending on 
which version of Python is installed, you will need to give it the following path.

```
$ spynl-cli services install-gi --folder /usr/local/lib/python3.7/site-packages/gi
```

## Upload

Loading images (standard and tenant logos) to AWS.


### AWS-Credentials

At first it tries searching for the 'credentials' file in this
directory: '/home/$USER/.aws/'
If it can't find it, then tries to get the credentials from the
environmental variables:

* AWS_ACCESS_KEY_ID
* AWS_SECRET_ACCESS_KEY

# spynl.pipe

This module enables piping of traffic to third-party servers.

This is useful because we can log traffic in our database, and maybe translate
some of the responses for convenience of our client software. 

Currently, two resource types are supported: 
* /posapi/ -> Foxpro
* /stockscube/ -> VectorResource

i.e. add to paths_resources.json:

"posapi": "spynl.pipe.FoxproResource",
"stockskube": "spynl.pipe.VectorResource"},
