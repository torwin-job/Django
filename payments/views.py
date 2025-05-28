from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .models import Organization, Payment, BalanceLog
from decimal import Decimal
from .services.services import PaymentService



@csrf_exempt
@require_http_methods(["POST"])
def bank_webhook(request):
    try:
        data = json.loads(request.body)
        success, message = PaymentService.process_bank_webhook(data)
        if not success:
            return JsonResponse({'status': message}, status=200)
        return JsonResponse({'status': message}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_http_methods(["GET"])
def get_balance(request, inn):
    balance = PaymentService.get_organization_balance(inn)
    if balance is not None:
        return JsonResponse({'inn': inn, 'balance': float(balance)})
    return JsonResponse({'error': 'Organization not found'}, status=404)
