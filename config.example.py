import configparser
import os

host = 'zhwiki.analytics.db.svc.eqiad.wmflabs'

reader = configparser.ConfigParser()
reader.read(os.path.expanduser('~/replica.my.cnf'))
user = reader.get('client', 'user')
password = reader.get('client', 'password')

config_page_name = 'User:Xiplus-abot/task/6/config.json'
