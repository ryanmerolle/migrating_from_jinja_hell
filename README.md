# TEST_TEMPLATE

Simplified template logic for sharing with Brad.

## Structure

### Filter Plugins

Single filter_plugin that leveraged [netutils](https://netutils.readthedocs.io/en/latest/netutils/utilities/index.html#netutils-to-jinja2-filters)

For the plugin to work, use the [requirements.txt](./requirements.txt)

### Roles

Single role calling a main.j2 template which includes a port_channel
& ethernet template.

### Group Vars

non-default_switchport logic is located in `./group_vars/{{ site_group }}/main`

### Artifacts

Located in `./artifacts/{{ inventory_hostname }}`

#### Example Logic

[Example logic Documented](./artifacts/example_logic/interfaces.md)
