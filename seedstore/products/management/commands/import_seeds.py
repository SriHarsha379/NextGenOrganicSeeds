import csv
from django.core.management.base import BaseCommand
from products.models import Seed, Category

class Command(BaseCommand):
    help = "Import seeds data from CSV file"

    def handle(self, *args, **kwargs):
        file_path = "C:/Users/harsh/PycharmProjects/seedstore/seedstore/seeds_data.csv"

        try:
            with open(file_path, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    category_name = row["category"].strip().capitalize()  # Normalize category name
                    category, created = Category.objects.get_or_create(name=category_name)

                    Seed.objects.update_or_create(
                        name=row["name"].strip(),
                        defaults={
                            "description": row["description"].strip(),
                            "price": row["price"].strip(),
                            "stock": row["stock"].strip(),
                            "image": row["image"].strip(),
                            "category": category,  # Assign Category instance
                        }
                    )

            self.stdout.write(self.style.SUCCESS("✅ Seeds imported successfully!"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Error: {e}"))
