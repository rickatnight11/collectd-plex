#!/usr/bin/env python

from __future__ import print_function

import argparse
import sys
import requests

CONFIG = None

def dispatch_value(type_instance, plugin_instance, value):
    '''Dispatch metric to collectd'''
    val = collectd.Values(plugin='plex',
                          type='gauge',
                          type_instance=type_instance,
                          plugin_instance=plugin_instance,
                          values = [value])
    val.dispatch()


def get_metrics(collectd=True):
    '''Collect requested metrics and handle appropriately'''

    metrics = []

    # Get PMS name
    CONFIG.servername = get_server_name()

    # Check for metric to collect
    if not (CONFIG.movies or CONFIG.shows or CONFIG.episodes or CONFIG.sessions):
        errormessage('No metrics configured to be collected!')

    # Collect media size metrics
    if CONFIG.movies or CONFIG.shows or CONFIG.episodes:
        sections = get_sections()
        #print(section['key'] + " " + section['title'] + " - " + section['type'])
        # (value, data) = get_media_count(conf)

        # Filter included sections, if specified
        if len(CONFIG.include) > 0:
            filteredsections = {}
            for section in CONFIG.include:
                if section in sections.keys():
                    filteredsections[section] = sections[section]
                else:
                    warnmessage('Requested section {0} not found on PMS!'.format(section))
        else:
            filteredsections = sections.keys()

        for section in filteredsections:
            # Filter out excluded sections
            if section in CONFIG.exclude:
                continue
            # Filter movie sections
            if sections[section]['type'] == 'movie' and CONFIG.movies:
                metrics.append(get_movies_metric(section))
            # Filter show sections
            elif sections[section]['type'] == 'show' and (CONFIG.shows or CONFIG.episodes):
                metrics.extend(get_shows_metrics(section, CONFIG.shows, CONFIG.episodes))


    # Collect session metrics
    if CONFIG.sessions:
        metrics.append(get_sessions())

    #plugin_instance = get_plugin_instance(conf)
    #type_instance = get_type_instance(data, conf)

    if len(metrics) == 0:
        errormessage('No metrics collected!  Something is wrong!')
    else:
        print(metrics)
    sys.exit(1)

    if collectd is True:
        # Dispatch metrics back to collectd
        dispatch_value(type_instance, plugin_instance, value)
    else:
        # Print metrics in interactive mode
        print({
            'value': value,
            'type_instance': type_instance,
            'plugin_instance': plugin_instance,
            'full_name': 'plex-{}.{}.value'.format(plugin_instance,
                                                   type_instance)
        })

def api_request(path):
    '''Return JSON object from requested PMS path'''

    if CONFIG.https:
        protocol = 'https'
    else:
        protocol = 'http'

    url = '{protocol}://{host}:{port}{path}'.format(protocol=protocol,
                                                    host=CONFIG.host,
                                                    port=CONFIG.port,
                                                    path=path)

    return get_json(url, CONFIG.authtoken)


def get_server_name():
    '''Pull basic server details from PMS'''

    server = api_request('/')
    return server['friendlyName']


def get_sections():
    '''Pull sections from PMS'''

    sectionobject = api_request('/library/sections')

    if not sectionobject.has_key('_children'):
        warnmessage('PMS API returned unexpected format from "/library/sections"')
        return False
    else:
        sections = {}
        for section in sectionobject['_children']:
            sections[section['key']] = section
        return sections


def get_section(section):
    '''Return json object of PMS library section'''
    return api_request('/library/sections/{}/all'.format(section))


def get_movies_metric(section):
    '''Return number of movies in section'''

    return {'type': 'movies',
            'section': section,
            'value': sum_videos(get_section(section))}
    

def get_shows_metrics(section, shows, episodes):
    '''Return number of shows and/or episodes'''

    metrics = []

    if not (shows or episodes):
        warningmessage('Must request number of shows and/or episodes!')
    sectionobject = get_section(section)
    if shows:
        metrics.append({'type': 'shows',
                        'section': section,
                        'value': sum_videos(sectionobject, False)})
    if episodes:
        metrics.append({'type': 'episodes',
                        'section': section,
                        'value': sum_videos(sectionobject, True)})
    return metrics


def get_sessions():

    sessionsobject = api_request('/status/sessions')

    return {'type': 'sessions',
            'value': sum_sessions(sessionsobject)}

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


def sum_videos(section, sum_leaf=False):
    if sum_leaf:
        return sum(c['leafCount'] for c in section['_children'])
    return len(section['_children'])

def sum_sessions(data):
    return len(data['_children'])


def parse_config(collectdconfig=None):

    # Handle arguments
    parser = argparse.ArgumentParser(
        description='Collect metrics from Plex Media Server.')
    parser.add_argument(
        'host',
        metavar='<HOSTNAME>',
        help='PMS hostname')
    parser.add_argument(
        'port',
        metavar='<PORT>',
        type=int,
        help='PMS port')
    parser.add_argument(
        'authtoken',
        metavar='<AUTH_TOKEN>',
        help='plex.tv authentication token')
    parser.add_argument(
        '--https',
        action='store_true',
        help='Use HTTPS instead of HTTP')
    parser.add_argument(
        '--sessions',
        action='store_true',
        help='Collect session count')
    parser.add_argument(
        '--movies',
        action='store_true',
        help='Collect movie count(s)')
    parser.add_argument(
        '--shows',
        action='store_true',
        help='Collect show count(s)')
    parser.add_argument(
        '--episodes',
        action='store_true',
        help='Collect episode count(s)')
    parser.add_argument(
        '-i', '--include',
        nargs='+',
        default=[],
        metavar='SECTION',
        help='section(s) to collect from')
    parser.add_argument(
        '-e', '--exclude',
        nargs='+',
        default=[],
        metavar='SECTION',
        help='section(s) to exclude collecting from')

    if collectdconfig is None:
        conf = parser.parse_args()
    else:
        conf = parser.parse_args(config)

    return conf


# Called interactively
if __name__ == '__main__':

    # Define poor-man's messaging bus for printing
    def infomessage(message):
        print(message)
    def warnmessage(message):
        print(message)
    def errormessage(message):
        print(message)
        sys.exit(1)

    # Handle commandline arguments
    CONFIG = parse_config()

    # Get metrics interactively
    get_metrics(collectd=False)

# Called from collectd
else:

    import collectd

    # Define poor-man's messaging bus for collectd messaging
    def infomessage(message):
        collectd.info('plex plugin: ' + message)
    def warnmessage(message):
         collectd.warning('plex plugin: ' + message)
    def errormessage(message): 
        collectd.error('plex plugin: ' + message)
        sys.exit(1)

    # Configuration callback for collectd
    def configure_callback(conf):
        '''Handle collectd module parameters'''

        # Initial/default parameters
        host = None
        port = None
        authtoken = None
        https = True
        sessions = True
	movies = True
	shows = True
	episodes = True
	include = []
	exclude = []

        # Convert collectd module parameters
	for node in conf.children:
	    key = node.key.lower()
	    val = node.values[0]

            if key == 'host':
	        host = val
	    elif key == 'port':
	        port = int(val)
	    elif key == 'authtoken':
	        authtoken = val
	    elif key == 'https':
	        https = val
	    elif key == 'sessions':
	        sessions = val,
	    elif key == 'movies':
	        movies = val,
	    elif key == 'shows':
	        shows = val,
	    elif key == 'episodes':
	        episodes = val,
	    elif key == 'include':
	        include = val,
	    elif key == 'exclude':
	        exclude = val,
	    else:
	        warnmessage(' Unknown config key: %s.' % key)
	        continue

        # Enforce required parameters
        if host is None:
            errormessage('Missing "Host" parameter!')
        if port is None:
            errormessage('Missing "Port" parameter!')
        if authtoken is None:
            errormessage('Missing "AuthToken" parameter!')

        config = [
            host,
            port,
            authtoken,
            '--https', https,
            '--sessions', sessions,
            '--movies', movies,
            '--shows', shows,
            '--episodes', episodes,
            '--include'
        ]

        config.extend(include)
        config.appent('--exclude')
        config.extend(exclude)

        CONFIG = parse_config(config)


    # Register configuration callback
    collectd.register_config(configure_callback)

    # Register read callback
    collectd.register_read(get_metrics)
