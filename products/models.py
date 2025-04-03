from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Seed(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    image = models.ImageField(upload_to='seed_images/', blank=True, null=True)

    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True)  # ForeignKey Fix

    def __str__(self):
        return self.name
