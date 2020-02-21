#from django.test import TestCase
from django.db import models
from unittest import TestCase
import factory
import factory.random
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from datatables_view import *


User = get_user_model()


class UserDatatablesView(DatatablesView):
    model = User
    column_defs = [
        DatatablesView.render_row_tools_column_def(),
        {
            'name': 'id',
            'visible': False,
        }, {
            'name': 'username',
        }, {
            'name': 'first_name',
            'choices': True,
            'autofilter': True,
        }, {
            'name': 'last_name',
        }
    ]


class UserDatatablesWithWrongKeyView(DatatablesView):
    model = User
    column_defs = [
        DatatablesView.render_row_tools_column_def(),
        {
            'name': 'id',
            'visible': False,
        }, {
            'name': 'username',
            'wrongkey': 'you_baaaad',
        }, {
            'name': 'first_name',
            'choices': True,
            'autofilter': True,
        }, {
            'name': 'last_name',
        }
    ]


class UserDatatablesWithEmptyColumnNameView(DatatablesView):
    model = User
    column_defs = [
        DatatablesView.render_row_tools_column_def(),
        {
            'name': 'id',
            'visible': False,
        }, {
            'name': '',
        }, {
            'name': '',
        }, {
            'name': 'first_name',
            'choices': True,
            'autofilter': True,
        }, {
            'name': 'last_name',
        }
    ]


class UserFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = User

    username = factory.Sequence(lambda n: 'username_{}'.format(n))
    password = 'password'
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')


class AutoFilterTestCase(TestCase):

    def setUp(self):
        factory.random.reseed_random('test_static_columns')
        self.build_fake_data()

    def tearDown(self):
        User.objects.all().delete()

    def build_fake_data(self):
        UserFactory.create_batch(100)

    def test_autofilter_columns(self):

        request = None
        view = UserDatatablesView()
        view.initialize(request)
        print(view.column_spec_by_name('first_name'))

        # Since we activated 'autofilter' for 'first_name',
        # we should see a choices list filled with distinct values
        queryset = view.get_initial_queryset(request)
        names = queryset.values_list('first_name', flat=True).distinct().order_by('first_name')
        # Example:
        # [('Alicia', 'Alicia'), ('Amanda', 'Amanda'), ('Amy', 'Amy'), ...
        expected_choices = [(item, item) for item in names]

        self.assertSequenceEqual(expected_choices, view.column_spec_by_name('first_name')['choices'])

    def test_unexcpeted_key(self):

        request = None
        view = UserDatatablesWithWrongKeyView()

        with self.assertRaises(Exception) as raise_context:
            view.initialize(request)
        self.assertTrue('Unexpected key "wrongkey"' in str(raise_context.exception))
        print(str(raise_context.exception))

    def test_missing_column_name(self):
        # TODO: to be investigated
        request = None
        view = UserDatatablesWithEmptyColumnNameView()
        view.initialize(request)
