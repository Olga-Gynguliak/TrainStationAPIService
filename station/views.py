from datetime import datetime

from django.db.models import F, Count
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from station.permissions import IsAdminOrIfAuthenticatedReadOnly


from rest_framework.mixins import CreateModelMixin, ListModelMixin, RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet
from station.models import (
    Station,
    Route,
    Crew,
    TrainType,
    Train,
    Journey,
    Order,
    Ticket,
)
from station.serializers import (
    StationSerializer,
    RouteSerializer,
    CrewSerializer,
    TrainTypeSerializer,
    TrainSerializer,
    JourneySerializer,
    OrderSerializer,
    TicketSerializer,
    JourneyListSerializer,
    JourneyDetailSerializer,
    RouteListSerializer,
    RouteDetailSerializer,
    OrderListSerializer,
    TrainImageSerializer,
    TrainDetailSerializer,
)


class StationViewSet(
    CreateModelMixin,
    ListModelMixin,
    GenericViewSet,
):
    queryset = Station.objects.all().prefetch_related(
        "departure_station", "arrival_station"
    )
    serializer_class = StationSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)


class RouteViewSet(
    CreateModelMixin, ListModelMixin, RetrieveModelMixin, GenericViewSet
):
    queryset = Route.objects.all().select_related("source", "destination")
    serializer_class = RouteSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)

    @staticmethod
    def _params_to_ints(qs):
        return [int(str_id) for str_id in qs.split(",")]

    def get_queryset(self):
        queryset = self.queryset
        source = self.request.query_params.get("source")

        if source:
            source_ids = self._params_to_ints(source)
            queryset = queryset.filter(source_id__in=source_ids)

        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == "list":
            return RouteListSerializer

        if self.action == "retrieve":
            return RouteDetailSerializer

        return super().get_serializer_class()


class CrewViewSet(
    CreateModelMixin,
    ListModelMixin,
    GenericViewSet,
):
    queryset = Crew.objects.all()
    serializer_class = CrewSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)


class TrainTypeViewSet(
    CreateModelMixin,
    ListModelMixin,
    GenericViewSet,
):
    queryset = TrainType.objects.all()
    serializer_class = TrainTypeSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)


class TrainViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Train.objects.all().select_related("train_type")
    serializer_class = TrainSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)

    def get_serializer_class(self):
        if self.action == "list":
            return TrainSerializer

        if self.action == "retrieve":
            return TrainDetailSerializer

        if self.action == "upload_image":
            return TrainImageSerializer

        return super().get_serializer_class()

    @action(
        methods=["POST"],
        detail=True,
        url_path="upload-image",
        permission_classes=[IsAdminUser],
    )
    def upload_image(self, request, pk=None):
        route = self.get_object()
        serializer = self.get_serializer(route, data=request.data)

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class JourneyViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    queryset = (
        Journey.objects.all()
        .prefetch_related("crews", "tickets")
        .select_related("route", "train", "train__train_type")
        .annotate(seats_cargo_nun_available=(F("train__cargo_num") - Count("tickets")))
        .annotate(
            seats_places_in_cargo_available=(
                F("train__places_in_cargo") - Count("tickets")
            )
        )
        .annotate(count_taken_seats=Count("tickets"))
        .annotate(count_taken_cargo=Count("tickets"))
    )
    serializer_class = JourneySerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)

    def get_serializer_class(self):

        if self.action == "list":
            return JourneyListSerializer

        if self.action == "retrieve":
            return JourneyDetailSerializer

        return super().get_serializer_class()

    @staticmethod
    def _params_to_ints(qs):
        return [int(str_id) for str_id in qs.split(",")]

    def get_queryset(self):
        queryset = self.queryset
        train = self.request.query_params.get("train")
        departure_time = self.request.query_params.get("departure_time")
        arrival_time = self.request.query_params.get("arrival_time")

        if train:
            train_ids = self._params_to_ints(train)
            queryset = queryset.filter(train__id__in=train_ids)

        if departure_time:
            departure_time = datetime.strptime(departure_time, "%Y-%m-%d").date()
            queryset = queryset.filter(departure_time__date=departure_time)

        if arrival_time:
            arrival_time = datetime.strptime(arrival_time, "%Y-%m-%d").date()
            queryset = queryset.filter(arrival_time__date=arrival_time)

        return queryset.distinct()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "train",
                type={"type": "array", "items": {"type": "integer"}},
                description="Filter by train IDs (e.g., ?train=2,5)"
            ),
            OpenApiParameter(
                "departure_time",
                type=OpenApiTypes.DATE,
                description="Filter by departure time (e.g., ?departure_time=2024-11-13)"
                ),
            OpenApiParameter(
                "arrival_time",
                type=OpenApiTypes.DATE,
                description="Filter by arrival time (e.g., ?arrival_time=2024-11-13)"
                )
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)



class OrderPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class OrderViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    pagination_class = OrderPagination
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = self.queryset.filter(user=self.request.user)

        if self.action == "list":
            queryset = queryset.prefetch_related(
                "tickets__journey__train", "tickets__journey__crews"
            )
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer

        return super().get_serializer_class()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TicketViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    GenericViewSet,
):
    queryset = (
        Ticket.objects.all()
        .select_related("journey", "journey__train", "order", "journey__route")
        .prefetch_related("journey__crews")
    )
    serializer_class = TicketSerializer
    permission_classes = (IsAdminOrIfAuthenticatedReadOnly,)
