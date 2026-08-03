import datetime
from io import BytesIO

from django.core import mail
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from press.forms import DistributionForm, FabricForm, NewspapersNumberForm
from press.models import (
    Distribution,
    DistributionPartyMembers,
    DistributionSympathizerMember,
    FactoryPoint,
    Newspaper,
    NewspaperNumber,
    NewspaperNumbersOnDistribution,
    Sympathizer,
    Town,
)
from press.services import distributions, factory, mail as mail_service, newspaper, report
from django.contrib.auth import get_user_model


def _get_user_model():
    return get_user_model()


class PressBaseTestCase(TestCase):
    """Базовый класс с фикстурами для тестов приложения press."""

    @classmethod
    def setUpTestData(cls):
        cls.user = _get_user_model().objects.create_user(
            email='user@example.com',
            password='pass1234',
            last_name='Иванов',
            first_name='Иван',
        )
        cls.party_member = _get_user_model().objects.create_user(
            email='party@example.com',
            password='pass1234',
            last_name='Петров',
            first_name='Пётр',
            party_member=True,
        )
        cls.sympathizer = Sympathizer.objects.create(name='Сидоров Алексей')
        cls.town = Town.objects.create(title='Москва')
        cls.factory = FactoryPoint.objects.create(title='Завод имени Ленина', town=cls.town)
        cls.newspaper = Newspaper.objects.create(title='Правда', short_title='Пр')
        cls.number = NewspaperNumber.objects.create(
            newspaper=cls.newspaper,
            number='1',
            year=datetime.date(2024, 1, 1),
        )

    def setUp(self):
        self.client = Client()
        self.client.login(email='user@example.com', password='pass1234')


class ModelsTests(PressBaseTestCase):
    """Тесты моделей приложения press."""

    def test_newspaper_str(self):
        self.assertEqual(str(self.newspaper), 'Правда')

    def test_newspaper_number_str(self):
        self.assertEqual(str(self.number), 'Правда 1')

    def test_newspaper_number_related_name(self):
        # related_name текущей реализации — 'newspaper'
        self.assertEqual(list(self.newspaper.newspaper.all()), [self.number])

    def test_sympathizer_str(self):
        self.assertEqual(str(self.sympathizer), 'соч. Сидоров Алексей')

    def test_sympathizer_normalize_name(self):
        self.assertEqual(self.sympathizer.normalize_name, 'сидоровалексей')

    def test_town_str(self):
        self.assertEqual(str(self.town), 'Москва')

    def test_factory_str(self):
        self.assertEqual(str(self.factory), 'Завод имени Ленина')

    def test_factory_related_name(self):
        self.assertEqual(list(self.town.factories.all()), [self.factory])

    def test_distribution_str(self):
        distribution = Distribution.objects.create(
            distribution_date=datetime.date(2024, 1, 15),
            autor=self.user,
            factory=self.factory,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        self.assertEqual(str(distribution), 'Раздача 15.01.2024 на Завод имени Ленина')

    def test_distribution_count_members_current_behavior(self):
        """
        count_members использует len() на RelatedManager.
        Это известная проблема; тест фиксирует текущее поведение.
        """
        distribution = Distribution.objects.create(
            distribution_date=datetime.date(2024, 1, 15),
            autor=self.user,
            factory=self.factory,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        with self.assertRaises(TypeError):
            distribution.count_members()

    def test_distribution_count_members_prefetch_still_raises(self):
        """
        prefetch_related не превращает RelatedManager в список,
        поэтому count_members продолжает падать с TypeError.
        """
        distribution = Distribution.objects.create(
            distribution_date=datetime.date(2024, 1, 15),
            autor=self.user,
            factory=self.factory,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        DistributionPartyMembers.objects.create(
            distribution=distribution, member=self.party_member, quantity=10
        )
        DistributionSympathizerMember.objects.create(
            distribution=distribution, member=self.sympathizer, quantity=5
        )
        distribution = Distribution.objects.prefetch_related(
            'party_members', 'sympathizer_members'
        ).get(pk=distribution.pk)
        with self.assertRaises(TypeError):
            distribution.count_members()

    def test_newspaper_numbers_on_distribution_str(self):
        distribution = Distribution.objects.create(
            distribution_date=datetime.date(2024, 1, 15),
            autor=self.user,
            factory=self.factory,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        line = NewspaperNumbersOnDistribution.objects.create(
            distribution=distribution, number=self.number, quantity=10
        )
        self.assertTrue(str(line).startswith('Номер в раздаче ID'))

    def test_distribution_party_members_str(self):
        distribution = Distribution.objects.create(
            distribution_date=datetime.date(2024, 1, 15),
            autor=self.user,
            factory=self.factory,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        line = DistributionPartyMembers.objects.create(
            distribution=distribution, member=self.party_member, quantity=10
        )
        self.assertTrue(str(line).startswith('Член партии на раздаче ID'))

    def test_distribution_sympathizer_member_str(self):
        distribution = Distribution.objects.create(
            distribution_date=datetime.date(2024, 1, 15),
            autor=self.user,
            factory=self.factory,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        line = DistributionSympathizerMember.objects.create(
            distribution=distribution, member=self.sympathizer, quantity=5
        )
        self.assertTrue(str(line).startswith('Сочувствующий на раздаче ID'))


class FormsTests(PressBaseTestCase):
    """Тесты форм приложения press."""

    def test_distribution_form_valid(self):
        form = DistributionForm(data={
            'distribution_date': '2024-01-15',
            'factory': self.factory.pk,
            'start_time': '10:00',
            'end_time': '12:00',
            'description': 'Тестовая раздача',
        })
        self.assertTrue(form.is_valid())

    def test_distribution_form_invalid_missing_factory(self):
        form = DistributionForm(data={
            'distribution_date': '2024-01-15',
            'start_time': '10:00',
            'end_time': '12:00',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('factory', form.errors)

    def test_fabric_form_valid(self):
        form = FabricForm(data={
            'town': self.town.pk,
            'title': 'Новый завод',
            'description': 'Описание',
        })
        self.assertTrue(form.is_valid())

    def test_newspapers_number_form_valid(self):
        form = NewspapersNumberForm(data={
            'newspaper': self.newspaper.pk,
            'number': '42',
            'year': '2024-01-01',
        })
        self.assertTrue(form.is_valid())


class ServicesTests(PressBaseTestCase):
    """Тесты сервисного слоя приложения press."""

    def test_distributions_get_all_by_date(self):
        Distribution.objects.create(
            distribution_date=datetime.date(2024, 1, 15),
            autor=self.user,
            factory=self.factory,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        result = distributions.get_all({'distribution_date': '2024-01-15'})
        self.assertEqual(len(result), 1)

    def test_distributions_get_all_empty(self):
        result = distributions.get_all({'distribution_date': '2099-01-01'})
        self.assertEqual(result, [])

    def test_factory_get_all(self):
        result = factory.get_all({'town': self.town.pk})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, 'Завод имени Ленина')

    def test_factory_get_all_empty(self):
        other_town = Town.objects.create(title='Другой город')
        result = factory.get_all({'town': other_town.pk})
        self.assertEqual(result, [])

    def test_newspaper_add(self):
        pk = newspaper.add_newspaper(title='Новая газета', short_title='НГ')
        created = Newspaper.objects.get(pk=pk)
        self.assertEqual(created.title, 'Новая газета')
        self.assertEqual(created.short_title, 'НГ')

    def test_newspaper_edit(self):
        pk = newspaper.add_newspaper(title='Старая газета', short_title='СГ')
        result = newspaper.edit_newspaper(pk, title='Новое название')
        self.assertEqual(result['title'], 'Новое название')

    def test_newspaper_get_by_id(self):
        result = newspaper.get_newspaper_by_id(self.newspaper.pk)
        self.assertEqual(result['title'], 'Правда')

    def test_newspaper_get_all(self):
        result = newspaper.get_all_newspapers(filter_by={'title': 'Правда'})
        self.assertEqual(len(result), 1)

    def test_newspaper_get_all_without_filter_current_behavior(self):
        """
        Если не передавать filter_by (или передать пустой dict),
        функция возвращает Manager и падает с TypeError.
        Тест фиксирует текущее поведение.
        """
        with self.assertRaises(TypeError):
            newspaper.get_all_newspapers()

    def test_generate_report_returns_bytesio(self):
        report_month = datetime.date(2024, 1, 1)
        result = report.generate_report(report_month=report_month)
        self.assertIsInstance(result, BytesIO)
        self.assertGreater(len(result.read()), 0)

    def test_generate_report_with_distribution(self):
        distribution = Distribution.objects.create(
            distribution_date=datetime.date(2024, 2, 10),
            autor=self.user,
            factory=self.factory,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        NewspaperNumbersOnDistribution.objects.create(
            distribution=distribution, number=self.number, quantity=10
        )
        DistributionPartyMembers.objects.create(
            distribution=distribution, member=self.party_member, quantity=10
        )
        result = report.generate_report(report_month=datetime.date(2024, 2, 1))
        self.assertIsInstance(result, BytesIO)

    def test_report_month_default(self):
        today = datetime.date.today()
        result = report._report_month()
        self.assertEqual(result.day, 1)

    def test_send_report(self):
        report_file = BytesIO(b'fake xlsx content')
        mail_service.send_report('test@example.com', 2024, report_file)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Отчёт о раздачах газет за 2024 год', mail.outbox[0].subject)


class ViewsTests(PressBaseTestCase):
    """Тесты view приложения press."""

    def test_my_distribution_get(self):
        response = self.client.get(reverse('press:all'))
        self.assertEqual(response.status_code, 200)

    def test_my_distribution_post_filter(self):
        Distribution.objects.create(
            distribution_date=datetime.date.today(),
            autor=self.user,
            factory=self.factory,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        response = self.client.post(reverse('press:all'), {
            'distribution_date': datetime.date.today().strftime('%Y-%m-%d'),
        })
        self.assertEqual(response.status_code, 200)

    def test_new_distrib_get(self):
        response = self.client.get(reverse('press:new-distrib'))
        self.assertEqual(response.status_code, 200)

    def test_new_distrib_post_success(self):
        response = self.client.post(reverse('press:new-distrib'), {
            'distribution_date': '2024-01-15',
            'factory': self.factory.pk,
            'start_time': '10:00',
            'end_time': '12:00',
            'description': 'Раздача',
            'party_members': [self.party_member.pk],
            'newspaper': [self.number.pk],
            'newspaper-quantity': ['10'],
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Distribution.objects.filter(factory=self.factory).exists())

    def test_new_distrib_post_no_members(self):
        """
        Если не указаны раздающие, форма невалидна, но view не возвращает
        HttpResponse. Тест фиксирует текущее поведение.
        """
        with self.assertRaises(ValueError):
            self.client.post(reverse('press:new-distrib'), {
                'distribution_date': '2024-01-15',
                'factory': self.factory.pk,
                'start_time': '10:00',
                'end_time': '12:00',
                'newspaper': [self.number.pk],
                'newspaper-quantity': ['10'],
            })
        self.assertFalse(Distribution.objects.filter(factory=self.factory).exists())

    def test_new_distrib_post_zero_members(self):
        """
        Если списки раздающих пустые, форма невалидна, view не возвращает
        HttpResponse. Тест фиксирует текущее поведение.
        """
        with self.assertRaises(ValueError):
            self.client.post(reverse('press:new-distrib'), {
                'distribution_date': '2024-01-15',
                'factory': self.factory.pk,
                'start_time': '10:00',
                'end_time': '12:00',
                'party_members': [],
                'sympathizer-members': [],
                'newspaper': [self.number.pk],
                'newspaper-quantity': ['10'],
            })

    def test_hx_newspaper(self):
        response = self.client.get(reverse('press:hx-newspaper-field'))
        self.assertEqual(response.status_code, 200)

    def test_hx_distrib_delete(self):
        distribution = Distribution.objects.create(
            distribution_date=datetime.date.today(),
            autor=self.user,
            factory=self.factory,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0),
        )
        response = self.client.delete(reverse('press:hx-distrib', kwargs={'pk': distribution.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Distribution.objects.filter(pk=distribution.pk).exists())

    def test_report_generate_get(self):
        response = self.client.get(reverse('press:report-generate'))
        self.assertEqual(response.status_code, 200)

    def test_report_generate_post(self):
        response = self.client.post(reverse('press:report-generate'), {
            'report-year': '2024',
            'report-email': 'boss@example.com',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_towns_get(self):
        response = self.client.get(reverse('press:towns'))
        self.assertEqual(response.status_code, 200)

    def test_towns_post(self):
        response = self.client.post(reverse('press:towns'), {'town-name': 'Новый город'})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Town.objects.filter(title='Новый город').exists())

    def test_towns_post_empty_name(self):
        response = self.client.post(reverse('press:towns'), {'town-name': ''})
        self.assertEqual(response.status_code, 200)

    def test_towns_post_duplicate_name(self):
        response = self.client.post(reverse('press:towns'), {'town-name': 'Москва'})
        self.assertEqual(response.status_code, 200)

    def test_towns_delete(self):
        town = Town.objects.create(title='Удаляемый')
        response = self.client.delete(reverse('press:towns-delete', kwargs={'pk': town.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Town.objects.filter(pk=town.pk).exists())

    def test_factory_get(self):
        response = self.client.get(reverse('press:factory'))
        self.assertEqual(response.status_code, 200)

    def test_factory_post(self):
        response = self.client.post(reverse('press:factory'), {
            'town': self.town.pk,
            'title': 'Фабрика',
            'description': 'Описание',
        })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(FactoryPoint.objects.filter(title='Фабрика').exists())

    def test_factory_delete(self):
        factory_point = FactoryPoint.objects.create(title='Удаляемый', town=self.town)
        response = self.client.delete(f"{reverse('press:factory')}?id={factory_point.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FactoryPoint.objects.filter(pk=factory_point.pk).exists())

    def test_factory_delete_no_id(self):
        response = self.client.delete(reverse('press:factory'))
        self.assertEqual(response.status_code, 404)

    def test_newspaper_get(self):
        response = self.client.get(reverse('press:newspaper'))
        self.assertEqual(response.status_code, 200)

    def test_newspaper_post(self):
        response = self.client.post(reverse('press:newspaper'), {
            'title': 'Известия',
            'short-title': 'Из',
        })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Newspaper.objects.filter(title='Известия').exists())

    def test_newspaper_post_empty_title_current_behavior(self):
        """
        В view используется title.strip == '' (без вызова метода),
        поэтому пустое название проходит валидацию.
        Тест фиксирует текущее поведение.
        """
        response = self.client.post(reverse('press:newspaper'), {
            'title': '   ',
            'short-title': 'Из',
        })
        self.assertEqual(response.status_code, 201)

    def test_newspaper_delete(self):
        newspaper_obj = Newspaper.objects.create(title='Удаляемая', short_title='Уд')
        response = self.client.delete(f"{reverse('press:newspaper')}?id={newspaper_obj.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Newspaper.objects.filter(pk=newspaper_obj.pk).exists())

    def test_newspaper_numbers_get(self):
        response = self.client.get(reverse('press:newspaper-numbers'))
        self.assertEqual(response.status_code, 200)

    def test_newspaper_numbers_post(self):
        response = self.client.post(reverse('press:newspaper-numbers'), {
            'newspaper': self.newspaper.pk,
            'number': '99',
            'year': '2024-06',
        })
        self.assertEqual(response.status_code, 201)
        self.assertTrue(NewspaperNumber.objects.filter(number='99').exists())

    def test_newspaper_numbers_delete(self):
        number = NewspaperNumber.objects.create(newspaper=self.newspaper, number='Для удаления')
        response = self.client.delete(f"{reverse('press:newspaper-numbers')}?id={number.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(NewspaperNumber.objects.filter(pk=number.pk).exists())

    def test_login_required_redirect(self):
        self.client.logout()
        response = self.client.get(reverse('press:all'))
        self.assertEqual(response.status_code, 302)


class ManagementCommandTests(PressBaseTestCase):
    """Тесты management-команд приложения press."""

    @override_settings(REPORT_MONTH_EMAIL='report@example.com')
    def test_send_report_command(self):
        from io import StringIO
        from press.management.commands.send_report import Command
        out = StringIO()
        command = Command()
        command.stdout = out
        command.handle()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Email с отчётом успешно отправлен', out.getvalue())


class DeprecatedViewsTests(PressBaseTestCase):
    """Тесты deprecated view, сохранённых для обратной совместимости."""

    def test_new_party_member_distrib(self):
        response = self.client.post(reverse('press:htmx-add-party-member'))
        self.assertEqual(response.status_code, 200)

    def test_new_sympathizer_distrib(self):
        response = self.client.post(reverse('press:htmx-add-sympathizer'))
        self.assertEqual(response.status_code, 200)

    def test_hx_add_party_member(self):
        response = self.client.post(reverse('press:hx-add-party-member'), {
            'select-party-members': self.party_member.pk,
        })
        self.assertEqual(response.status_code, 200)

    def test_hx_delete_party_member(self):
        response = self.client.delete(
            reverse('press:hx-delete-pary-member', kwargs={'id_delete_member': self.party_member.pk})
        )
        self.assertEqual(response.status_code, 204)
