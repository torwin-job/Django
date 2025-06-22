from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging
from .models import Organization, Payment, BalanceLog
from decimal import Decimal
from .services.services import PaymentService

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def bank_webhook(request):
    try:
        data = json.loads(request.body)
        logger.info(f"Получен вебхук: {data}")
        
        success, message = PaymentService.process_bank_webhook(data)
        
        if not success:
            logger.warning(f"Ошибка обработки вебхука: {message}")
            return JsonResponse({'status': 'error', 'message': message}, status=400)
        
        logger.info(f"Вебхук успешно обработан: {message}")
        return JsonResponse({'status': 'success', 'message': message}, status=200)
        
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except Exception as e:
        logger.error(f"Неожиданная ошибка в webhook: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@require_http_methods(["GET"])
def get_balance(request, inn):
    try:
        logger.info(f"Запрос баланса для ИНН: {inn}")
        
        balance = PaymentService.get_organization_balance(inn)
        
        if balance is not None:
            logger.info(f"Баланс для ИНН {inn}: {balance}")
            return JsonResponse({'inn': inn, 'balance': float(balance)})
        
        logger.warning(f"Организация с ИНН {inn} не найдена")
        return JsonResponse({'error': 'Organization not found'}, status=404)
        
    except Exception as e:
        logger.error(f"Ошибка при получении баланса для ИНН {inn}: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@require_http_methods(["GET"])
def get_balance_history(request, inn):
    try:
        logger.info(f"Запрос истории баланса для ИНН: {inn}")
        
        # Получаем лимит из параметров запроса
        limit = request.GET.get('limit', 10)
        try:
            limit = int(limit)
            if limit > 100:  # Ограничиваем максимальное количество записей
                limit = 100
        except ValueError:
            limit = 10
        
        history = PaymentService.get_balance_history(inn, limit)
        
        if history is not None:
            logger.info(f"История баланса для ИНН {inn} получена: {len(history)} записей")
            return JsonResponse({'inn': inn, 'history': history})
        
        logger.warning(f"Организация с ИНН {inn} не найдена")
        return JsonResponse({'error': 'Organization not found'}, status=404)
        
    except Exception as e:
        logger.error(f"Ошибка при получении истории баланса для ИНН {inn}: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)
