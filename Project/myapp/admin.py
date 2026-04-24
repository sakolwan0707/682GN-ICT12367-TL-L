from django.contrib import admin
from .models import Customers, Categories, Employees, Ingredients, OrderDetails, Products, Suppliers, Orders, Recipes
# Register your models here.


admin.site.register(Customers)
admin.site.register(Categories)
admin.site.register(Employees)
admin.site.register(Ingredients)
admin.site.register(OrderDetails)
admin.site.register(Products)
admin.site.register(Suppliers)
admin.site.register(Orders)
admin.site.register(Recipes)