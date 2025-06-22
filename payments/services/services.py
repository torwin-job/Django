import logging
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import F
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

            # Проверка на дублирование с блокировкой
            if Payment.objects.select_for_update().filter(operation_id=operation_id).exists():
                return False, 'already processed'

            # Получение или создание организации с блокировкой
            organization, created = Organization.objects.select_for_update().get_or_create(
                inn=payer_inn,
                defaults={'balance': 0}
            )

            # Создание записи о платеже ПЕРЕД изменением баланса
            payment = Payment.objects.create(
                operation_id=operation_id,
                amount=amount,
                payer_inn=payer_inn,
                document_number=document_number,
                document_date=document_date
            )

            # Логирование изменения баланса ПЕРЕД изменением баланса
            balance_log = BalanceLog.objects.create(
                organization=organization, 
                amount=amount
            )

            # Атомарное обновление баланса с использованием F() для предотвращения гонки
            organization.balance = F('balance') + amount
            organization.save()
            
            # Обновляем объект из базы данных для получения актуального баланса
            organization.refresh_from_db()

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
            # Используем select_for_update для консистентного чтения
            organization = Organization.objects.select_for_update(nowait=True).get(inn=inn)
            return organization.balance
        except Organization.DoesNotExist:
            logger.warning(f"Организация с ИНН {inn} не найдена")
            return None
        except Exception as e:
            logger.error(f"Ошибка при получении баланса организации {inn}: {e}")
            return None

    @staticmethod
    @transaction.atomic
    def update_organization_balance(inn, amount):
        """
        Безопасно обновляет баланс организации.
        
        Args:
            inn (str): ИНН организации.
            amount (Decimal): Сумма для изменения баланса.
            
        Returns:
            tuple: (bool, str, Decimal) - Успех операции, сообщение и новый баланс.
        """
        try:
            # Блокируем запись организации для обновления
            organization = Organization.objects.select_for_update().get(inn=inn)
            
            # Проверяем, что баланс не станет отрицательным (если это уменьшение)
            if amount < 0 and organization.balance + amount < 0:
                return False, 'insufficient funds', organization.balance
            
            # Атомарно обновляем баланс
            organization.balance = F('balance') + amount
            organization.save()
            
            # Обновляем объект для получения актуального баланса
            organization.refresh_from_db()
            
            logger.info(f"Баланс организации {inn} изменен на {amount}. Новый баланс: {organization.balance}")
            return True, 'success', organization.balance
            
        except Organization.DoesNotExist:
            return False, 'organization not found', None
        except Exception as e:
            logger.error(f"Ошибка при обновлении баланса организации {inn}: {e}")
            return False, str(e), None

    @staticmethod
    def get_balance_history(inn, limit=10):
        """
        Получает историю изменений баланса организации.
        
        Args:
            inn (str): ИНН организации.
            limit (int): Количество последних записей.
            
        Returns:
            list: Список записей истории баланса.
        """
        try:
            organization = Organization.objects.get(inn=inn)
            history = BalanceLog.objects.filter(organization=organization).order_by('-created_at')[:limit]
            return [
                {
                    'amount': float(record.amount),
                    'created_at': record.created_at.isoformat(),
                    'balance_after': float(record.organization.balance)
                }
                for record in history
            ]
        except Organization.DoesNotExist:
            logger.warning(f"Организация с ИНН {inn} не найдена")
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении истории баланса для ИНН {inn}: {e}")
            return []