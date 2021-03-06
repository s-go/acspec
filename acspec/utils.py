import errno
import os
import re
import keyword
from six import iteritems

from acspec.dsl import has_option, get_option


def _get_bases(spec):
    if has_option(spec, "bases"):
        return set(get_option(spec, "bases"))
    else:
        return set()


def topological_iteritems(specs, pre_emitted=[]):
    pending = [(name, _get_bases(spec)) for name, spec in iteritems(specs)]
    emitted = pre_emitted[:]
    while pending:
        next_pending = []
        next_emitted = []
        for entry in pending:
            name, bases = entry
            bases.difference_update(emitted)
            if bases:
                next_pending.append(entry)
            else:
                yield name, specs[name]
                emitted.append(name)
                next_emitted.append(name)
        if not next_emitted:
            raise ValueError("Cyclic inheritance: {}".format(next_pending))
        pending = next_pending
        emitted = next_emitted


def underscore(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def camelize(s):
    # camelize with lower first character
    # return re.sub(r'(?!^)_(.)', lambda m: m.group(1).upper(), s)
    return re.sub(r"(?:^|_)(.)", lambda m: m.group(1).upper(), s)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def is_valid_identifier(name):
    if not name:
        return False
    return re.match(
        "[_A-Za-z][_a-zA-Z0-9]*$", name
    ) and not keyword.iskeyword(name)
