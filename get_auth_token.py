#!/usr/bin/env python

import httplib, urllib, base64, socket, getpass, json

# Grab user credentials
username = raw_input("plex.tv User: ")
password = getpass.getpass("plex.tv Password: ")

# Form HTTP request
base64string = base64.encodestring('%s:%s' % (username, password)).replace('\n', '')
txdata = ""

headers={'Authorization': "Basic %s" % base64string,
         'X-Plex-Device': "CollectD Plex Plugin",
         'X-Plex-Device-Name': socket.gethostname(),
         'X-Plex-Client-Identifier': "collectd-plex"+socket.gethostname(),
         'X-Plex-Product': "CollectD Plex Plugin",
         'X-Plex-Version': "0.001"}

# Make HTTP request to plex.tv
conn = httplib.HTTPSConnection("plex.tv")
conn.request("POST","/users/sign_in.json",txdata,headers)
response = conn.getresponse()
data = response.read()

# Check response
if response.status != 201:
    print "HTTP Error: " + str(response.status)
    print str(data)
else:
    j = json.loads(str(data))
    print "Plex.tv Auth Token: " + j['user']['authentication_token']
conn.close()
