from pathlib import Path
import importlib.util

from .user import User
from .role import Role
from .permission import Permissions

# Department still lives in the legacy apps/accounts/models.py module.
_department_model_path = Path(__file__).resolve().parent.parent / 'models.py'
_department_spec = importlib.util.spec_from_file_location(
    'apps.accounts.department_model',
    _department_model_path,
)

if _department_spec is None or _department_spec.loader is None:
    raise ImportError('Unable to load Department model.')

_department_module = importlib.util.module_from_spec(_department_spec)
_department_spec.loader.exec_module(_department_module)
Department = _department_module.Department
