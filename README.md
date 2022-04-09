# notional #

<a href="https://pypi.org/project/notional">
    <img src="https://img.shields.io/pypi/v/notional.svg" alt="PyPI">
</a>
<a href="LICENSE">
    <img src="https://img.shields.io/github/license/jheddings/notional" alt="License">
</a>
<a href="https://github.com/ambv/black">
    <img src="https://img.shields.io/badge/code%20style-black-black" alt="Code style">
</a>

A high level interface and object model for the Notion SDK.  This is loosely modeled
after concepts found in [SQLAlchemy](http://www.sqlalchemy.org) and
[MongoEngine](http://mongoengine.org).  This module is built on the excellent
[notion-sdk-py](https://github.com/ramnes/notion-sdk-py) library, providing higher-
level access to the API.

> :warning: **Work In Progress**: The interfaces in this module are still in development
and are likely to change.  Furthermore, documentation is pretty sparse so use at your
own risk!

That being said, if you do use this library, please drop me a message!

If you want to get up and running quickly, check out the [Quick Start](docs/quick.md).

[View the full documentation](https://jheddings.github.io/notional/).

## Installation ##

Install the most recent release using PyPi:


```shell
pip install notional
```

*Note:* it is recommended to use a virtual environment (`venv`) for installing libraries
to prevent conflicting dependency versions.

## Usage ##

Connect to the API using an integration token or an OAuth access token:

```python
import notional

notion = notional.connect(auth=AUTH_TOKEN)

# do some things
```

## Contributing ##

I built this module so that I could interact with Notion in a way that made sense to
me.  Hopefully, others will find it useful.  If someone is particularly passionate about
this area, I would be happy to consider other maintainers or contributors.

Any pull requests or other submissions are welcome.  As most open source projects go, this
is a side project.  Large submissions will take time to review for acceptance, so breaking
them into smaller pieces is always preferred.  Thanks in advance!

Please read the full [contribution guide](https://github.com/jheddings/notional/blob/main/.github/CONTRIBUTING.md).

### Known Issues ###

See [Issues](https://github.com/jheddings/notional/issues) on github.

### Feature Requests ###

See [Issues](https://github.com/jheddings/notional/issues) on github.
