# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='parallelrpclib',
    version='0.0.1',  # See: https://packaging.python.org/en/latest/single_source_version.html
    description='An experimental parallel XML-RPC client',
    long_description=long_description,
    license='LGPLv3+',

    # The project's main homepage.
    url='https://github.com/BjarniRunar/pyparallelrpclib',

    # Author details
    author='Bjarni R. Einarsson',
    author_email='bre@klaki.net',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
    ],

    # What does your project relate to?
    keywords='parallel xmlrpc development',

    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    install_requires=[], # see: https://packaging.python.org/en/latest/requirements.html
    extras_require={},
    package_data={},
    data_files=[],
    entry_points={},
)
