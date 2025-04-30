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
                    name = row["name"].strip()
                    description = row["description"].strip()
                    price = float(row["price"].strip())
                    stock = int(row["stock"].strip())
                    image = row["image"].strip()
                    category_name = row["category"].strip().capitalize()

                    # Get or create category
                    category, _ = Category.objects.get_or_create(name=category_name)

                    # Check if seed exists
                    existing_seed = Seed.objects.filter(name=name).first()
                    if existing_seed:
                        # Increment stock and update other details
                        existing_seed.stock += stock
                        existing_seed.description = description
                        existing_seed.price = price
                        existing_seed.image = image
                        existing_seed.category = category
                        existing_seed.save()
                        self.stdout.write(self.style.SUCCESS(f"🔄 Updated and incremented stock for: {name}"))
                    else:
                        # Create new seed
                        Seed.objects.create(
                            name=name,
                            description=description,
                            price=price,
                            stock=stock,
                            image=image,
                            category=category
                        )
                        self.stdout.write(self.style.SUCCESS(f"➕ Created new seed: {name}"))

            self.stdout.write(self.style.SUCCESS("✅ All seeds processed successfully!"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Error: {e}"))
