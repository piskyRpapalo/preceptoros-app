# My node · correlate local identity before preliminary admission

The desktop request form and local identity setup are separate actions. The lifecycle reads admission evidence for the configured identity, so forwarding a different identity can leave a valid pending request outside the visible lifecycle.

The existing local PWA intake now requires the submitted node to match the prepared identity before forwarding. Missing or different identity returns a cause-bearing 409. The Android native intake is outside this route. Matching identity still permits only preliminary review and leaves all downstream authority checks in place.

Directed check: `python3 -m unittest test_node_registration test_node_lifecycle`. Exercise missing and different identities, nonlocal and forwarded requests, and the matching pending request.
