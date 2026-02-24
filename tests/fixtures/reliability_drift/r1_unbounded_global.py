# Fixture: R1 — module-level mutable mutated inside functions
_cache = {}
results_list = []


def handle_request(key, value):
    _cache[key] = value  # mutation of module-level dict
    results_list.append(value)  # mutation of module-level list
