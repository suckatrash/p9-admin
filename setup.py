import setuptools

setuptools.setup(
    name = "p9-admin",
    version = "0.9.2",

    description = "Administrative tools for Platform9",
    author = "Daniel Parks",
    author_email = "daniel.parks@puppet.com",
    url = "http://github.com/puppetlabs/p9-admin",
    license = "BSD",
    long_description = open("README.md").read(),

    classifiers = [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Programming Language :: Python :: 2",
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
