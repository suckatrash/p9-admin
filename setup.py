import setuptools

setuptools.setup(
    name = "p9-admin",
    version = "0.0.2",

    description = "Administrative tools for Platform9",
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
        "pf9-saml-auth",
    ],

    include_package_data = True,
    entry_points = {
        "console_scripts": [
            "p9-admin = p9admin.cli:main"
        ]
    }
)
