# Python version support assessment

The skill intentionally targets Python 3.14 only, matching the repository runtime rule and current dependency test environment. New scripts use standard-library typing plus the existing JSON-schema, Pillow, Matplotlib, and optional scikit-image dependencies. Office export remains dependency-optional; a missing `python-pptx` backend is reported rather than making the core skill depend on it.
