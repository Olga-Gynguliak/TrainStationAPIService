from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from station.models import Station, Route, TrainType, Train, Crew, Journey
from station.serializers import CrewSerializer

Route_URL = reverse('station:route-list')
Journey_URL = reverse('station:journey-list')
Crew_URL = reverse('station:crew-list')


class JourneyModelTests(TestCase):
    def setUp(self):
        self.station1 = Station.objects.create(name="Station 1", latitude=35.45, longitude=25.55)
        self.station2 = Station.objects.create(name="Station 2", latitude=35.45, longitude=25.55)

        self.route = Route.objects.create(
            source=self.station1, destination=self.station2, distance=500
        )

        self.train_type = TrainType.objects.create(name="Train Type")
        self.train = Train.objects.create(
            name="Train 1", cargo_num=5, places_in_cargo=100, train_type=self.train_type
        )
        self.crew1 = Crew.objects.create(first_name="John", last_name="Doe")
        self.departure_time = timezone.now()
        self.arrival_time = self.departure_time + timedelta(hours=2)

    def test_journey_creation(self):
        journey = Journey.objects.create(
            route=self.route,
            train=self.train,
            departure_time=self.departure_time,
            arrival_time=self.arrival_time,
        )
        journey.crews.add(self.crew1)

        self.assertTrue(isinstance(journey, Journey))
        self.assertIn(self.crew1, journey.crews.all())

    def sample_route(**params):
        source = Station.objects.create(name="Source Station", latitude=0.0, longitude=0.0)
        destination = Station.objects.create(name="Destination Station", latitude=1.0, longitude=1.0)
        defaults = {"source": source, "destination": destination, "distance":100}
        defaults.update(params)
        return Route.objects.create(**defaults)

    def image_upload_url(train_id):
        """Returns the upload URL for an image"""
        return reverse("station:train-image-upload", args=[train_id])


class UnauthenticatedRouteApiTests(APITestCase):
    def test_auth_required(self):
        response = self.client.get(Route_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RouteApiAuthenticationTests(APITestCase):
    def setUp(self):
        self.client = self.client_class()
        self.test_user = self._create_test_user()
        self._authenticate_user(self.test_user)

    def _create_test_user(self):
        return get_user_model().objects.create_user(
            email="test@test.com",
            password="testpass"
        )

    def _authenticate_user(self, user):
        self.client.force_authenticate(user=user)

    def test_filter_routes_by_source_station(self):
        station_1 = self._create_station(name="Source 1", latitude=10.0, longitude=20.0)
        station_2 = self._create_station(name="Source 2", latitude=15.0, longitude=25.0)

        route_1 = self._create_route(source=station_1)
        route_2 = self._create_route(source=station_2)

        response_1 = self._get_routes_with_source(station_1.id)
        self._assert_route_filter_response(response_1, route_1)

        response_2 = self._get_routes_with_source(station_2.id)
        self._assert_route_filter_response(response_2, route_2)

    def _create_station(self, name, latitude, longitude):
        return Station.objects.create(name=name, latitude=latitude, longitude=longitude)

    def _create_route(self, source):
        return Route.objects.create(source=source, destination=source, distance=100)

    def _get_routes_with_source(self, source_id):
        return self.client.get(Route_URL, {"source": source_id})

    def _assert_route_filter_response(self, response, expected_route):
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertTrue(any(route["id"] == expected_route.id for route in response.data))


class UnauthenticatedRouteApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_requires_authentication(self):
        response = self.client.get(Route_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UnauthenticatedJourneyApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_requires_authentication(self):
        response = self.client.get(Journey_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class CrewViewSetTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

        self.admin_user = get_user_model().objects.create_superuser(
            email="admin@example.com",
            password="adminpassword"
        )
        self.regular_user = get_user_model().objects.create_user(
            email="user@example.com",
            password="userpassword"
        )
        self.crew = Crew.objects.create(first_name="John", last_name="Doe")

    def test_list_crew_authenticated(self):
        self.client.force_authenticate(self.regular_user)
        response = self.client.get(Crew_URL)
        print(response.status_code)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if response.status_code == status.HTTP_200_OK:
            crews = Crew.objects.all()
            serializer = CrewSerializer(crews, many=True)
            self.assertEqual(response.data, serializer.data)
        else:
            self.fail(f"Expected 200 response, but got {response.status_code}")

    def test_create_crew_as_admin(self):
        self.client.force_authenticate(self.admin_user)
        payload = {"first_name": "John", "last_name": "Doe"}
        response = self.client.post(Crew_URL, payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Crew.objects.count(), 2)
        self.assertEqual(Crew.objects.last().first_name, "John")

    def test_create_crew_as_regular_user(self):
        self.client.force_authenticate(self.regular_user)
        payload = {"first_name": "John", "last_name": "Doe"}
        response = self.client.post(Crew_URL, payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Crew.objects.count(), 1)
