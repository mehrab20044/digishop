from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from orders.models import Order
from orders.services.order_service import expire_order


class Command(BaseCommand):
    help = "Expire unpaid orders and release their reserved stock."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help="Maximum number of orders processed per database batch.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]

        if not 1 <= batch_size <= 2000:
            raise CommandError(
                "--batch-size must be between 1 and 2000."
            )

        cutoff = timezone.now()
        last_id = None
        expired_count = 0
        processed_count = 0

        while True:
            queryset = Order.objects.filter(
                status=Order.Status.PENDING_PAYMENT,
                expires_at__lte=cutoff,
            )

            if last_id is not None:
                queryset = queryset.filter(pk__gt=last_id)

            order_ids = list(
                queryset.order_by("pk")
                .values_list("pk", flat=True)[:batch_size]
            )

            if not order_ids:
                break

            for order_id in order_ids:
                if expire_order(order_id=order_id):
                    expired_count += 1

                processed_count += 1

            last_id = order_ids[-1]

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {processed_count} orders; "
                f"expired {expired_count} orders."
            )
        )