#!/usr/bin/env python

import os
import sys

import django
from django.conf import settings
from django.test.utils import get_runner


def run_tests(*test_args):

    # Since out app has no Models, we need to involve another 'tests' app
    # with at least a Model to make sure that migrations are run for test sqlite database
    if not test_args:
        test_args = ['tests', 'datatables_view', ]

    os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.settings'
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(test_args)
    sys.exit(bool(failures))


if __name__ == '__main__':
    run_tests(*sys.argv[1:])
