# -*- coding: utf-8 -*-
# Copyright © 2021-2026 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Standalone utility to delete expired cached geospatial data, based on the 'refresh_after' expiry dates recorded by
'instructions_records_to_db.py' and 'data_to_db.py'. Not currently wired into any pipeline; run manually or on a
schedule (e.g. a cron job) to reclaim space, rather than leaving expired data to be replaced lazily on next fetch.

- 'full' fetch_mode layers: an expired layer's whole table is dropped, and its 'fetched_at'/'refresh_after' columns
  are cleared, so 'full_geospatial_layers_data_to_db' treats it as never-fetched and re-downloads it on next run.
- 'aoi' fetch_mode layers: expiry is tracked per logged catchment area, not per layer. This script deletes expired
  'user_log_information' rows, so those areas are no longer considered covered, and are re-fetched into the
  existing table (via 'process_existing_aoi_geospatial_layers') next time a catchment covering them is run.
  It intentionally does NOT delete the underlying feature rows for an expired aoi area, since a single aoi table
  can be shared by many overlapping catchment fetches with different expiries. Deleting features outright would
  require subtracting the expired log geometry from all other unexpired log geometries for the same table first,
  to avoid deleting data that is still validly cached for another catchment; that is out of scope here.
"""

import logging

from sqlalchemy import delete, text, update
from sqlalchemy.engine import Connection

from eddie.digitaltwin.instructions_records_to_db import FetchMode, GeospatialLayers
from eddie.digitaltwin.tables import UserLogInfo, check_table_exists

log = logging.getLogger(__name__)


def delete_expired_full_layer_tables(conn: Connection) -> None:
    """
    Drop the table for each 'full' fetch_mode geospatial layer whose 'refresh_after' expiry date has passed, and
    clear its 'fetched_at'/'refresh_after', so it is re-fetched from scratch next time
    'full_geospatial_layers_data_to_db' runs.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    """
    expired_query = f"""
    SELECT table_name FROM {GeospatialLayers.__tablename__}
    WHERE fetch_mode = '{FetchMode.FULL}' AND refresh_after IS NOT NULL AND refresh_after <= now();
    """
    expired_table_names = [row[0] for row in conn.execute(text(expired_query))]

    for table_name in expired_table_names:
        if check_table_exists(conn, table_name):
            log.info(f"Dropping expired 'full' fetch_mode table '{table_name}'.")
            conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}";'))
        else:
            log.info(f"Expired 'full' fetch_mode table '{table_name}' does not exist. Nothing to drop.")

    if expired_table_names:
        conn.execute(
            update(GeospatialLayers)
            .where(GeospatialLayers.table_name.in_(expired_table_names))
            .values(fetched_at=None, refresh_after=None)
        )


def delete_expired_user_log_entries(conn: Connection) -> int:
    """
    Delete rows from 'user_log_information' whose 'refresh_after' expiry date has passed. This does not delete any
    feature data; it only forgets that the area was previously fetched, so it is treated as uncovered and
    re-fetched (appended to the existing 'aoi' fetch_mode table) next time a catchment covering it is processed.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.

    Returns
    -------
    int
        The number of expired 'user_log_information' rows deleted.
    """
    if not check_table_exists(conn, UserLogInfo.__tablename__):
        log.info(f"'{UserLogInfo.__tablename__}' does not exist. Nothing to delete.")
        return 0

    result = conn.execute(
        delete(UserLogInfo).where(UserLogInfo.refresh_after.isnot(None), UserLogInfo.refresh_after <= text("now()"))
    )
    log.info(f"Deleted {result.rowcount} expired 'user_log_information' row(s).")
    return result.rowcount


def delete_expired_cache(conn: Connection) -> None:
    """
    Delete all expired cached geospatial data: dropping expired 'full' fetch_mode layer tables outright, and
    forgetting expired 'aoi' fetch_mode coverage by deleting the relevant 'user_log_information' rows.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    """
    delete_expired_full_layer_tables(conn)
    delete_expired_user_log_entries(conn)


if __name__ == "__main__":
    # Example standalone usage; not wired into any existing pipeline/CLI.
    from eddie.digitaltwin import setup_environment  # pylint: disable=import-outside-toplevel

    engine = setup_environment.get_database()
    with engine.connect() as connection:
        delete_expired_cache(connection)
        connection.commit()
