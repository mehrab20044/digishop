from django.urls import path
from .views import AddItemView, CartView, ItemView, MergeView

app_name = 'cart'
urlpatterns = [
    path('', CartView.as_view(), name='detail'),
    path('items/', AddItemView.as_view(), name='add-item'),
    path('items/<int:item_id>/', ItemView.as_view(), name='item'),
    path('merge/', MergeView.as_view(), name='merge'),
]
