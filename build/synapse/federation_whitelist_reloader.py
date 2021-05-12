import logging
import os
from pathlib import Path
from typing import Any, Dict

from synapse.api.errors import HttpResponseException
from synapse.handlers.auth import AuthHandler


# This file gets created during docker build from the given Raiden version
from synapse.http import RequestTimedOutError
from synapse.metrics.background_process_metrics import run_as_background_process


PATH_KNOWN_FEDERATION_SERVERS_DEFAULT_URL = Path("/known_servers.default.txt")


class FederationWhitelistReloaderProvider:
    """
    Helper that peridoically fetches and updates the allowed federation domain whitelist.

    Implemented as a password provider since this is a handy way to inject code into Synapse.
    """

    __version__ = "0.1"

    def __init__(self, config: Dict[str, Any], account_handler: AuthHandler) -> None:
        self.hs = account_handler._hs
        self.known_servers_url = os.environ.get(
            "URL_KNOWN_FEDERATION_SERVERS", PATH_KNOWN_FEDERATION_SERVERS_DEFAULT_URL.read_text()
        )
        self.update_interval = config.get("update_interval", 3600)
        self.log = logging.getLogger(__name__)
        self.clock = self.hs.get_clock()
        self.clock.call_later(0, self.run_check_and_fetch_in_background)

    @staticmethod
    def parse_config(config: Dict[str, Any]) -> Dict[str, Any]:
        return config

    def run_check_and_fetch_in_background(self) -> None:
        run_as_background_process(
            "federation_whitelist_reloader", self._check_and_update_whitelist
        )

    async def _check_and_update_whitelist(self) -> None:
        http_client = self.hs.get_proxied_blacklisted_http_client()
        try:
            known_servers = await http_client.get_json(self.known_servers_url)
            if not isinstance(known_servers, dict):
                raise TypeError(f"Invalid response format from known servers URL: {known_servers}")
            if "all_servers" not in known_servers:
                raise ValueError(
                    f"Known servers response is missing 'all_serves' key: {known_servers}"
                )
            new_whitelist = known_servers["all_servers"]
            self.hs.config.federation_domain_whitelist = {domain: True for domain in new_whitelist}
            self.log.warning("Updated federation whitelist. New list: %s", new_whitelist)
        except (HttpResponseException, RequestTimedOutError, TypeError, ValueError) as ex:
            self.log.error(f"Error fetching federation known servers: {ex}. Will retry later.")
        self.clock.call_later(self.update_interval, self.run_check_and_fetch_in_background)
