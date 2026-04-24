from itertools import product
from multiprocessing import context
from django.contrib import messages
import random
import re
from decimal import Decimal
from django.shortcuts import redirect, render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from .models import Customers, Categories, Employees, Ingredients, OrderDetails, Products, Suppliers, Orders, Payments, Recipes
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Sum, Q #, F
from django.db.models import F
from django.urls import reverse

# Create your views here.
def clean_note(note):
    if not note: return ""
    # ลบส่วน "ท็อปปิ้ง: ..., " หรือ "ท็อปปิ้ง: ..." ออก
    cleaned = re.sub(r'ท็อปปิ้ง:.*?(, |$)', '', note)
    # ลบคอมม่าส่วนเกินที่อาจเกิดจากการตัด
    cleaned = re.sub(r', , ', ', ', cleaned).strip(', ')
    return cleaned

def home(request):
    
    # --- อัปเดตสถานะเมนูอัตโนมัติก่อนแสดงหน้า Home ---
    # 1. หาเมนูที่ควรเป็น Sold out (วัตถุดิบตัวใดตัวหนึ่งในสูตร <= min_qty)
    low_stock_ids = Recipes.objects.filter(
        ingredient__stock_qty__lte=F('ingredient__min_qty')
    ).values_list('product_id', flat=True).distinct()

    # 2. อัปเดตเมนูที่วัตถุดิบไม่พอให้เป็น 'Sold out'
    Products.objects.filter(product_id__in=low_stock_ids).update(is_active='Sold out')

    # 3. อัปเดตเมนูที่มีวัตถุดิบครบถ้วนให้กลับมาเป็น 'True' (พร้อมขาย)
    Products.objects.exclude(product_id__in=low_stock_ids).filter(
        is_active__in=['True', 'Sold out']
    ).update(is_active='True')

    # แสดงทั้งเมนูที่พร้อมขาย (True) และของหมด (Sold out)
    menu = Products.objects.filter(is_active__in=['True', 'Sold out']).order_by('category')
    product_type = Categories.objects.all()
                
    context = {
        'menu': menu,
        'product_type': product_type
    }
    return render(request, 'index.html', context=context)

def _get_pending_order_from_session(request):
    order_id = request.session.get('current_order_id')
    if not order_id:
        return None
    return Orders.objects.filter(order_id=order_id, order_status='Pending').first()

def payment(request):
    order = _get_pending_order_from_session(request)
    order_items = []
    total = 0
    menu = Products.objects.all()

    if order:
        order_items = OrderDetails.objects.filter(order=order)
        for item in order_items:
            item.note = clean_note(item.note)
        total = sum((item.unit_price or 0) * (item.quantity or 0) for item in order_items)

    member_info = order.customer if order and order.customer else None

    return render(request, 'payment.html', {
        'order': order,
        'order_items': order_items,
        'total': total,
        'menu': menu,
        'member_info': member_info,
    })

def remove_order_item(request, item_id):
    item = get_object_or_404(OrderDetails, pk=item_id)
    order = item.order
    item.delete()
    order.total_amount = sum(od.unit_price * od.quantity for od in OrderDetails.objects.filter(order=order)) or 0
    order.save()
    return redirect('payment')

def orderdetail(request):
    ingredients = Ingredients.objects.filter(unit='Topping')
    existing_order = _get_pending_order_from_session(request)
    existing_items = []
    if existing_order:
        existing_items = OrderDetails.objects.filter(order=existing_order)

    if request.method == 'POST':
        product_name = request.POST.get('product_name')
        quantity = int(request.POST.get('quantity'))
        final_price = float(request.POST.get('final_price'))
        drink_type = request.POST.get('drink_type')
        size = request.POST.get('size')
        sweetness = request.POST.get('sweetness')
        allergy = "แพ้นม/ครีม" if request.POST.get('allergy_milk') else "ไม่มีอาการแพ้"
        user_note = request.POST.get('note', '')
        selected_toppings = request.POST.getlist('toppings')
        topping_names = []
        for tid in selected_toppings:
            ing = Ingredients.objects.filter(ingredient_id=tid).first()
            if ing:
                topping_names.append(ing.ingredient_name)

        full_note = f"ประเภท: {drink_type}, ไซส์: {size}, หวาน: {sweetness}%, {allergy}, หมายเหตุ: {user_note}"
        product = Products.objects.filter(product_name=product_name).first()
        
        emp_id = request.session.get('employee_id')
        emp = Employees.objects.filter(employee_id=emp_id).first()
        
        if not emp:
            sales_employees = Employees.objects.filter(position='Sales')
            if not sales_employees.exists():
                sales_employees = Employees.objects.filter(position='พนักงานขาย')
            emp = random.choice(list(sales_employees)) if sales_employees.exists() else Employees.objects.first()
        
        order = _get_pending_order_from_session(request)

        if not order:
            last_order = Orders.objects.filter(order_id__startswith='OR').order_by('-order_id').first()
            next_num = int(last_order.order_id[2:]) + 1 if last_order else 1
            order_id = f"OR{next_num:04d}"
            order = Orders.objects.create(order_id=order_id, employee=emp, order_datetime=timezone.now(), total_amount=Decimal('0.00'), order_status='Pending', order_type='Walk-in')
            request.session['current_order_id'] = order.order_id

        unit_price = final_price / quantity if quantity != 0 else 0
        OrderDetails.objects.create(
            order=order, 
            product=product, 
            quantity=quantity, 
            unit_price=unit_price, 
            note=full_note,
            sweetness=int(sweetness) if sweetness else 100
        )
        order.total_amount = (order.total_amount or Decimal('0.00')) + Decimal(str(final_price))
        order.save()
        return redirect('payment')

    return render(request, 'orderdetail.html', {'ingredient': ingredients, 'existing_order': existing_order, 'existing_items': existing_items})

def login(request):
    if request.method == 'POST':
        emp_id = request.POST.get('employee_id')
        password = request.POST.get('password')
        try:
            employee = Employees.objects.get(employee_id=emp_id)
            if employee.emp_phone == password: 
                request.session['employee_id'] = employee.employee_id
                request.session['employee_name'] = employee.emp_name
                request.session['employee_position'] = employee.position
                return redirect('employee_nav')
            else:
                messages.error(request, "รหัสผ่านไม่ถูกต้อง")
        except Employees.DoesNotExist:
            messages.error(request, "ไม่พบรหัสพนักงานนี้ในระบบ")
    return render(request, 'login.html')

def employee_nav(request):
    if 'employee_id' not in request.session: return redirect('login')
    context = {
        'emp_name': request.session.get('employee_name'),
        'emp_position': request.session.get('employee_position')
    }
    return render(request, 'employee_nav.html', context)

def register_customer(request):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    name, phone = request.POST.get('name', '').strip(), request.POST.get('phone', '').strip()
    if not name or not phone: return JsonResponse({'error': 'กรุณากรอกข้อมูลให้ครบถ้วน'}, status=400)
    if Customers.objects.filter(cus_phone=phone).exists(): return JsonResponse({'error': 'เบอร์โทรศัพท์นี้เป็นสมาชิกอยู่แล้ว'}, status=400)
    last_customer = Customers.objects.filter(customer_id__startswith='C').order_by('-customer_id').first()
    next_id_num = int(last_customer.customer_id[1:]) + 1 if last_customer else 1
    new_customer_id = f"C{next_id_num:05d}"
    try:
        customer = Customers.objects.create(customer_id=new_customer_id, cus_name=name, cus_phone=phone, member_points=0, created_at=timezone.now())
        order = _get_pending_order_from_session(request)
        if order: 
            order.customer = customer
            order.save()
        return JsonResponse({'success': True, 'message': 'สมัครสมาชิกสำเร็จ', 'customer_id': customer.customer_id, 'name': customer.cus_name, 'phone': customer.cus_phone})
    except Exception as e: return JsonResponse({'error': str(e)}, status=500)

def get_customer_info(request):
    phone = request.GET.get('phone', '').strip()
    if not phone:
        return JsonResponse({'error': 'กรุณากรอกเบอร์โทรศัพท์'}, status=400)
    
    customer = Customers.objects.filter(cus_phone=phone).first()
    if customer:
        return JsonResponse({
            'success': True,
            'name': customer.cus_name,
            'points': customer.member_points or 0
        })
    else:
        return JsonResponse({'success': False, 'message': 'ไม่พบข้อมูลสมาชิก'})

def submit_order(request):
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    order = _get_pending_order_from_session(request)
    if not order: return JsonResponse({'error': 'No order found'}, status=400)
    
    phone = request.POST.get('phone', '').strip()
    
    payment_method = request.POST.get('payType', 'Cash')
    if payment_method == 'qr': 
        payment_method = 'QR Code'
    elif payment_method == 'credit': 
        payment_method = 'Credit Card'
    else: 
        payment_method = 'Cash'

    if phone:
        customer = Customers.objects.filter(cus_phone=phone).first()
        if customer and order.total_amount >= 50:
            customer.member_points = (customer.member_points or 0) + int(order.total_amount // 50) * 5
            customer.save()
            order.customer = customer
    
    order.order_status = 'Confirmed'
    order.save()

    order_items = OrderDetails.objects.filter(order=order)
    for item in order_items:
        recipes = Recipes.objects.filter(product=item.product)
        for recipe in recipes:
            ingredient = recipe.ingredient
            qty_used_per_unit = recipe.quantity_used or Decimal('0')
            
            if ingredient.ingredient_id == 'IN0002':
                sweetness_factor = Decimal(str(item.sweetness or 100)) / Decimal('100')
                qty_used_per_unit = qty_used_per_unit * sweetness_factor

            order_qty = Decimal(str(item.quantity or 0))
            total_deduction = qty_used_per_unit * order_qty
            
            current_stock = ingredient.stock_qty or Decimal('0')
            ingredient.stock_qty = current_stock - total_deduction
            
            min_limit = ingredient.min_qty or Decimal('0')
            if ingredient.stock_qty <= min_limit:
                ingredient.ingredirent_status = 'Low Stock'
            else:
                ingredient.ingredirent_status = 'Normal'
            
            ingredient.save()

    low_stock_ids = Recipes.objects.filter(
        ingredient__stock_qty__lte=F('ingredient__min_qty')
    ).values_list('product_id', flat=True).distinct()

    Products.objects.filter(product_id__in=low_stock_ids).update(is_active='False')

    Products.objects.exclude(product_id__in=low_stock_ids).filter(
        is_active__in=['True', 'False']
    ).update(is_active='True')

    Payments.objects.create(
        order=order,
        payment_datetime=timezone.now(),
        payment_method=payment_method,
        amount_paid=order.total_amount,
        payment_status='Completed'
    )
    
    order_items_data = []
    for item in order_items:
        order_items_data.append({
            'name': f"{item.product.product_name} ({item.product.size})",
            'quantity': item.quantity,
            'price': float(item.unit_price),
            'note': clean_note(item.note)
        })
    
    points_earned = 0
    if order.customer and order.total_amount >= 50:
        points_earned = int(order.total_amount // 50) * 5

    response_data = {
        'success': True,
        'order_id': order.order_id,
        'datetime': timezone.now().strftime('%d/%m/%Y %H:%M:%S'),
        'items': order_items_data,
        'total': float(order.total_amount),
        'payment_method': payment_method,
        'customer_name': order.customer.cus_name if order.customer else 'ลูกค้าทั่วไป',
        'points_earned': points_earned,
        'redirect': reverse('home')
    }

    request.session.pop('current_order_id', None)
    return JsonResponse(response_data)

def get_order_details(request):
    order_id = request.GET.get('order_id')
    order = get_object_or_404(Orders, pk=order_id)
    order_items = OrderDetails.objects.filter(order=order)
    payment = Payments.objects.filter(order=order).first()
    
    order_items_data = []
    for item in order_items:
        order_items_data.append({
            'name': f"{item.product.product_name} ({item.product.size})",
            'quantity': item.quantity,
            'price': float(item.unit_price),
            'note': clean_note(item.note)
        })
    
    points_earned = int(order.total_amount // 50) * 5 if order.customer and order.total_amount >= 50 else 0

    response_data = {
        'success': True,
        'order_id': order.order_id,
        'datetime': order.order_datetime.strftime('%d/%m/%Y %H:%M:%S'),
        'items': order_items_data,
        'total': float(order.total_amount),
        'payment_method': payment.payment_method if payment else 'N/A',
        'customer_name': order.customer.cus_name if order.customer else 'ลูกค้าทั่วไป',
        'points_earned': points_earned,
    }
    return JsonResponse(response_data)

def admin_manage(request):
    if 'employee_id' not in request.session: return redirect('login')
    
    search_query = request.GET.get('search', '').strip()
    
    # ดึงหมวดหมู่ทั้งหมดมาก่อน
    categories = Categories.objects.all().order_by('category_id')
    
    # ดึงสินค้าทั้งหมดพร้อมข้อมูลหมวดหมู่ (select_related)
    all_products = Products.objects.all().select_related('category').order_by('product_id')
    
    # ดึงออเดอร์ทั้งหมด
    order_list = Orders.objects.all().select_related('customer').order_by('-order_datetime')

    # ถ้ามีการค้นหา ให้กรองทั้งสินค้าและออเดอร์
    if search_query:
        all_products = all_products.filter(
            Q(product_name__icontains=search_query) |
            Q(product_id__icontains=search_query)
        )
        order_list = order_list.filter(
            Q(order_id__icontains=search_query) | 
            Q(customer__cus_phone__icontains=search_query)
        )

    # ทำ Pagination แยกกัน
    products_paginator = Paginator(all_products, 50) # เพิ่มเป็น 50 ต่อหน้าให้เห็นข้อมูลเยอะขึ้น
    p_page_num = request.GET.get('p_page', 1)
    products_page = products_paginator.get_page(p_page_num)

    orders_paginator = Paginator(order_list, 20)
    page_num = request.GET.get('page', 1)
    orders_page = orders_paginator.get_page(page_num)

    return render(request, 'admin_manage.html', {
        'products': products_page, 
        'categories': categories, 
        'page_obj': orders_page, 
        'emp_name': request.session.get('employee_name'),
        'search_query': search_query,
        'current_p_page': p_page_num
    })

def dashboard(request):
    if 'employee_id' not in request.session: return redirect('login')
    emp_position = request.session.get('employee_position')
    if emp_position == 'Sales':
        return HttpResponse("คุณไม่มีสิทธิ์เข้าถึงหน้านี้", status=403)

    all_orders = Orders.objects.all()
    total_sales, total_orders_count = sum(order.total_amount for order in all_orders), all_orders.count()
    low_stock_count = sum(1 for ing in Ingredients.objects.all() if ing.stock_qty <= (ing.min_qty or 0))
    top_selling_items = OrderDetails.objects.values('product__product_name').annotate(total_qty=Sum('quantity')).order_by('-total_qty')[:5]
    return render(request, 'dashboard.html', {'total_sales': total_sales, 'total_orders_count': total_orders_count, 'low_stock_count': low_stock_count, 'top_selling_items': top_selling_items, 'emp_name': request.session.get('employee_name')})

def edit_product(request):
    if 'employee_id' not in request.session: return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        product_id = request.POST.get('product_id')
        product = get_object_or_404(Products, pk=product_id)
        product.product_name = request.POST.get('name')
        product.price = Decimal(request.POST.get('price'))
        
        # ปรับการ Map สถานะให้ถูกต้อง
        status_map = {'On': 'True', 'Off': 'False', 'Sold out': 'Sold out'}
        product.is_active = status_map.get(request.POST.get('status'), 'True')
        product.save()

        # จัดการรูปภาพ (ถ้ามีการอัปโหลดมาใหม่)
        if 'image' in request.FILES:
            import os
            from django.conf import settings
            image_file = request.FILES['image']
            product_dir = os.path.join(settings.BASE_DIR, 'myapp', 'static', 'img', 'product')
            os.makedirs(product_dir, exist_ok=True)
            # บันทึกทับไฟล์เดิม (หรือสร้างใหม่ถ้าไม่มี) โดยใช้ product_id เป็นชื่อไฟล์
            file_path = os.path.join(product_dir, f"{product_id}.png")
            with open(file_path, 'wb+') as destination:
                for chunk in image_file.chunks():
                    destination.write(chunk)

        return JsonResponse({'success': True, 'message': 'บันทึกข้อมูลเรียบร้อยแล้ว'})
    except Exception as e: return JsonResponse({'error': str(e)}, status=500)

def add_product(request):
    if 'employee_id' not in request.session: return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        name = request.POST.get('name')
        price = Decimal(request.POST.get('price'))
        category_id = request.POST.get('category_id')
        size = request.POST.get('size', 'S')
        status_input = request.POST.get('status', 'On')
        
        # Map สถานะให้ตรงกับระบบ
        status_map = {'On': 'True', 'Off': 'False', 'Sold out': 'Sold out'}
        status = status_map.get(status_input, 'True')

        category = get_object_or_404(Categories, pk=category_id)
        
        # สร้าง ID ใหม่แบบปลอดภัย
        last_prod = Products.objects.all().order_by('product_id').last()
        if last_prod and last_prod.product_id.startswith('P'):
            next_id = int(last_prod.product_id[1:]) + 1
        else:
            next_id = 1
        new_id = f"P{next_id:05d}"
        
        product = Products.objects.create(
            product_id=new_id, 
            product_name=name, 
            price=price, 
            category=category, 
            size=size, 
            is_active=status
        )

        if 'image' in request.FILES:
            import os
            from django.conf import settings
            image_file = request.FILES['image']
            product_dir = os.path.join(settings.BASE_DIR, 'myapp', 'static', 'img', 'product')
            os.makedirs(product_dir, exist_ok=True)
            file_path = os.path.join(product_dir, f"{new_id}.png")
            with open(file_path, 'wb+') as destination:
                for chunk in image_file.chunks(): 
                    destination.write(chunk)
        
        return JsonResponse({'success': True, 'message': 'เพิ่มเมนูเรียบร้อยแล้ว', 'product_id': new_id})
    except Exception as e: 
        return JsonResponse({'error': str(e)}, status=500)

def edit_ingredient(request):
    if 'employee_id' not in request.session: return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        ingredient = get_object_or_404(Ingredients, pk=request.POST.get('ingredient_id'))
        ingredient.supplier = get_object_or_404(Suppliers, pk=request.POST.get('supplier_id'))
        ingredient.stock_qty = Decimal(request.POST.get('stock_qty'))
        ingredient.min_qty = Decimal(request.POST.get('min_qty'))
        ingredient.unit = request.POST.get('unit')
        ingredient.ingredirent_status = 'Low Stock' if ingredient.stock_qty <= ingredient.min_qty else 'Normal'
        ingredient.save()
        return JsonResponse({'success': True, 'message': 'อัปเดตข้อมูลวัตถุดิบเรียบร้อยแล้ว'})
    except Exception as e: return JsonResponse({'error': str(e)}, status=500)

def add_ingredient(request):
    if 'employee_id' not in request.session: return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        name, supplier_id, unit = request.POST.get('name'), request.POST.get('supplier_id'), request.POST.get('unit')
        stock_qty, min_qty = Decimal(request.POST.get('stock_qty') or '0'), Decimal(request.POST.get('min_qty') or '0')
        supplier = get_object_or_404(Suppliers, pk=supplier_id)
        last_ing = Ingredients.objects.filter(ingredient_id__startswith='IN').order_by('-ingredient_id').first()
        new_id = f"IN{int(last_ing.ingredient_id[2:])+1:04d}" if last_ing else "IN0001"
        
        Ingredients.objects.create(ingredient_id=new_id, ingredient_name=name, supplier=supplier, unit=unit, stock_qty=stock_qty, min_qty=min_qty, ingredirent_status='Normal' if stock_qty > min_qty else 'Low Stock')
        return JsonResponse({'success': True, 'message': 'เพิ่มวัตถุดิบใหม่เรียบร้อยแล้ว'})
    except Exception as e: return JsonResponse({'error': str(e)}, status=500)

def queue(request):
    if 'employee_id' not in request.session: return redirect('login')
    pending_orders = Orders.objects.filter(order_status='Confirmed').order_by('order_datetime')
    ready_orders = Orders.objects.filter(order_status='Ready').order_by('order_datetime')
    for order in pending_orders: 
        order.items = OrderDetails.objects.filter(order=order)
        for item in order.items: item.note = clean_note(item.note)
    for order in ready_orders: 
        order.items = OrderDetails.objects.filter(order=order)
        for item in order.items: item.note = clean_note(item.note)
    return render(request, 'employee_state.html', {'pending_orders': pending_orders, 'ready_orders': ready_orders, 'pending_count': pending_orders.count(), 'ready_count': ready_orders.count(), 'emp_name': request.session.get('employee_name')})

def update_order_status(request, order_id, new_status):
    if 'employee_id' not in request.session: return redirect('login')
    order = get_object_or_404(Orders, pk=order_id)
    emp = Employees.objects.filter(employee_id=request.session.get('employee_id')).first()
    if emp: order.employee = emp
    order.order_status = new_status
    order.save()
    return redirect('queue')

def recipe_list(request):
    if 'employee_id' not in request.session: return redirect('login')
    low_stock_ids = Recipes.objects.filter(ingredient__stock_qty__lte=F('ingredient__min_qty')).values_list('product_id', flat=True).distinct()
    Products.objects.filter(product_id__in=low_stock_ids).update(is_active='Sold out')
    Products.objects.exclude(product_id__in=low_stock_ids).filter(is_active__in=['True', 'Sold out']).update(is_active='True')

    search_query = request.GET.get('search', '').strip()
    products = Products.objects.filter(is_active__in=['True', 'Sold out']).order_by('category', 'product_name')
    all_ingredients = Ingredients.objects.all().order_by('ingredient_name')
    if search_query: products = products.filter(product_name__icontains=search_query)
    for product in products: product.recipe_items = Recipes.objects.filter(product=product).select_related('ingredient')
    return render(request, 'recipes.html', {'products': products, 'all_ingredients': all_ingredients, 'emp_name': request.session.get('employee_name'), 'search_query': search_query})

def save_recipe(request):
    if 'employee_id' not in request.session: return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        product = get_object_or_404(Products, pk=request.POST.get('product_id'))
        product.description = request.POST.get('description', '')
        product.save()
        Recipes.objects.filter(product=product).delete()
        last_r = Recipes.objects.filter(recipe_id__startswith='RE').order_by('-recipe_id').first()
        next_num = int(last_r.recipe_id[2:]) + 1 if last_r else 1
        ingredient_ids, quantities = request.POST.getlist('ingredient_ids[]'), request.POST.getlist('quantities[]')
        for i in range(len(ingredient_ids)):
            qty = Decimal(quantities[i])
            if qty <= 0: continue
            Recipes.objects.create(recipe_id=f"RE{next_num:04d}", product=product, ingredient=get_object_or_404(Ingredients, pk=ingredient_ids[i]), quantity_used=qty)
            next_num += 1
        return JsonResponse({'success': True, 'message': 'บันทึกสูตรเรียบร้อยแล้ว'})
    except Exception as e: return JsonResponse({'error': str(e)}, status=500)

def get_recipe_details(request):
    product = get_object_or_404(Products, pk=request.GET.get('product_id'))
    recipes = Recipes.objects.filter(product=product).select_related('ingredient')
    recipe_items = [{'ingredient_id': r.ingredient.ingredient_id, 'ingredient_name': r.ingredient.ingredient_name, 'quantity': float(r.quantity_used), 'unit': r.ingredient.unit} for r in recipes]
    return JsonResponse({'success': True, 'product_name': product.product_name, 'product_id': product.product_id, 'size': product.size, 'category': product.category.category_name, 'description': product.description or '', 'items': recipe_items})

def order_history(request):
    if 'employee_id' not in request.session: return redirect('login')
    search_query = request.GET.get('search', '').strip()
    order_list = Orders.objects.all().order_by('-order_datetime')
    if search_query: order_list = order_list.filter(Q(order_id__icontains=search_query) | Q(customer__cus_phone__icontains=search_query))
    orders_page = Paginator(order_list, 20).get_page(request.GET.get('page'))
    return render(request, 'order_history.html', {'page_obj': orders_page, 'emp_name': request.session.get('employee_name'), 'search_query': search_query})

def stock_manage(request):
    if 'employee_id' not in request.session: return redirect('login')
    search_query = request.GET.get('search', '').strip()
    ingredients_list = Ingredients.objects.all().order_by('ingredient_name')
    ingredients = Ingredients.objects.all().order_by('supplier__supplier_name', 'ingredient_id')
    suppliers = Suppliers.objects.all()
    if search_query: ingredients = ingredients.filter(Q(ingredient_name__icontains=search_query) | Q(supplier__supplier_name__icontains=search_query))
    page_obj = Paginator(ingredients, 20).get_page(request.GET.get('page'))
    return render(request, 'stock_manage.html', {'ingredients': page_obj, 'all_ingredients_list': ingredients_list, 'suppliers': suppliers, 'emp_name': request.session.get('employee_name'), 'search_query': search_query})

def restock_ingredient(request):
    if 'employee_id' not in request.session: return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST': return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        ingredient = get_object_or_404(Ingredients, pk=request.POST.get('ingredient_id'))
        ingredient.stock_qty = (ingredient.stock_qty or Decimal('0')) + Decimal(request.POST.get('stock_qty') or '0')
        ingredient.ingredirent_status = 'Low Stock' if ingredient.stock_qty <= (ingredient.min_qty or Decimal('0')) else 'Normal'
        ingredient.save()
        return JsonResponse({'success': True, 'message': f'เติมสต็อก {ingredient.ingredient_name} เรียบร้อยแล้ว'})
    except Exception as e: return JsonResponse({'error': str(e)}, status=500)

def logout(request):
    request.session.flush()
    return redirect('login')
