"""sdk.connector.fixtures — connectors that exist to TEST the contract, not to serve a bundle.

Nothing here is in `index.json`, so nothing here can be named by a bundle's `runtime.connector`:
`registry.resolve()` reaches a fixture only through its explicit, per-call `extra=` injection.

`csv_dir` is not an optional extra to the suite. §3.2: "two SQL engines can detect an AWS
assumption and are structurally incapable of detecting a SQL assumption" -- the first draft's kill
criterion was written in a unit that could not fire. This is the unit that can.
"""
