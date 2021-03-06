

# TeaRoom

TeaRoom is a (short description) built with [Python][0] using the [Django Web Framework][1].

This project has the following basic apps:

* App1 (short desc)
* App2 (short desc)
* App3 (short desc)

## Installation

### Quick start

To set up a development environment quickly, first install Python 3.4. It
comes with virtualenv built-in. So create a virtual env by:

    1. `$ python3.4 -m venv TeaRoom`
    2. `$ . TeaRoom/bin/activate`

> Sometimes, binaries like pip get installed inside `local/bin/`. So append
> this line to `TeaRoom/bin/activate`:
>
> `PATH="$VIRTUAL_ENV/local/bin:$PATH"`

Now the pip commands should work smoothly. Install all dependencies:

    pip install -r dev-requirements.txt

Run migrations:

    python manage.py migrate

### Detailed instructions

Take a look at the docs for a detailed instructions guide.

[0]: https://www.python.org/
[1]: https://www.djangoproject.com/

## Quick install (any python version)

Create a virtual python environment:

    sudo pip install virtualenv
    virtualenv TeaRoomEnv
    cd TeaRoomEnv/
    source bin/activate

Clone the repository:

    git clone git@github.com:zazasa/TeaRoom.git
    cd TeaRoom/

Install the required libraries:

    sudo apt-get install libffi-dev
    pip install -r requirements.txt 

Have one of the admins send you the `local.env` file (put it in src/TeaRoom/settings).

Create data structures (sqlite database):
    
    cd src
    ./manage.py migrate
    ./manage.py createsuperuser