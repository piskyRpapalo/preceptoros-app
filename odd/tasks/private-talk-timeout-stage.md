# Private Talk · classify timeouts by phase

Existing APP Talk already maps `station_probe_timeout` to the connection
stage. A timeout raised during the station tags probe used to reach the
generic classifier as `station_timeout`, which the APP interpreted as model
failure. A timeout wrapped by urllib as URLError lost the timeout cause.

The proxy now preserves the probe distinction for direct and wrapped timeouts.
Generation still reports `station_timeout`. The configured deadlines, network
scope, JSON limit and authorization remain unchanged. No retry is added.

The controlled experiment uses the existing station contract test with
injected transport, crossing probe/generation with direct/wrapped timeouts.
Before the fix three of the four cases failed. After it, `python3 -m unittest
-q test_pwa test_private_talk_route` passes twice. This experiment measures
classification on the APP code path. Production timing and audio were not
part of the experiment.
