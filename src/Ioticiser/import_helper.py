# Copyright (c) 2015 Iotic Labs Ltd. All rights reserved.

from importlib import import_module
import logging
#from iotic.logger import log
#log = log.getLogger(__name__)
log = logging.getLogger(__name__)


def getItemFromModule(module, item=None):
    """Loads an item from a module.  E.g.: moduleName=a.b.c is equivalent to 'from a.b import c'. If additionally
       itemName = d, this is equivalent to 'from a.b.c import d'. Returns None on failure"""
    try:
        if item is None:
            item = module.rsplit('.', maxsplit=1)[-1]
            module = module[:-(len(item) + 1)]
        return getattr(import_module(module), item)
    except:
        log.exception('Failed to import %s.%s', module, item if item else '')


def loadConfigurableComponent(config, basename, includeBaseConfig=True, key='impl', expectedClass=None):
    """Loads the given component from configuration, as defined (via 'impl') in the given basename config section.
    On failure returns None. includeBaseConfig indicates whether to supply base config section to component in
    addition to implementation specific section. The implementing component should accept a configuration argument
    (or two, if includeBaseConfig is set).
    To allow for the same component to be used multiple times, the value/section (to which the key points) can have
    a suffix, starting with '#'. This and any subsequent characters are ignored (only for loading of the implementing
    class, not its section)."""
    if not (basename in config and
            key in config[basename] and
            config[basename][key] in config):
        log.error('%s section, "%s" value or "%s" section missing', basename, key, key)
        return None
    implName = config[basename][key]
    log.debug('Loading component %s (%s)', basename, implName)
    component = getItemFromModule(implName.split('#', maxsplit=1)[0])
    if component is None:
        return None
    try:
        if includeBaseConfig:
            component = component(dict(config[basename]), dict(config[implName]))
        else:
            component = component(dict(config[implName]))
    except:
        log.exception('Failed to initialise %s', implName)
        return None

    if expectedClass and not isinstance(component, expectedClass):
        log.error('Component %s (%s) not of expected type %s (got %s)', basename, implName, expectedClass,
                  type(component))
        return None

    return component
