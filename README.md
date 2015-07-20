# collectd-plex

A Plex plugin for [collectd](https://collectd.org/).

# Requirements

* Plex.tv authentication token (see included `get_auth_token.py` script)
* Plex Media Server
* CollectD `python` plugin

# Configuration

* `Host` - Plex server hostname
* `Port` - Plex server port
* `AuthToken` - Plex.tv authentication token
* `Metric` - Metric to collect.  Supported metrics:
  * `movies` - number of movies
  * `shows` - number of shows
  * `episodes` - number of episodes
  * `sessions` - number of active sessions/streams
* **Optional:** `Section` - Plex library section to query (must match metric type)

## Examples

```
<LoadPlugin python>
  Globals true
</LoadPlugin>

<Plugin python>
  ModulePath "/path/to/plugin"
  Import "plex"

  # Count all movies in a Movie section
  <Module plex>
    Host "localhost"
    Port 32400
    AuthToken <token>
    Metric movies
    Section 1
  </Module>

  # Count all shows in a TV Show section
  <Module plex>
    Host "localhost"
    Port 32400
    AuthToken <token>
    Metric shows
    Section 2
  </Module>

  # Count all episodes in a TV Show section
  <Module plex>
    Host "localhost"
    Port 32400
    AuthToken <token>
    Metric episodes
    Section 2
  </Module>

  # Count all active sessions
  <Module plex>
    Host "localhost"
    Port 32400
    AuthToken <token>
    Metric sessions
  </Module>

</Plugin>
```
