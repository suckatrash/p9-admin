import setuptools

setuptools.setup(
    name = "slice-admin",
    version = "0.0.1",

    description = "Administrative tools for SLICE",
    author = "Daniel Parks",
    author_email = "daniel.parks@puppet.com",
    url = "http://github.com/puppetlabs/slice-admin",
    license = "BSD",
    long_description = open("README.rst").read(),

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
        "openstacksdk",
    ],

    include_package_data = True,
    entry_points = {
        "console_scripts": [
            "slice-admin = sliceadmin.cli:main"
        ]
    }
)
