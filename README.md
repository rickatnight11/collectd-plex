# collectd-plex

A Plex plugin for [collectd](https://collectd.org/). It can collect such
metrics as library size (movies, shows, episodes) and active sessions.

## Requirements

* Plex.tv authentication token (see included `get_auth_token.py` script)
* Plex Media Server
* CollectD `python` plugin

## Configuration

**Required:**

* `Host` - Plex server hostname
* `Port` - Plex server port
* `AuthToken` - Plex.tv authentication token

**Optional:**
* `HTTPS` - use HTTPS instead of HTTP (defaults to `True`)
* `Sessions` - collect active session count (defaults to `True`)
* `Movies` - collect movie counts (defaults to `True`)
* `Shows` - collect show counts (defaults to `True`)
* `Episodes` - collect episode counts (defaults to `True`)
* `MyPlex` - collect remote access status (defaults to `False`)
* `Include` - sections to collect media counts for (assumes all, if excluded)
* `Exclude` - sections to ignore media counts for (assumes all, if excluded)

## Usage

This plugin will, by default, collect all metrics it can from the Plex server
by looking for all libraries/sections.  You can tune/limit this behavior with
the **Optional** parameters defined above, if you only want to collect a
certain kind of metric or are only interested in a subset of sections/libraries.

## Examples

### Collect all metrics from Plex server

This configuration will query the Plex server for all libraries and collect
all metrics.

```
<LoadPlugin python>
  Globals true
</LoadPlugin>

<Plugin python>
  ModulePath "/path/to/plugin"
  Import "plex"

  <Module plex>
    Host "localhost"
    Port 32400
    AuthToken <token>
  </Module>

</Plugin>
```

### Collect show and episode count from a single library

Assuming section `1` is a `show` library, this configuration will limit the
collection to just that library, which will result in show and episode count
being collected.

```
<LoadPlugin python>
  Globals true
</LoadPlugin>

<Plugin python>
  ModulePath "/path/to/plugin"
  Import "plex"

  <Module plex>
    Host "localhost"
    Port 32400
    AuthToken <token>
    IncludeSections 1
  </Module>

</Plugin>
```

### Collect Remote Access status

This configuration will monitor all metrics, plus Remote Access (MyPlex/Plex.tv) status.

```
<LoadPlugin python>
  Globals true
</LoadPlugin>

<Plugin python>
  ModulePath "/path/to/plugin"
  Import "plex"

  <Module plex>
    Host "localhost"
    Port 32400
    AuthToken <token>
    MyPlex true
  </Module>

</Plugin>
```

Reported values will be:

| Value | Meaning                                                |
|-------|--------------------------------------------------------|
| -1    | Error (not logged in to Plex account on the server?)   |
| 0     | Unreachable                                            |
| 1     | Waiting (server is trying to connect to Remote Access) |
| 2     | Reachable                                              |