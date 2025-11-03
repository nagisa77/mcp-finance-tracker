"""MCP finance tracker package."""

from pkgutil import extend_path

# NOTE:
# -----
# The project itself lives in a package called ``mcp`` so that it can be
# launched via ``python -m mcp.mcp_server``.  The upstream Model Context
# Protocol SDK that we depend on is also published as a package called
# ``mcp`` (available after installing ``mcp>=1.19``).  When Python imports a
# package it caches the first one it encounters under ``sys.modules['mcp']``.
# Running our own package therefore shadows the SDK and attempting to import
# ``mcp.server.fastmcp`` fails with ``ModuleNotFoundError``.
#
# To make both packages coexist we treat ``mcp`` as a namespace package and
# extend its search path so that Python also looks inside the SDK's
# installation directory for submodules.  This allows ``from mcp.server``
# imports to resolve correctly while keeping local imports working.
__path__ = extend_path(__path__, __name__)

__all__ = [
    "crud",
    "config",
    "database",
    "models",
    "schemas",
]
