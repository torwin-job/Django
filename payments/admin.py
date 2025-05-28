from django.contrib import admin
from .models import Organization, Payment, BalanceLog

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("inn", "balance")
    search_fields = ("inn",)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("operation_id", "amount", "payer_inn", "document_number", "document_date", "created_at")
    search_fields = ("operation_id", "payer_inn", "document_number")

@admin.register(BalanceLog)
class BalanceLogAdmin(admin.ModelAdmin):
    list_display = ("organization", "amount", "created_at")
    search_fields = ("organization__inn",)
