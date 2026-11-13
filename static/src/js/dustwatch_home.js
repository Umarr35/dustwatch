/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

class DustWatchHome extends Component {
    static template = "dustwatch.DustWatchHome";
}

registry.category("actions").add(
    "dustwatch_home",
    DustWatchHome
);