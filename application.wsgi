import os, sys

PROJECT_DIR = '/var/www/hknewswebscrapper.in/hknewswebscrapper'

sys.path.append(PROJECT_DIR)
sys.path.append('/var/www/hknewswebscrapper.in/hknewswebscrapper/.venv/lib64/python3.6/site-packages')

from hknewswebscrapper import app as application
