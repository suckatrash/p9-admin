import setuptools

setuptools.setup(
    name = "p9-admin",
    version = "0.0.1",

    description = "Administrative tools for SLICE",
    author = "Daniel Parks",
    author_email = "daniel.parks@puppet.com",
    url = "http://github.com/puppetlabs/p9-admin",
    license = "BSD",
    long_description = open("README.rst").read(),

    classifiers = [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        # pf9-saml-auth is 2.7 only
        "Programming Language :: Python :: 2 :: Only",
    ],

    packages = setuptools.find_packages(),
    install_requires = [
        "click",
        "openstacksdk",
        # Must be installed manually, since it's not on PyPi
        "pf9-saml-auth"
    ],

    include_package_data = True,
    entry_points = {
        "console_scripts": [
            "p9-admin = p9admin.cli:main"
        ]
    }
)
