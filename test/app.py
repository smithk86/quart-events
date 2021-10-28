#!/usr/bin/env python

import _path_patch


from testapp import create_app
app = create_app()
app.run()
