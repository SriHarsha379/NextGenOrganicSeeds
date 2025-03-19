import csv
import os
from django.core.management.base import BaseCommand
from products.models import Seed, Category

class Command(BaseCommand):
    help = "Import seeds data from CSV file"

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the CSV file')

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']

        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"❌ Error: File not found: {file_path}"))
            return

        try:
            with open(file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    category_name = row["category"].strip().capitalize()  # Normalize category name
                    category, _ = Category.objects.get_or_create(name=category_name)

                    Seed.objects.update_or_create(
                        name=row["name"].strip(),
                        defaults={
                            "description": row["description"].strip(),
                            "price": float(row["price"].strip()),  # Ensure numeric type
                            "stock": int(row["stock"].strip()),  # Ensure numeric type
                            "image": row["image"].strip(),
                            "category": category,  # Assign Category instance
                        }
                    )

            self.stdout.write(self.style.SUCCESS("✅ Seeds imported successfully!"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Error: {e}"))
