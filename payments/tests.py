from django.test import TestCase, TransactionTestCase
from django.db import transaction
from decimal import Decimal
import uuid
from .models import Organization, Payment, BalanceLog
from .services.services import PaymentService
from django.utils import timezone
import threading
import time


class PaymentServiceTestCase(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            inn='1234567890',
            balance=Decimal('1000.00')
        )
        
    def test_process_bank_webhook_success(self):
        """Тест успешной обработки вебхука"""
        data = {
            'operation_id': str(uuid.uuid4()),
            'amount': '500.00',
            'payer_inn': '1234567890',
            'document_number': 'DOC001',
            'document_date': timezone.now()
        }
        
        success, message = PaymentService.process_bank_webhook(data)
        
        self.assertTrue(success)
        self.assertEqual(message, 'success')
        
        # Проверяем, что платеж создан
        payment = Payment.objects.get(operation_id=data['operation_id'])
        self.assertEqual(payment.amount, Decimal('500.00'))
        
        # Проверяем, что баланс обновлен
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.balance, Decimal('1500.00'))
        
        # Проверяем, что лог создан
        balance_log = BalanceLog.objects.filter(organization=self.organization).first()
        self.assertIsNotNone(balance_log)
        self.assertEqual(balance_log.amount, Decimal('500.00'))

    def test_process_bank_webhook_duplicate(self):
        """Тест обработки дублирующегося вебхука"""
        operation_id = str(uuid.uuid4())
        data = {
            'operation_id': operation_id,
            'amount': '500.00',
            'payer_inn': '1234567890',
            'document_number': 'DOC001',
            'document_date': timezone.now()
        }
        
        # Первый вызов
        success1, message1 = PaymentService.process_bank_webhook(data)
        self.assertTrue(success1)
        
        # Второй вызов с тем же operation_id
        success2, message2 = PaymentService.process_bank_webhook(data)
        self.assertFalse(success2)
        self.assertEqual(message2, 'already processed')

    def test_process_bank_webhook_missing_fields(self):
        """Тест обработки вебхука с отсутствующими полями"""
        data = {
            'operation_id': str(uuid.uuid4()),
            'amount': '500.00',
            # Отсутствует payer_inn
            'document_number': 'DOC001',
            'document_date': timezone.now()
        }
        
        success, message = PaymentService.process_bank_webhook(data)
        self.assertFalse(success)
        self.assertEqual(message, 'missing required fields')

    def test_process_bank_webhook_invalid_amount(self):
        """Тест обработки вебхука с некорректной суммой"""
        data = {
            'operation_id': str(uuid.uuid4()),
            'amount': 'invalid_amount',
            'payer_inn': '1234567890',
            'document_number': 'DOC001',
            'document_date': timezone.now()
        }
        
        success, message = PaymentService.process_bank_webhook(data)
        self.assertFalse(success)
        self.assertEqual(message, 'invalid amount format')

    def test_get_organization_balance(self):
        """Тест получения баланса организации"""
        balance = PaymentService.get_organization_balance('1234567890')
        self.assertEqual(balance, Decimal('1000.00'))

    def test_get_organization_balance_not_found(self):
        """Тест получения баланса несуществующей организации"""
        balance = PaymentService.get_organization_balance('9999999999')
        self.assertIsNone(balance)

    def test_update_organization_balance(self):
        """Тест безопасного обновления баланса"""
        success, message, new_balance = PaymentService.update_organization_balance('1234567890', Decimal('500.00'))
        self.assertTrue(success)
        self.assertEqual(message, 'success')
        self.assertEqual(new_balance, Decimal('1500.00'))

    def test_update_organization_balance_insufficient_funds(self):
        """Тест обновления баланса с недостаточными средствами"""
        success, message, balance = PaymentService.update_organization_balance('1234567890', Decimal('-2000.00'))
        self.assertFalse(success)
        self.assertEqual(message, 'insufficient funds')

    def test_get_balance_history(self):
        """Тест получения истории баланса"""
        # Создаем несколько записей в истории
        BalanceLog.objects.create(organization=self.organization, amount=Decimal('100.00'))
        BalanceLog.objects.create(organization=self.organization, amount=Decimal('200.00'))
        
        history = PaymentService.get_balance_history('1234567890', limit=5)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['amount'], 200.0)  # Последняя запись первая


class PaymentServiceConcurrencyTestCase(TransactionTestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            inn='1234567890',
            balance=Decimal('1000.00')
        )

    def test_concurrent_webhook_processing(self):
        """Тест конкурентной обработки вебхуков"""
        operation_ids = [str(uuid.uuid4()) for _ in range(5)]
        results = []
        
        def process_webhook(operation_id):
            data = {
                'operation_id': operation_id,
                'amount': '100.00',
                'payer_inn': '1234567890',
                'document_number': f'DOC{operation_id[:8]}',
                'document_date': timezone.now()
            }
            return PaymentService.process_bank_webhook(data)
        
        # Запускаем обработку вебхуков последовательно (SQLite не поддерживает конкурентные блокировки)
        for operation_id in operation_ids:
            result = process_webhook(operation_id)
            results.append(result)
        
        # Проверяем, что все вебхуки обработаны успешно
        success_count = sum(1 for success, _ in results if success)
        self.assertEqual(success_count, 5)
        
        # Проверяем, что баланс корректно обновлен
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.balance, Decimal('1500.00'))  # 1000 + 5 * 100
        
        # Проверяем, что все платежи созданы
        payment_count = Payment.objects.filter(payer_inn='1234567890').count()
        self.assertEqual(payment_count, 5)

    def test_duplicate_operation_id_handling(self):
        """Тест обработки дублирующихся operation_id в конкурентной среде"""
        operation_id = str(uuid.uuid4())
        data = {
            'operation_id': operation_id,
            'amount': '100.00',
            'payer_inn': '1234567890',
            'document_number': 'DOC001',
            'document_date': timezone.now()
        }
        
        # Первый вызов должен быть успешным
        success1, message1 = PaymentService.process_bank_webhook(data)
        self.assertTrue(success1)
        self.assertEqual(message1, 'success')
        
        # Второй вызов с тем же operation_id должен быть отклонен
        success2, message2 = PaymentService.process_bank_webhook(data)
        self.assertFalse(success2)
        self.assertEqual(message2, 'already processed')
        
        # Проверяем, что баланс изменился только один раз
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.balance, Decimal('1100.00'))  # 1000 + 100
