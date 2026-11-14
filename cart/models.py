from django.db import models
from django.contrib.auth.models import User
from products.models import Seed

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    seed = models.ForeignKey(Seed, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    @property
    def total_price(self):
        return self.quantity * self.seed.price

    def __str__(self):
        return f"{self.user.username} - {self.seed.name} ({self.quantity})"


