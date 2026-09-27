# Discovery proximity contract

`GET /events` accepts `lat` (degrees, -90..90), `lng` (degrees, -180..180), and `radius` (kilometres, >0..100). The three query parameters must be supplied together; an incomplete or invalid set returns HTTP 422.

With these parameters, the endpoint applies the existing public, published, active and optional search/status/host filters, excludes events without usable coordinates, then filters by great-circle distance, sorts by ascending distance, and finally applies `limit`. Each nearby result includes `distanceKm` rounded to two decimals. Event coordinates take precedence over the associated bar's coordinates; no coordinates are inferred from a city or address. Without geographic parameters, existing `/events` behaviour and ordering remain in place and `distanceKm` is null.

The mobile chip requests foreground location only when tapped and sends a 20 km radius. If permission or a position is unavailable, the chip stays off and the ordinary Discovery listing remains accessible.
