from django.db import models
from django.utils import timezone
# Create your models here.
    
class Categories(models.Model):
    category_id = models.CharField(primary_key=True, max_length=6, db_collation='Thai_CS_AI')
    category_name = models.CharField(max_length=100, db_collation='Thai_CS_AI')

    class Meta:
        managed = True
        db_table = 'categories'


class Customers(models.Model):
    customer_id = models.CharField(primary_key=True, max_length=6, db_collation='Thai_CS_AI')
    cus_name = models.CharField(max_length=100, db_collation='Thai_CS_AI', blank=True, null=True)
    cus_phone = models.CharField(unique=True, max_length=20, db_collation='Thai_CS_AI')
    cus_email = models.CharField(max_length=100, db_collation='Thai_CS_AI', blank=True, null=True)
    member_points = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'customers'


class Employees(models.Model):
    POSITION_CHOICES = [
        ('Manager', 'Manager'),
        ('Assistant manager', 'Assistant manager'),
        ('Sales', 'Sales'),
    ]
    employee_id = models.CharField(primary_key=True, max_length=6, db_collation='Thai_CS_AI')
    emp_name = models.CharField(max_length=100, db_collation='Thai_CS_AI')
    position = models.CharField(max_length=100, choices=POSITION_CHOICES, db_collation='Thai_CS_AI', blank=True, null=True)
    emp_phone = models.CharField(max_length=50, db_collation='Thai_CS_AI', blank=True, null=True)
    hire_date = models.DateField(blank=True, null=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    emp_status = models.CharField(max_length=50, db_collation='Thai_CS_AI', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'employees'


class Ingredients(models.Model):
    ingredient_id = models.CharField(primary_key=True, max_length=6, db_collation='Thai_CS_AI')
    supplier = models.ForeignKey('Suppliers', models.DO_NOTHING, blank=True, null=True)
    ingredient_name = models.CharField(max_length=150, db_collation='Thai_CS_AI')
    unit = models.CharField(max_length=50, db_collation='Thai_CS_AI', blank=True, null=True)
    stock_qty = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    min_qty = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    ingredirent_status = models.CharField(max_length=20, db_collation='Thai_CS_AI', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'ingredients'


class OrderDetails(models.Model):
    order_detail_id = models.AutoField(primary_key=True)
    order = models.ForeignKey('Orders', models.DO_NOTHING)
    product = models.ForeignKey('Products', models.DO_NOTHING)
    quantity = models.IntegerField(blank=True, null=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=21, decimal_places=2, blank=True, null=True)
    note = models.CharField(max_length=255, db_collation='Thai_CS_AI', blank=True, null=True)
    sweetness = models.IntegerField(default=100, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'order_details'


class Orders(models.Model):
    order_id = models.CharField(primary_key=True, max_length=6, db_collation='Thai_CS_AI')
    customer = models.ForeignKey(Customers, models.DO_NOTHING, blank=True, null=True)
    employee = models.ForeignKey(Employees, models.DO_NOTHING)
    order_datetime = models.DateTimeField(blank=True, null=True)
    order_type = models.CharField(max_length=20, db_collation='Thai_CS_AI', blank=True, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_status = models.CharField(max_length=20, db_collation='Thai_CS_AI', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'orders'


class Payments(models.Model):
    payment_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Orders, models.DO_NOTHING)
    payment_datetime = models.DateTimeField(blank=True, null=True)
    payment_method = models.CharField(max_length=50, db_collation='Thai_CS_AI', blank=True, null=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20, db_collation='Thai_CS_AI', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'payments'


class Products(models.Model):
    product_id = models.CharField(primary_key=True, max_length=6, db_collation='Thai_CS_AI')
    category = models.ForeignKey(Categories, models.DO_NOTHING)
    product_name = models.CharField(max_length=150, db_collation='Thai_CS_AI')
    description = models.TextField(db_collation='Thai_CS_AI', blank=True, null=True)  # This field type is a guess.
    price = models.DecimalField(max_digits=10, decimal_places=2)
    size = models.CharField(max_length=50, db_collation='Thai_CS_AI', blank=True, null=True)
    is_active = models.CharField(max_length=10, db_collation='Thai_CS_AI')

    class Meta:
        managed = True
        db_table = 'products'


class Suppliers(models.Model):
    supplier_id = models.CharField(primary_key=True, max_length=6, db_collation='Thai_CS_AI')
    supplier_name = models.CharField(max_length=150, db_collation='Thai_CS_AI')
    contact_name = models.CharField(max_length=100, db_collation='Thai_CS_AI', blank=True, null=True)
    phone = models.CharField(max_length=20, db_collation='Thai_CS_AI', blank=True, null=True)
    email = models.CharField(max_length=100, db_collation='Thai_CS_AI', blank=True, null=True)
    address = models.CharField(max_length=255, db_collation='Thai_CS_AI', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'suppliers'

class Recipes(models.Model):
    recipe_id = models.CharField(primary_key=True, max_length=6, db_collation='Thai_CS_AI')
    product = models.ForeignKey(Products, models.DO_NOTHING)
    ingredient = models.ForeignKey(Ingredients, models.DO_NOTHING)
    quantity_used = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = True
        db_table = 'recipes'
