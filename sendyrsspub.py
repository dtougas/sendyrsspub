"""
    :copyright: (c) 2015-2018 Damien Tougas
    :license: MIT, see LICENSE.txt for more details

"""
import argparse
import pprint
import sqlite3
import sys

import feedparser
from jinja2 import Environment, FileSystemLoader
import requests

from settings import DEFAULTS


class SendyRSSPublisher(object):
    def __init__(self, sendy_url, sendy_api_key, feed_url, feed_log):
        self.sendy_url = sendy_url
        self.sendy_api_key = sendy_api_key
        self.feed_url = feed_url
        self.feed_log = feed_log
        self.template_env = Environment(loader=FileSystemLoader('templates'))

    def parse_feed(self):
        return feedparser.parse(self.feed_url)

    def log_feed_data(self, data):
        for idx, entry in enumerate(data.entries):
            self.feed_log.add(entry['id'])

    def prune_feed_data(self, data):
        new_entries = []
        for idx, entry in enumerate(data['entries']):
            if not self.feed_log.exists(entry['id']):
                new_entries.append(entry)
        data['entries'] = new_entries
        return data

    def render_string_template(self, string_template, data):
        template = self.template_env.from_string(string_template)
        return self.render_template(template, data)

    def render_file_template(self, template_name, data):
        template = self.template_env.get_template(template_name)
        return self.render_template(template, data)

    def render_template(self, template, data):
        if len(data['entries']) == 0:
            return None
        return template.render(**data)

    def render_and_send(self, from_name, from_email, reply_to, subject_template,
                        plain_template, html_template, data, list_ids):
        if len(data['entries']) == 0:
            return
        subject = self.render_string_template(subject_template, data)
        plain_text = self.render_file_template(plain_template, data)
        html_text = self.render_file_template(html_template, data)
        return self.send(from_name, from_email, reply_to, subject,
                         plain_text, html_text, list_ids)

    def send(self, from_name, from_email, reply_to, subject, plain_text,
             html_text, list_ids):
        post_data = {
            'api_key': self.sendy_api_key,
            'from_name': from_name,
            'from_email': from_email,
            'reply_to': reply_to,
            'subject': subject,
            'plain_text': plain_text,
            'html_text': html_text,
            'list_ids': list_ids,
            'send_campaign': 1
        }
        path_prefix = ''
        if not self.sendy_url.endswith('/'):
            path_prefix = '/'
        url = '%s%s/api/campaigns/create.php' % (self.sendy_url, path_prefix)
        r = requests.post(url, data=post_data)
        if not r.status_code == 200 or \
                not r.text == 'Campaign created and now sending':
            raise Exception('ERROR: Status %s: %s' % (r.status_code, r.text))


class SQLiteFeedLog(object):
    def __init__(self, file_name, feed_url):
        self.feed_url = feed_url
        self.conn = sqlite3.connect(file_name)
        self.cursor = self.conn.cursor()
        q = self.cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name='feed_log'
            """)
        if not q.fetchone():
            self.cursor.execute(
                "CREATE TABLE feed_log (feed_url text, entry_id text)")
            self.conn.commit()

    def add(self, entry_id):
        if self.exists(entry_id):
            return
        parameters = (self.feed_url, str(entry_id))
        self.cursor.execute("INSERT INTO feed_log VALUES (?, ?)", parameters)
        self.conn.commit()

    def remove(self, entry_id):
        if not self.exists(entry_id):
            return
        parameters = (self.feed_url, str(entry_id))
        self.cursor.execute(
            "DELETE FROM feed_log WHERE feed_url=? AND entry_id=?",
            parameters)
        self.conn.commit()

    def prune(self, remainder=10):
        parameters = (self.feed_url, remainder)
        self.cursor.execute("""
          DELETE
          FROM feed_log
          WHERE feed_url=?
          AND oid NOT IN (
            SELECT oid
            FROM feed_log
            ORDER BY oid DESC
            LIMIT ?
          )
          """, parameters)
        self.conn.commit()

    def clear(self):
        parameters = (self.feed_url,)
        self.cursor.execute(
            "DELETE FROM feed_log WHERE feed_url=?", parameters)
        self.conn.commit()

    def exists(self, entry_id):
        parameters = (self.feed_url, str(entry_id))
        q = self.cursor.execute(
            "SELECT entry_id FROM feed_log WHERE feed_url=? AND entry_id=?",
            parameters)
        if not q.fetchone():
            return False
        return True

    def close(self):
        self.conn.close()


class CommandProcessor(argparse.Namespace):
    def __init__(self, **kwargs):
        self._rss_publisher = None
        self._template_names = None
        super(CommandProcessor, self).__init__(**kwargs)

    def setup(self):
        if not hasattr(self, 'feed_url') or not self.feed_url:
            raise Exception('ERROR: feed-url not set')
        if not self.database:
            raise Exception('ERROR: database not set')
        feed_log = SQLiteFeedLog(self.database, self.feed_url)
        self._rss_publisher = SendyRSSPublisher(
            sendy_url=self.sendy_url,
            sendy_api_key=self.sendy_api_key,
            feed_url=self.feed_url,
            feed_log=feed_log
        )

    def process(self):
        self.setup()
        getattr(self, self.cmd)()

    def _get_data(self):
        data = self._rss_publisher.parse_feed()
        if not self.all:
            data = self._rss_publisher.prune_feed_data(data)
        return data

    def _parse_template_names(self):
        if not self.template:
            raise Exception('ERROR: template not set')
        template_list = self.template.split(',')
        templates = {}
        for template in template_list:
            if template.endswith('.html'):
                templates['html'] = template
            elif template.endswith('.txt'):
                templates['txt'] = template
            else:
                raise Exception('ERROR: Unknown template type: %s' % template)
        self._template_names = templates

    def test_feed(self):
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self._get_data())

    def test_template(self):
        self._parse_template_names()
        for template in self._template_names.values():
            print('---------- %s ----------' % template)
            print(self._rss_publisher.render_file_template(template,
                                                           self._get_data()))

    def send_newsletter(self):
        self._parse_template_names()
        if not self.from_name:
            raise Exception('ERROR: From name not set')
        if not self.from_email:
            raise Exception('ERROR: From email not set')
        if not self.reply_to:
            raise Exception('ERROR: Reply-to not set')
        if not self.subject:
            raise Exception('ERROR: Subject not set')
        if not 'txt' in self._template_names.keys():
            raise Exception('ERROR: No plain text template set')
        if not 'html' in self._template_names.keys():
            raise Exception('ERROR: No HTML template set')
        if not self.list_ids:
            raise Exception('ERROR: List IDs not set')
        data = self._get_data()
        self._rss_publisher.render_and_send(
            from_name=self.from_name,
            from_email=self.from_email,
            reply_to=self.reply_to,
            subject=self.subject,
            plain_template=self._template_names['txt'],
            html_template=self._template_names['html'],
            data=data,
            list_ids=self.list_ids
        )
        if not self.disable_log:
            self._rss_publisher.log_feed_data(data)

    def db_clear(self):
        self._rss_publisher.feed_log.clear()

    def db_prune(self):
        self._rss_publisher.feed_log.prune(getattr(self, 'remainder', 10))


def setup_arg_parser():
    parser = argparse.ArgumentParser(prog='sendyrsspub.py')
    #
    # Root level parser
    #
    parser.add_argument(
        '-d', '--database',
        default=DEFAULTS.get('database', None),
        help='feed log database location'
    )
    parser.add_argument(
        '-u', '--sendy-url',
        default=DEFAULTS.get('sendy_url', None),
        help='sendy URL'
    )
    parser.add_argument(
        '-k', '--sendy-api-key',
        default=DEFAULTS.get('sendy_api_key', None),
        help='sendy API key'
    )
    subparsers = parser.add_subparsers()
    #
    # test_feed command parser
    #
    p_test_feed = subparsers.add_parser(
        'test_feed',
        help='output parsed RSS feed data'
    )
    p_test_feed.add_argument(
        '-f', '--feed-url',
        help='url of the RSS feed',
        default=DEFAULTS.get('feed_url', None)
    )
    p_test_feed.add_argument(
        '-a', '--all',
        action='store_true',
        default=False,
        help='all feed data (i.e. ignore the feed log)'
    )
    p_test_feed.set_defaults(cmd='test_feed')
    #
    # Parser for the test_template command
    #
    p_test_template = subparsers.add_parser(
        'test_template',
        help='output processed newsletter template'
    )
    p_test_template.add_argument(
        '-f', '--feed-url',
        default=DEFAULTS.get('feed_url', None),
        help='url of the RSS feed'
    )
    p_test_template.add_argument(
        '-t', '--template',
        default=DEFAULTS['template'],
        help='template file name(s) (comma separated)'
    )
    p_test_template.add_argument(
        '-a', '--all',
        action='store_true',
        default=False,
        help='all feed data (i.e. ignore the feed log)'
    )
    p_test_template.set_defaults(cmd='test_template')
    #
    # Parser for the send newsletter command
    #
    p_send_newsletter = subparsers.add_parser(
        'send_newsletter',
        help='send a newsletter'
    )
    p_send_newsletter.add_argument(
        '-f', '--feed-url',
        default=DEFAULTS.get('feed_url', None),
        help='url of the RSS feed'
    )
    p_send_newsletter.add_argument(
        '-t', '--template',
        default=DEFAULTS.get('template', None),
        help='template file name(s) (comma separated)'
    )
    p_send_newsletter.add_argument(
        '-n', '--from-name',
        default=DEFAULTS['from_name'],
        help='from name'
    )
    p_send_newsletter.add_argument(
        '-e', '--from-email',
        default=DEFAULTS['from_email'],
        help='from email'
    )
    p_send_newsletter.add_argument(
        '-r', '--reply-to',
        default=DEFAULTS['reply_to'],
        help='reply-to email'
    )
    p_send_newsletter.add_argument(
        '-s', '--subject',
        default=DEFAULTS['subject'],
        help='newsletter subject'
    )
    p_send_newsletter.add_argument(
        '-l', '--list-ids',
        default=DEFAULTS['list_ids'],
        help='list IDs (comma separated)'
    )
    p_send_newsletter.add_argument(
        '-a', '--all',
        action='store_true',
        default=False,
        help='all feed data (i.e. ignore the feed log)'
    )
    p_send_newsletter.add_argument(
        '-d', '--disable-log',
        action='store_true',
        default=False,
        help='do not register items as processed in the feed log'
    )
    p_send_newsletter.set_defaults(cmd='send_newsletter')
    #
    # Parser for the db_clear command
    #
    p_db_clear = subparsers.add_parser(
        'db_clear',
        help='clean all entries in the feed log database'
    )
    p_db_clear.add_argument(
        '-f', '--feed-url',
        default=DEFAULTS.get('feed_url', None),
        help='url of the RSS feed'
    )
    p_db_clear.set_defaults(cmd='db_clear')
    #
    # Parser for the db_prune command
    #
    p_db_prune = subparsers.add_parser(
        'db_prune',
        help='prune oldest entries from the feed log'
    )
    p_db_prune.add_argument(
        '-f', '--feed-url',
        default=DEFAULTS.get('feed_url', None),
        help='url of the RSS feed'
    )
    p_db_prune.add_argument(
        '-r', '--remainder',
        help='number of entries to remain in the feed log (default is 10)'
    )
    p_db_prune.set_defaults(cmd='db_prune')
    return parser


if __name__ == '__main__':
    parser = setup_arg_parser()
    command_processor = CommandProcessor()
    parser.parse_args(sys.argv[1:], namespace=command_processor)
    try:
        command_processor.process()
    except Exception as ex:
        print(str(ex))
        sys.exit(1)
