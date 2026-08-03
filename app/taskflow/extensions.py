"""Flask extension instances.

Kept in their own module so models and blueprints can import ``db`` without
importing the application factory, avoiding circular imports.
"""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
