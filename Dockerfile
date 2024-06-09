FROM ubuntu:20.04

RUN apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    python3.8-dev \
    python3-pip \
    build-essential \
    # begin for weasyprint:
    python3-cffi \
    python3-brotli \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    # end weasyprint
    supervisor \
    locales \
    zlib1g-dev\
    libjpeg-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    gcc \
    pkg-config \
    git

RUN locale-gen en_US.UTF-8

ARG BUILD_TIME
ARG BUILD_NR
ARG PRINTQ_S3_KEY
ARG PRINTQ_S3_SECRET

ENV SPYNL_BUILD_NR=${BUILD_NR:-"Missing buildnr"}
ENV SPYNL_BUILD_TIME=${BUILD_TIME:-"Missing time"}
ENV SPYNL_PRINTQ_AWS_ACCESS_KEY_ID=${PRINTQ_S3_KEY:-""}
ENV SPYNL_PRINTQ_AWS_SECRET_ACCESS_KEY=${PRINTQ_S3_SECRET:-""}
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
ENV SPYNL_PRETTY=0
ENV SPYNL_DOMAIN=swcloud.nl
ENV SPYNL_MONGO_SSL=false
ENV SPYNL_LOGGING_LEVEL=WARN
ENV SENTRY_API_KEY=""
ENV SWAPI_USAGE_PLAN=""
ENV EMAIL_HOST=email-smtp.eu-west-1.amazonaws.com
ENV REDSHIFT_MAX_CONNECTIONS=100
ENV SALES_EMAIL=sales@softwear.nl
ENV MARKETING_EMAIL=marketing@softwear.nl
ENV FINANCE_EMAIL=finance@softwear.nl
ENV WEB_CONCURRENCY=2
ENV SPYNL_PAY_NL_IP_WHITELIST=85.158.206.20

ADD . application
WORKDIR application

# RUN cd /usr/lib/python3/dist-packages/gi && \
#     ln -s _gi.cpython-36m-x86_64-linux-gnu.so _gi.cpython-37m-x86_64-linux-gnu.so

# NOTE setuptools workaround, needed to be able to use spynl-cli in a global install. 
ENV SETUPTOOLS_USE_DISTUTILS=stdlib

RUN /application/scripts/generate_env.sh /application/spynl_env

RUN python3.8 -m pip install --upgrade pip setuptools && \
        python3.8 -m pip install -r requirements.txt
RUN spynl-cli dev versions
RUN spynl-cli dev translate
RUN spynl-cli services install-fonts

EXPOSE 6543 80

CMD ["/application/scripts/run.sh"]
