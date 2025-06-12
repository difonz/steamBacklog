from flask_frozen import Freezer
from app import app
import os
import shutil


freezer = Freezer(app)

if __name__ == '__main__':
    if os.path.isdir('build'):
        shutil.rmtree('build')
    freezer.freeze()