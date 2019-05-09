import setuptools
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setuptools.setup(
    name = "p9-admin",
    version = "0.9.3",

    description = "Administrative tools for Platform9",
    author = "Gene Liverman",
    author_email = "gene.liverman@puppet.com",
    url = "http://github.com/puppetlabs/p9-admin",
    license = "BSD",

    long_description = long_description,
    long_description_content_type = 'text/markdown',

    classifiers = [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
    ],

    packages = setuptools.find_packages(),
    install_requires = [
        "click",
        "configparser",
        "openstacksdk",
        "python-glanceclient",
        "python-keystoneclient",
        "python-ldap",
        "requests",
    ],

    include_package_data = True,
    entry_points = {
        "console_scripts": [
            "p9-admin = p9admin.cli:main"
        ]
    }
)
