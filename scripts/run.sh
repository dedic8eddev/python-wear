#!/bin/bash

# Helper function for substituting environmental variables into a file.
# It's your job to redirect stdout to a file.
render () {
    . /spynl_env
    python3 -c "import os; f = open('$1').read(); print(os.path.expandvars(f))"
}


# Prepend the environment to the domain if not in production.
# For example test.softwearconnect.nl
case "$SPYNL_ENVIRONMENT" in
    dev | edge | test | beta )
    SPYNL_DOMAIN="$SPYNL_ENVIRONMENT"."$SPYNL_DOMAIN"
    ;;
esac

export SPYNL_2FA_ISSUER="SoftwearConnect"
export SPYNL_2FA_JWT_SECRET=$(uuid)
case "$SPYNL_ENVIRONMENT" in
    dev | edge | test )
    SPYNL_2FA_ISSUER="$SPYNL_2FA_ISSUER $SPYNL_ENVIRONMENT"
    ;;
esac

# If the mail domain is not set use our defaults.
if [ -z "$SPYNL_MAIL_DOMAIN" ]; then
    case "$SPYNL_ENVIRONMENT" in
        # This is on sentia's side.
        beta | production )
            SPYNL_MAIL_DOMAIN=softwearconnect.com
            ;;
        edge | test )
            SPYNL_MAIL_DOMAIN="$SPYNL_ENVIRONMENT".softwearconnect.com
            ;;
        * )
            SPYNL_MAIL_DOMAIN=dev.swcloud.nl
            ;;
    esac
fi
export SPYNL_MAIL_DOMAIN

case "$SPYNL_ENVIRONMENT" in
    edge | test | e2e )
        # Do not spam sales and marketing in dev and test
        SALES_EMAIL=softweardev@gmail.com
        MARKETING_EMAIL=softweardev@gmail.com
        FINANCE_EMAIL=softweardev@gmail.com
        # Also return pretty responses.
        SPYNL_PRETTY=1
        ;;
esac

case "$SPYNL_ENVIRONMENT" in
    edge | test | beta | production )
        SPYNL_LOGGING_LEVEL=WARN
        ;;
    * )
        SPYNL_LOGGING_LEVEL=DEBUG
        ;;
esac
export SPYNL_LOGGING_LEVEL

# Render the production.ini with the environmental variables.
echo "[PRODUCTION.INI]"
render /application/scripts/config/production.ini.template | tee production.ini

# Setup the command for superviserd to run.
COMMAND="gunicorn --paste $PWD/production.ini --config /application/scripts/config/gunicorn.conf.py"

# Run supervisord.
cp /application/scripts/config/supervisord.conf /etc/supervisord.conf
echo "command=""$COMMAND" >> /etc/supervisord.conf
supervisord --nodaemon -c /etc/supervisord.conf
