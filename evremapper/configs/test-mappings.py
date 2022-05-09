#!/usr/bin/env python3

from evremapper.configs.mappings import Mappings
from evremapper.configs.context import RuntimeContext


# TODO: Better tests
mappings = Mappings()

mappings.load("/home/kevin/.config/ev-remapper/mappings/Default.json")
context = RuntimeContext(mappings._mappings)

print(context.key_to_code)
