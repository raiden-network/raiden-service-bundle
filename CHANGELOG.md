## Changelog
- WIP - `WIP` - **Upgrade release**
  - Upgrade Synapse to v1.5.1
  - Use `stable` release from https://github.com/raiden-network/raiden-services
  - Use version tagged public images instead of building locally.
  - Make all bundled software versions easier to maintain (`BUILD_VERSIONS` & `docker-compose.yml::x-versions`).
  - Removed auto registration, added interactive registration script (`./register-service-provider.sh`).
- 2019-10-07 - `2019.10.1` - **Upgrade release**
  - Upgrade https://github.com/raiden-network/raiden-services image to `v0.4.0`
- 2019-10-02 - `2019.10.0` - **Upgrade release**
  - Add https://github.com/raiden-network/raiden-services services to the bundle
  - Upgrade Synapse to v1.3.1
  - Tune Postgres default parameters
  - Merge federation access under regular HTTPS port (443)
    - Port 8448 is no longer needed
- 2018-12-19 - `2018.12.0` - **Maintenance release**
  - purger.py restart improvements
- 2018-10-19 - `2018.10.0` - **Maintenence release**
  - Add new servers to known list
  - Upgrade Synapse to 0.33.7
  - Automatically purge historic state and restart service once a day, removing the need for an external cron service
  - Updated minimum docker and docker-compose version requirements
- 2018-08-09 - `2018.8.1` - **Initial public release**
- 2018-08-02 - `2018.8.0` - **Initial version**