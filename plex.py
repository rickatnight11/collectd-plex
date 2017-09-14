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
    if not (CONFIG.movies or CONFIG.shows or CONFIG.episodes or CONFIG.sessions or CONFIG.myplex):
        errormessage('No metrics configured to be collected!')

    # Collect media size metrics
    if CONFIG.movies or CONFIG.shows or CONFIG.episodes:
        sections = get_sections()

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
        metrics.extend(get_sessions())

    # Collect MyPlex metrics
    if CONFIG.myplex:
        metrics.extend(get_remote_reachability())

    if len(metrics) == 0:
        errormessage('No metrics collected!  Something is wrong!')

    # Handle metrics accordingly
    for metric in metrics:
        if collectd is True:
            # Dispatch metrics back to collectd
            dispatch_value(metric['instance'], CONFIG.servername, metric['value'])
        else:
            # Print metrics in interactive mode
            print({
                'value': metric['value'],
                'type_instance': metric['instance'],
                'plugin_instance': CONFIG.servername,
                'full_name': 'plex-{0}.{1}.value'.format(CONFIG.servername,
                                                       metric['instance'])
            })

def api_request(path, structure='json'):
    '''Return JSON/XML object from requested PMS path'''

    if CONFIG.https:
        protocol = 'https'
    else:
        protocol = 'http'

    url = '{protocol}://{host}:{port}{path}'.format(protocol=protocol,
                                                    host=CONFIG.host,
                                                    port=CONFIG.port,
                                                    path=path)

    if structure == 'json':
        return get_json(url, CONFIG.authtoken)
    elif structure == 'xml':
        return get_xml(url, CONFIG.authtoken)
    else:
        errormessage('Unknown structure: ' + str(structure))
        return False


def get_server_name():
    '''Pull basic server details from PMS'''

    server = api_request('/')

    # Old PMS < 1.2.6 schema
    if 'friendlyName' in server:
        return server['friendlyName']
    # Newer PMS 1.2.6+ schema
    elif 'MediaContainer' in server:
        return server['MediaContainer']['friendlyName']
    # Unknown format
    else:
        errormessage('Unknown server detail format!')
        return False

def get_remote_reachability():
    '''Pull remote reachability (plex.tv) status from PMS'''

    server = api_request('/myplex/account')

    metrics = []
    state = -1

    try:
        if server['MyPlex']['mappingState'] == 'mapped':
            # Anything different from 'unreachable' is valid
            if server['MyPlex']['mappingError'] != 'unreachable':
                state = 2
            else:
                state = 0
        elif server['MyPlex']['mappingState'] == 'waiting':
            # Currently estabilishing connection
            state = 1
        elif server['MyPlex']['mappingState'] == 'unknown':
            # No specific info provided by server, assume unreachable
            state = 0
        else:
            state = 0
    except KeyError:
        errormessage('Missing MyPlex field, probably not signed in?')
        state = -1

    metrics.append({'instance': 'remote-reachability',
                    'value': state})
    return metrics


def get_sections():
    '''Pull sections from PMS'''

    sectionobject = api_request('/library/sections')

    apimatched = False

    # Old PMS < 1.2.6 schema
    if '_children' in sectionobject:
        apimatched = True
        api_sections = sectionobject['_children']
    # Newer PMS 1.2.6+ schemas
    elif 'MediaContainer' in sectionobject:
        # PMS 1.3.0 schema
        if 'Metadata' in sectionobject['MediaContainer']:
            apimatched = True
            api_sections = sectionobject['MediaContainer']['Metadata']
        # PMS 1.3.2 schema
        elif 'Directory' in sectionobject['MediaContainer']:
            apimatched = True
            api_sections = sectionobject['MediaContainer']['Directory']

    # Parse sections
    if apimatched:
        sections = {}
        for section in api_sections:
            sections[section['key']] = section
        return sections

    # Unknown format
    errormessage('PMS API returned unexpected format from "/library/sections"')
    return False


def get_section(section):
    '''Return json object of PMS library section'''
    return api_request('/library/sections/{0}/all'.format(section))


def get_movies_metric(section):
    '''Return number of movies in section'''

    return {'instance': 'movies-{0}'.format(section),
            'value': sum_videos(get_section(section))}


def get_shows_metrics(section, shows, episodes):
    '''Return number of shows and/or episodes'''

    metrics = []

    if not (shows or episodes):
        warningmessage('Must request number of shows and/or episodes!')
    sectionobject = get_section(section)
    if shows:
        metrics.append({'instance': 'shows-{0}'.format(section),
                        'value': sum_videos(sectionobject, False)})
    if episodes:
        metrics.append({'instance': 'episodes-{0}'.format(section),
                        'value': sum_videos(sectionobject, True)})
    return metrics


def get_sessions():

    try:
        import xml.etree.ElementTree as ET
    except Exception as e:
        errormessage('Failed to import ElementTree Python module!')
        return False

    sessionsobject = api_request('/status/sessions', structure='xml')

    metrics = []

    # Count active/inactive sessions
    active = 0
    inactive = 0

    # Parse XML response into ElementTree object
    try:
        root = ET.fromstring(sessionsobject)
    except Exception as e:
        errormessage('Failed to parse XML!')
        return False

    # Enumerate sessions
    for player in root.iter('Player'):
        if 'state' in player.attrib:
            if player.attrib['state'] == 'playing':
                active += 1
            else:
                inactive += 1
        inactive += 1

    # Construct session metrics
    metrics.append({'instance': 'sessions-total',
                    'value': active + inactive})

    metrics.append({'instance': 'sessions-active',
                    'value': active})
    metrics.append({'instance': 'sessions-inactive',
                    'value': inactive})

    return metrics


def get_json(url, authtoken):
    headers = {
               'Accept': 'application/json',
               'X-Plex-Token': authtoken
              }
    r = requests.get(url, headers=headers, verify=False)
    try:
        json_object = r.json()
        return r.json()
    except:
        errormessage('Failed to parse JSON!')
        return False


def get_xml(url, authtoken):
    headers = {
               'X-Plex-Token': authtoken
              }
    r = requests.get(url, headers=headers, verify=False)
    return r.text


def sum_videos(section, sum_leaf=False):

    # Old PMS < 1.2.6 schema
    if '_children' in section:
        if sum_leaf:
            return sum(c['leafCount'] for c in section['_children'])
        return len(section['_children'])
    # Newer PMS 1.2.6+ schema
    elif 'MediaContainer' in section:
        if sum_leaf:
            return sum(c['leafCount'] for c in section['MediaContainer']['Metadata'])
        return len(section['MediaContainer']['Metadata'])
    # Unknown format
    else:
        errormessage('Unknown section format!')
        return False


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
        '--myplex',
        action='store_true',
        help='Collect remote (plex.tv) reachability')
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
        conf = parser.parse_args(collectdconfig)
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
        myplex = False
        include = []
        exclude = []
        # Convert collectd module parameters
        for node in conf.children:
            key = node.key.lower()
            if key == 'include':
                for section in node.values:
                    include.append(str(int(section)))
                    continue
            elif key == 'exclude':
                for section in node.values:
                    exclude.append(str(int(section)))
                    continue
            else:
                val = node.values[0]
                if key == 'host':
                    host = val
                elif key == 'port':
                    port = str(int(val))
                elif key == 'authtoken':
                    authtoken = val
                elif key == 'https':
                    https = val
                elif key == 'sessions':
                    sessions = val
                elif key == 'movies':
                    movies = val
                elif key == 'shows':
                    shows = val
                elif key == 'episodes':
                    episodes = val
                elif key == 'myplex':
                    myplex = val
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
        collectdconfig = [host,
                        port,
                        authtoken]
        if https:
            collectdconfig.append('--https')
        if sessions:
            collectdconfig.append('--sessions')
        if movies:
            collectdconfig.append('--movies')
        if shows:
            collectdconfig.append('--shows')
        if episodes:
            collectdconfig.append('--episodes')
        if myplex:
            collectdconfig.append('--myplex')

        if len(include) > 0:
            collectdconfig.append('--include')
            collectdconfig.extend(include)
        if len(exclude) > 0:
            collectdconfig.append('--exclude')
            collectdconfig.extend(exclude)
        global CONFIG
        CONFIG = parse_config(collectdconfig)
        infomessage('configured with ' + str(CONFIG))

    # Register configuration callback
    collectd.register_config(configure_callback)
    # Register read callback
    collectd.register_read(get_metrics)
