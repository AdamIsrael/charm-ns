#!/usr/bin/env python3

import sys

sys.path.append("lib")

from charms.osm.ns import NetworkService

from ops.charm import CharmBase
from ops.main import main
from ops.model import (
    ActiveStatus,
    BlockedStatus,
    MaintenanceStatus,
    WaitingStatus,
    ModelError,
)


class NetworkServiceCharm(CharmBase):
    def __init__(self, *args):
        super().__init__(*args)

        # Register all of the events we want to observe
        for event in (
            # Charm events
            self.on.config_changed,
            self.on.install,
            self.on.upgrade_charm,
            # Charm actions (primitives)
            self.on.add_user_action,
        ):
            self.framework.observe(event, self)

    def on_config_changed(self, event):
        """Handle changes in configuration"""
        unit = self.model.unit

        # Unit should go into a waiting state until Juju credentials are provided
        unit.status = WaitingStatus("Waiting for Juju credentials")

        # Check that we have a juju username/password
        if (
            self.model.config["juju-username"]
            and self.model.config["juju-password"]
        ):
            unit.status = ActiveStatus()
        else:
            unit.status = BlockedStatus("Invalid Juju credentials.")

    def on_install(self, event):
        """Called when the charm is being installed"""
        # unit = self.model.unit

        # unit.status = ActiveStatus()
        pass

    def on_upgrade_charm(self, event):
        """Upgrade the charm."""
        unit = self.model.unit

        # Mark the unit as under Maintenance.
        unit.status = MaintenanceStatus("Upgrading charm")

        self.on_install(event)

        # When maintenance is done, return to an Active state
        unit.status = ActiveStatus()

    ####################
    # NS Charm methods #
    ####################

    def on_add_user_action(self, event):
        username = event.params["username"]
        bw = event.params["bw"]
        qos = event.params["qos"]
        tariff = event.params["tariff"]

        client = NetworkService(
            user=self.model.config["juju-username"],
            secret=self.model.config["juju-password"],
        )

        user_id = self.add_user(client, username, tariff)
        if user_id > 0:
            success = self.set_policy(client, user_id, bw, qos)
            event.set_results({"user-id": user_id, "policy-set": success})
        else:
            event.fail("user_id is 0; add_user failed.")

    def add_user(self, client, username, tariff):
        """Add a user to the database and return the id."""

        cfg = config()

        application = client.GetApplicationName(
            cfg["nsr-name"], cfg["user-vdu-id"], cfg["user-member-index"]
        )

        output = client.ExecutePrimitiveGetOutput(
            # The name of the application for adding a user
            application,
            # The name of the action to call
            "add-user",
            # The parameter(s) required by the above charm and action
            params={"username": username, "tariff": tariff,},
            # How long to wait (in seconds) for the action to finish
            timeout=500,
        )

        # Get the output from the `add-user` function
        user_id = int(output["user-id"])

        return user_id

    def set_policy(self, client, user_id, bw, qos):
        """Set the policy for a user."""
        success = False

        cfg = config()
        application = client.GetApplicationName(
            cfg["nsr-name"], cfg["policy-vdu-id"], cfg["policy-member-index"]
        )

        success = client.ExecutePrimitiveGetOutput(
            # The name of the application for policy management
            application,
            # The name of the action to call
            "set-policy",
            # The parameter(s) required by the above charm and action
            params={"user_id": user_id, "bw": bw, "qos": qos,},
            # How long to wait (in seconds) for the action to finish
            timeout=500,
        )

        # Get the output from the `add-user` function
        return success


if __name__ == "__main__":
    main(NetworkServiceCharm)
