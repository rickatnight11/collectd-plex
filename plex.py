#!/usr/bin/env python

from __future__ import print_function

import sys
import requests

CONFIGS = []


def configure_callback(conf):
    host = None
    port = None
    metric = None
    section = None
    instance = None
    authtoken = None

    for node in conf.children:
        key = node.key.lower()
        val = node.values[0]

        if key == 'host':
            host = val
        elif key == 'port':
            port = int(val)
        elif key == 'metric':
            metric = val
        elif key == 'section':
            section = str(int(val))
        elif key == 'authtoken':
            authtoken = val
        else:
            warnmessage(' Unknown config key: %s.' % key)
            continue

    config = {
        'host': host,
        'port': port,
        'authtoken': authtoken,
        'metric': metric,
        'section': section
    }

    infomessage('Configured with {}'.format(config))
    CONFIGS.append(config)


def read_callback():
    for conf in CONFIGS:
        get_metrics(conf)


def dispatch_value(type_instance, plugin_instance, value):
    val = collectd.Values(plugin='plex')
    val.type = 'gauge'
    val.type_instance = type_instance
    val.plugin_instance = plugin_instance
    val.values = [value]
    val.dispatch()


def get_metrics(conf, callback=None):

    if conf['metric'] in ['movies', 'shows', 'episodes']:
        if conf['section'] is None:
            errormessage('Must provide section number to find media count!')
        (value, data) = get_media_count(conf)
    elif conf['metric'] in ['sessions']:
        (value, data) = get_sessions(conf) 
    else:
        errormessage('Unknown metric type: {0}'.format(conf['metric']))

    plugin_instance = get_plugin_instance(conf)
    type_instance = get_type_instance(data, conf)

    if callback is None:
        dispatch_value(type_instance, plugin_instance, value)
    else:
        callback(type_instance, plugin_instance, value)

def get_media_count(conf):

    url = 'http://{host}:{port}/library/sections/{section}/all'.format(host=conf['host'],
                                                                       port=conf['port'],
                                                                       section=conf['section'])

    data = get_json(url, conf['authtoken'])
    validate_media_type(conf['section'], data['librarySectionTitle'], conf['metric'], data['viewGroup'])

    if conf['metric'] in ['movies', 'shows']:
    	count = sum_videos(data, False)
    elif conf['metric'] in ['episodes']:
        count = sum_videos(data, True)

    return (count, data)

def validate_media_type(section, title, metric, media):

    mapping = {'movies': 'movie',
               'shows': 'show',
               'episodes': 'show'}

    if mapping[metric] != media:
        errormessage('Section #{0} ({1}) contains {2}s. Does not match metric, {3}!'.format(section,
                                                                                            title,
                                                                                            media,
                                                                                            metric))
        sys.exit(1)
    else:
        return True


def get_sessions(conf):

    url = 'http://{host}:{port}/status/sessions'.format(
        host=conf['host'],
        port=conf['port'],
        section=conf['section']
    )

    data = get_json(url, conf['authtoken'])
    count = sum_sessions(data)

    return (count, data)

def get_plugin_instance(conf):
    return conf['host']


def get_type_instance(data, conf):

    if conf['metric'] == 'sessions':
        return 'sessions'
    elif conf['metric'] in ['movies', 'shows', 'episodes']:
        if conf['section'] is None:
            return conf['metric']+'-all'
        else:
            return conf['metric']+'-'+conf['section']


def get_json(url, authtoken):
    headers = {
               'Accept': 'application/json',
               'X-Plex-Token': authtoken
              }
    r = requests.get(url, headers=headers)
    return r.json()


def sum_videos(data, sum_leaf=False):
    if sum_leaf:
        return sum(c['leafCount'] for c in data['_children'])
    return len(data['_children'])

def sum_sessions(data):
    return len(data['_children'])


def main():
    if (len(sys.argv) < 5) or (len(sys.argv) > 6):
        infomessage('{} <host> <port> <authtoken> <metric> [<section>]'.format(sys.argv[0]))
        infomessage('Metrics:')
        infomessage('- movies')
        infomessage('- shows')
        infomessage('- episodes')
        errormessage('- sessions')
    section = sys.argv[5] if len(sys.argv) == 6 else None
    conf = {
        'host': sys.argv[1],
        'port': sys.argv[2],
        'authtoken': sys.argv[3],
        'metric': sys.argv[4],
        'section': section
    }

    def callback(type_instance, plugin_instance, value):
        print({
            'value': value,
            'type_instance': type_instance,
            'plugin_instance': plugin_instance,
            'full_name': 'plex-{}.{}.value'.format(plugin_instance,
                                                   type_instance)
        })
    get_metrics(conf, callback)


if __name__ == '__main__':

    def infomessage(message):
        print(message)
    def warnmessage(message):
        print(message)
    def errormessage(message):
        print(message)
        sys.exit(1)
    main()
else:
    import collectd

    def infomessage(message):
        collectd.info('plex plugin: ' + message)
    def warnmessage(message):
         collectd.warning('plex plugin: ' + message)
    def errormessage(message): 
        collectd.error('plex plugin: ' + message)
        sys.exit(1)

    collectd.register_config(configure_callback)
    collectd.register_read(read_callback)
