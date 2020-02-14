from raiden.constants import (DISCOVERY_DEFAULT_ROOM,
                              MONITORING_BROADCASTING_ROOM,
                              PATH_FINDING_BROADCASTING_ROOM, Networks)
from raiden.network.transport.matrix import make_room_alias
from raiden.utils.typing import ChainID


def get_broadcast_room_aliases(network):
    room_alias_fragments = [
        DISCOVERY_DEFAULT_ROOM,
        PATH_FINDING_BROADCASTING_ROOM,
        MONITORING_BROADCASTING_ROOM,
    ]

    broadcast_room_aliases = list()

    for room_alias_fragment in room_alias_fragments:
        broadcast_room_alias = make_room_alias(ChainID(network.value), room_alias_fragment)
        broadcast_room_aliases.append((network, broadcast_room_alias))

    return broadcast_room_aliases
