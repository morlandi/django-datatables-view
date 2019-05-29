#from django.test import TestCase
from django.db import models
import unittest
from datatables_view import *


class TestModelWithoutLatestBy(models.Model):
    one = models.CharField(max_length=20)
    two = models.CharField(max_length=20)

    class Meta:
        app_label = 'myappname2'


class TestModelWithLatestBy(models.Model):
    one = models.CharField(max_length=20)
    two = models.CharField(max_length=20)

    class Meta:
        app_label = 'myappname2'
        get_latest_by = "one"


class DatatablesWithoutLatestByView(DatatablesView):
    model = TestModelWithoutLatestBy


class DatatablesWithLatestByView(DatatablesView):
    model = TestModelWithLatestBy


class DatatablesForceFilterView(DatatablesView):
    model = TestModelWithoutLatestBy

    def get_show_date_filters(self, request):
        return True


class TestDateFilters(unittest.TestCase):

    def test_filters_flag(self):

        request = None

        view = DatatablesWithoutLatestByView()
        view.initialize(request)
        self.assertFalse(view.show_date_filters)

        view = DatatablesWithLatestByView()
        view.initialize(request)
        self.assertTrue(view.show_date_filters)

        view = DatatablesForceFilterView()
        view.initialize(request)
        self.assertTrue(view.show_date_filters)
