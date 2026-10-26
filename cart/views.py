from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import permissions
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from .serializers import AddItemSerializer, UpdateItemSerializer
from .services import add_item, merge_guest, resolve_cart, snapshot, touch, update_item


class CartThrottle(SimpleRateThrottle):
    rate = '120/min'
    scope = 'shopping_cart'

    def get_cache_key(self, request, view):
        ident = f'user:{request.user.pk}' if request.user.is_authenticated else f'ip:{self.get_ident(request)}'
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class CartAPI(APIView):
    permission_classes = [permissions.AllowAny]
    parser_classes = [JSONParser]
    throttle_classes = [CartThrottle]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store, private'
        response['Vary'] = 'Authorization, X-Cart-Token'
        return response


class CartView(CartAPI):
    @extend_schema(responses=OpenApiTypes.OBJECT, parameters=[OpenApiParameter('X-Cart-Token', str, location=OpenApiParameter.HEADER, description='256-bit guest token as 64 lowercase hexadecimal characters.')])
    def get(self, request):
        return Response(snapshot(resolve_cart(request), request))


class AddItemView(CartAPI):
    @extend_schema(request=AddItemSerializer, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def post(self, request):
        serializer = AddItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = resolve_cart(request, create=True, lock=True)
        add_item(cart, serializer.validated_data)
        return Response(snapshot(cart, request))


class ItemView(CartAPI):
    @extend_schema(request=UpdateItemSerializer, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def patch(self, request, item_id):
        serializer = UpdateItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = resolve_cart(request, lock=True)
        if cart is None:
            from rest_framework.exceptions import NotFound
            raise NotFound()
        update_item(cart, item_id, serializer.validated_data['quantity'])
        return Response(snapshot(cart, request))

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def delete(self, request, item_id):
        cart = resolve_cart(request, lock=True)
        if cart is None:
            from rest_framework.exceptions import NotFound
            raise NotFound()
        get_object_or_404(cart.items, pk=item_id).delete()
        touch(cart)
        return Response(snapshot(cart, request))


class MergeView(CartAPI):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def post(self, request):
        return Response(merge_guest(request))
