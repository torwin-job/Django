import logging
from decimal import Decimal, InvalidOperation
from django.db import transaction
from payments.models import Organization, Payment, BalanceLog

logger = logging.getLogger(__name__)

class PaymentService:
    @staticmethod
    @transaction.atomic
    def process_bank_webhook(data):
        """
        Обрабатывает вебхук от банка.
        
        Args:
            data (dict): Данные вебхука.
            
        Returns:
            tuple: (bool, str) - Успех операции и сообщение.
        """
        try:
            operation_id = data.get('operation_id')
            amount = Decimal(data.get('amount'))
            payer_inn = data.get('payer_inn')
            document_number = data.get('document_number')
            document_date = data.get('document_date')

            # Валидация входных данных
            if not all([operation_id, amount, payer_inn, document_number, document_date]):
                return False, 'missing required fields'

            # Проверка на дублирование
            if Payment.objects.filter(operation_id=operation_id).exists():
                return False, 'already processed'

            # Получение или создание организации
            organization, _ = Organization.objects.get_or_create(inn=payer_inn)

            # Создание платежа
            Payment.objects.create(
                operation_id=operation_id,
                amount=amount,
                payer_inn=payer_inn,
                document_number=document_number,
                document_date=document_date
            )

            # Обновление баланса
            organization.balance += amount
            organization.save()

            # Логирование изменения баланса
            BalanceLog.objects.create(organization=organization, amount=amount)
            logger.info(f"Баланс организации {organization.inn} увеличен на {amount}. Новый баланс: {organization.balance}")
            return True, 'success'
        except InvalidOperation:
            return False, 'invalid amount format'
        except Exception as e:
            logger.error(f"Ошибка при обработке вебхука: {e}")
            return False, str(e)

    @staticmethod
    def get_organization_balance(inn):
        """
        Получает баланс организации по ИНН.
        
        Args:
            inn (str): ИНН организации.
            
        Returns:
            Decimal or None: Баланс организации или None, если организация не найдена.
        """
        try:
            organization = Organization.objects.get(inn=inn)
            return organization.balance
        except Organization.DoesNotExist:
            return None