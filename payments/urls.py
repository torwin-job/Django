from django.urls import path
from . import views

urlpatterns = [
    path('api/webhook/bank/', views.bank_webhook, name='bank_webhook'),
    path('api/organizations/<str:inn>/balance/', views.get_balance, name='get_balance'),
] 