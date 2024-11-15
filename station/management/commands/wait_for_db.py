import time
from django.db import connections
from django.db.utils import OperationalError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):

    def handle(self, *args, **options):
        self.stdout.write("Waiting for database...")
        db_connection = None
        attempts = 0
        while not db_connection:
            try:
                db_connection = connections["default"]

                db_connection.ensure_connection()
                self.stdout.write(self.style.SUCCESS("Connected to database"))
            except OperationalError:
                attempts += 1
                if attempts > 5:
                    raise CommandError("Could not connect to database")
                self.stdout.write("Database unavailable, waiting 1 second...")
                time.sleep(1)
