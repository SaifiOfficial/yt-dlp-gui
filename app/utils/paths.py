from __future__ import annotations

import os
import sys


def project_resource_path(*parts: str) -> str:
    """Return a resource path in source and PyInstaller builds."""
    roots: list[str] = []
    if getattr(sys, 'frozen', False):
        bundle_root = getattr(sys, '_MEIPASS', '')
        if bundle_root:
            roots.append(bundle_root)
        executable_root = os.path.dirname(sys.executable)
        roots.extend((
            os.path.join(executable_root, '_internal'),
            executable_root,
        ))
    else:
        roots.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

    for root in roots:
        candidate = os.path.join(root, *parts)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(roots[0], *parts)
