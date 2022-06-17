from netutils.utils import jinja2_convenience_function

# https://netutils.readthedocs.io/en/latest/netutils/utilities/index.html#netutils-to-jinja2-filters

class FilterModule(object):
    def filters(self):
        return jinja2_convenience_function()
