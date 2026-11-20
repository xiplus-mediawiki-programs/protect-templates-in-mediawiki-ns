#!/usr/bin/env python
# coding: utf-8

import argparse
import json
import os
import re

import pymysql
os.environ['PYWIKIBOT_DIR'] = os.path.dirname(os.path.realpath(__file__))
import pywikibot

from config import config_page_name, host, password, user  # pylint: disable=E0611,W0614

parser = argparse.ArgumentParser()
parser.add_argument('--dry-run', action='store_true', dest='dry_run')
args = parser.parse_args()

site = pywikibot.Site('zh', 'wikipedia')
site.login()

config_page = pywikibot.Page(site, config_page_name)
cfg = config_page.text
cfg = json.loads(cfg)
print(json.dumps(cfg, indent=4, ensure_ascii=False))

if not cfg['enable']:
    print('disabled')
    exit()

conn = pymysql.connect(
    host=host,
    user=user,
    password=password,
    charset="utf8"
)

with conn.cursor() as cur:
    cur.execute('use zhwiki_p')
    cur.execute("""
        SELECT lt_namespace, lt_title, tl_from, page_title
        FROM templatelinks
        LEFT JOIN linktarget ON tl_target_id = lt_id
        LEFT JOIN page ON tl_from = page_id
        WHERE tl_from_namespace = 8 AND lt_namespace != 8
    """)
    res = cur.fetchall()

templates = set()
included_in = {}
for row in res:
    ns = int(row[0])
    title = row[1].decode()
    tl_from = int(row[2])
    from_title = row[3].decode() if row[3] else str(tl_from)
    templates.add((ns, title))
    included_in.setdefault((ns, title), set()).add('MediaWiki:' + from_title.replace('_', ' '))

template_whitelist = set(pywikibot.Page(site, t).title() for t in cfg.get('template_whitelist', []))

titles = []
ignored_titles = []
for (ns, title) in templates:
    page = pywikibot.Page(site, title, ns)
    fulltitle = page.title()
    if fulltitle in template_whitelist or re.search(cfg['template_whiteregex'], fulltitle):
        ignored_titles.append((fulltitle, sorted(included_in[(ns, title)])))
        continue

    titles.append(fulltitle)

titles.sort()
ignored_titles.sort()

text = '\n'
for title in titles:
    # print(title)
    text += '| ' + title + '\n'

page = pywikibot.Page(site, cfg['page'])
try:
    idx1 = page.text.index('<!--listbegins-->') + len('<!--listbegins-->')
    idx2 = page.text.index('<!--listends-->', idx1)
except ValueError:
    print('Cannot locate insertion position')
    exit()

newtext = page.text[:idx1] + text + page.text[idx2:]
if page.text == newtext:
    print('List unchanged')
elif args.dry_run:
    pywikibot.showDiff(page.text, newtext)
else:
    page.text = newtext
    page.save(cfg['summary'])

if cfg.get('ignored_list_page'):
    def format_protection(protection, action):
        if action not in protection:
            return 'none'
        level, expiry = protection[action]
        if expiry != 'infinity':
            return '{}（至 {}）'.format(level, expiry)
        return level

    text = '{| class="wikitable sortable"\n! 頁面 !! 編輯保護 !! 移動保護 !! 嵌入於\n'
    for title, from_titles in ignored_titles:
        ignored_page = pywikibot.Page(site, title)
        protection = ignored_page.protection()
        if ignored_page.exists():
            edit = format_protection(protection, 'edit')
            move = format_protection(protection, 'move')
        else:
            edit = '（未建立）' + format_protection(protection, 'create')
            move = ''
        included = '<br>'.join('[[{}]]'.format(t) for t in from_titles)
        text += '|-\n| [[:{}]] || {} || {} || {}\n'.format(title, edit, move, included)
    text += '|}'

    ignored_list_page = pywikibot.Page(site, cfg['ignored_list_page'])
    if ignored_list_page.text == text:
        print('Ignored list unchanged')
    elif args.dry_run:
        pywikibot.showDiff(ignored_list_page.text, text)
    else:
        ignored_list_page.text = text
        ignored_list_page.save(summary=cfg['ignored_list_summary'], minor=False)
