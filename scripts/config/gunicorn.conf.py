import os

bind = '0.0.0.0:{}'.format(os.environ.get('SPYNL_PORT', '6543'))
workers = os.environ['WEB_CONCURRENCY']
access_logfile = '-'
access_logformat = '%%(t)s %%(U)s %%(s)s %%(m)s %%(h)s'
timeout = 180
max_requests = 1000
