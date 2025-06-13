from flask_frozen import Freezer
from app import app  # Ensure this imports your Flask `app`

# Tell Frozen‑Flask to generate relative URLs
app.config['FREEZER_RELATIVE_URLS'] = True

freezer = Freezer(app)

# Register each static endpoint (with no dynamic parameters)
@freezer.register_generator
def login():
    yield {}

@freezer.register_generator
def register():
    yield {}

@freezer.register_generator
def dashboard():
    yield {}

@freezer.register_generator
def games():
    yield {}

if __name__ == '__main__':
    freezer.freeze()
